"""
Observability: structured logging (structlog) and Langfuse tracing.

Langfuse is a core dependency — evaluation runs require it for trace
storage and the management console surfaces Langfuse data in every
dashboard view.  ``init_langfuse()`` raises ``RuntimeError`` when the
SDK is missing or the required environment variables are not set.

Usage::

    from desmet.observability import configure_logging, get_logger, init_langfuse

    configure_logging(verbose=True)
    log = get_logger("my_module")
    log.info("hello", key="value")
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import structlog
from structlog.stdlib import ProcessorFormatter

# ---------------------------------------------------------------------------
# structlog configuration
# ---------------------------------------------------------------------------

def configure_logging(verbose: bool = False) -> None:
    """Configure structlog to wrap stdlib logging.

    Third-party libraries that use stdlib ``logging`` will also be formatted
    through the structlog processor chain via ``ProcessorFormatter``.
    """
    level = logging.DEBUG if verbose else logging.INFO

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ExtraAdder(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger, optionally bound to *name*."""
    return structlog.get_logger(name)


# ---------------------------------------------------------------------------
# Langfuse (optional)
# ---------------------------------------------------------------------------

try:
    from langfuse import Langfuse as _Langfuse  # type: ignore[assignment]  # noqa: N811
except ImportError:
    _Langfuse = None

_langfuse_client: Any | None = None

_log = get_logger("desmet.observability")


def _suppress_otel_noise() -> None:
    """Silence OpenTelemetry export errors when no collector is running.

    Langfuse v3 auto-registers an OTel exporter that tries to POST to
    ``localhost:3100``.  When Langfuse isn't configured we silence the
    noisy ``ConnectionRefused`` tracebacks by raising the OTel SDK log
    level to CRITICAL.
    """
    for name in ("opentelemetry", "opentelemetry.sdk", "opentelemetry.exporter"):
        logging.getLogger(name).setLevel(logging.CRITICAL)


def init_langfuse() -> Any:
    """Initialise the Langfuse client from environment variables.

    Langfuse is a core dependency — this function raises ``RuntimeError``
    when the SDK is not installed or the required environment variables
    (``LANGFUSE_PUBLIC_KEY``, ``LANGFUSE_SECRET_KEY``) are missing.

    Returns the connected client instance.
    """
    global _langfuse_client  # noqa: PLW0603

    # Already initialised — return cached client.
    if _langfuse_client is not None:
        return _langfuse_client

    if _Langfuse is None:
        raise RuntimeError(
            "Langfuse SDK is not installed.  Install it with: uv pip install langfuse"
        )

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        raise RuntimeError(
            "Langfuse is not configured.  Set LANGFUSE_PUBLIC_KEY and "
            "LANGFUSE_SECRET_KEY in your .env file."
        )

    _langfuse_client = _Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
    )
    # Langfuse v3 registers an OTel TracerProvider on init; downstream
    # libraries (LangChain, litellm) may try to register their own,
    # triggering a harmless but noisy "Overriding of current TracerProvider
    # is not allowed" warning.  Suppress it.
    _suppress_otel_noise()
    _log.info("langfuse_status", status="connected", host=host)
    return _langfuse_client


def get_langfuse() -> Any | None:
    """Return the current Langfuse client (may be ``None``)."""
    return _langfuse_client


def shutdown_langfuse() -> None:
    """Flush and shut down the Langfuse client."""
    global _langfuse_client  # noqa: PLW0603
    if _langfuse_client is not None:
        _langfuse_client.flush()
        _langfuse_client.shutdown()
        _langfuse_client = None


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

_session_id: str | None = None


def start_session(label: str | None = None) -> str:
    """Create a new Langfuse session ID for this evaluation run.

    All traces created after this call will be grouped under the same
    session in the Langfuse UI.  Call once at the start of an evaluation.

    Returns the generated session ID.
    """
    global _session_id  # noqa: PLW0603
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    _session_id = f"desmet-{label}-{ts}" if label else f"desmet-{ts}"
    _log.info("langfuse_session", session_id=_session_id)
    return _session_id


def get_session_id() -> str | None:
    """Return the current session ID, or ``None``."""
    return _session_id


# ---------------------------------------------------------------------------
# Trace / span context managers  (Langfuse SDK v3 API)
# ---------------------------------------------------------------------------

@contextmanager
def langfuse_trace(
    name: str,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Generator[Any | None, None, None]:
    """Open a top-level Langfuse span (acts as trace root).

    If a session has been started via ``start_session()``, the trace is
    automatically associated with that session so all traces in one
    evaluation run are grouped together in the Langfuse UI.

    Yields the ``LangfuseSpan`` or ``None`` when unavailable.
    """
    client = get_langfuse()
    if client is None:
        yield None
        return

    session_id = get_session_id()

    from langfuse import propagate_attributes  # type: ignore[import-untyped]

    ctx = propagate_attributes(session_id=session_id) if session_id else propagate_attributes()

    with ctx:
        with client.start_as_current_observation(name=name, metadata=metadata or {}) as span:
            yield span


@contextmanager
def langfuse_span(
    parent: Any | None,
    name: str,
    metadata: dict[str, Any] | None = None,
    input: Any | None = None,  # noqa: A002
) -> Generator[Any | None, None, None]:
    """Open a child span on *parent*.  No-op when ``parent is None``."""
    if parent is None:
        yield None
        return

    with parent.start_as_current_observation(name=name, metadata=metadata or {}, input=input) as span:
        yield span


# ---------------------------------------------------------------------------
# Framework-native callback helpers
# ---------------------------------------------------------------------------


def get_langchain_callback(*, session_id: str | None = None) -> Any | None:
    """Return a Langfuse CallbackHandler for LangChain/LangGraph, or None.

    The handler automatically captures every LLM call, tool invocation,
    and chain execution as nested spans in Langfuse.  When *session_id*
    is omitted the module-level session (from ``start_session()``) is used.
    """
    if get_langfuse() is None:
        return None
    try:
        from langfuse.langchain import CallbackHandler  # type: ignore[import-untyped]

        # In Langfuse v4, session_id is propagated via propagate_attributes()
        # context manager (set in langfuse_trace), not via the constructor.
        return CallbackHandler()
    except ImportError:
        return None


def get_openai_agents_tracing_processor() -> Any | None:
    """Return an Agents SDK ``TracingProcessor`` that forwards spans to Langfuse.

    Each generation (LLM call), function (tool call), and agent span produced
    by ``Runner.run()`` is recorded as a nested observation under the current
    Langfuse trace.  Returns ``None`` when Langfuse is not available.
    """
    client = get_langfuse()
    if client is None:
        return None

    try:
        from agents.tracing import TracingProcessor as _TP
        from agents.tracing import (
            AgentSpanData,
            FunctionSpanData,
            GenerationSpanData,
        )
    except ImportError:
        return None

    class LangfuseTracingProcessor(_TP):
        """Bridge OpenAI Agents SDK spans → Langfuse observations."""

        def __init__(self, lf_client):
            self._client = lf_client
            # span_id → (span_type, context_manager, observation)
            self._spans: dict[str, tuple[str, Any, Any]] = {}

        def on_trace_start(self, trace) -> None:
            pass  # outer Langfuse trace is managed by the runner

        def on_trace_end(self, trace) -> None:
            pass

        def _enter_observation(self, span_id, span_type, ctx_mgr):
            """Enter a context manager and store the yielded observation."""
            observation = ctx_mgr.__enter__()
            self._spans[span_id] = (span_type, ctx_mgr, observation)

        def on_span_start(self, span) -> None:
            data = span.span_data

            if isinstance(data, GenerationSpanData):
                cm = self._client.start_as_current_observation(
                    name=f"llm-{data.model or 'unknown'}",
                    as_type="generation",
                    model=data.model,
                    input=data.input,
                    metadata={"model_config": dict(data.model_config) if data.model_config else {}},
                )
                self._enter_observation(span.span_id, "generation", cm)

            elif isinstance(data, FunctionSpanData):
                cm = self._client.start_as_current_observation(
                    name=f"tool-{data.name}",
                    input=data.input,
                    metadata={"tool_name": data.name},
                )
                self._enter_observation(span.span_id, "function", cm)

            elif isinstance(data, AgentSpanData):
                cm = self._client.start_as_current_observation(
                    name=f"agent-{data.name}",
                    metadata={"agent_name": data.name},
                )
                self._enter_observation(span.span_id, "agent", cm)

        def on_span_end(self, span) -> None:
            entry = self._spans.pop(span.span_id, None)
            if entry is None:
                return
            span_type, ctx_mgr, observation = entry
            data = span.span_data

            try:
                if span_type == "generation" and isinstance(data, GenerationSpanData):
                    # Filter usage to only standard keys Langfuse accepts
                    usage = {}
                    if data.usage:
                        for k in ("input_tokens", "output_tokens", "total_tokens"):
                            if k in data.usage:
                                usage[k] = data.usage[k]
                    observation.update(
                        output=data.output,
                        usage_details=usage,
                    )
                elif span_type == "function" and isinstance(data, FunctionSpanData):
                    observation.update(output=str(data.output) if data.output else None)
            finally:
                ctx_mgr.__exit__(None, None, None)

        def shutdown(self) -> None:
            for _, (_, ctx_mgr, _) in list(self._spans.items()):
                ctx_mgr.__exit__(None, None, None)
            self._spans.clear()

        def force_flush(self) -> None:
            self._client.flush()

    return LangfuseTracingProcessor(client)


def record_generation(
    parent: Any | None,
    name: str,
    model: str | None = None,
    input: Any | None = None,  # noqa: A002
    output: Any | None = None,
    usage: dict[str, int] | None = None,
    cost: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record an LLM generation observation on *parent*.  No-op if ``None``."""
    if parent is None:
        return

    cost_details = {"total": cost} if cost else {}

    with parent.start_as_current_observation(
        name=name,
        as_type="generation",
        model=model,
        input=input,
        output=output,
        usage_details=usage or {},
        cost_details=cost_details,
        metadata=metadata or {},
    ):
        pass  # generation is recorded and ended on context exit


def replay_trace_to_langfuse(
    parent: Any | None,
    stage_name: str,
    trace: Any,
    model: str | None = None,
) -> None:
    """Replay an :class:`AgentTrace` as nested Langfuse observations.

    Creates a span per conversation message and per tool call so the
    Langfuse UI shows the full execution timeline.  Called from the
    host runner after the container returns its ``StageResult``.

    No-op when *parent* is ``None``.
    """
    if parent is None:
        return

    # Build usage summary from the trace for the top-level generation
    input_tokens = getattr(trace, "total_tokens_input", 0) or 0
    output_tokens = getattr(trace, "total_tokens_output", 0) or 0
    usage = {}
    if input_tokens or output_tokens:
        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
    cost_usd = getattr(trace, "total_cost_usd", 0.0) or 0.0

    has_errors = bool(getattr(trace, "errors", None))

    with parent.start_as_current_observation(
        name=f"agent-{stage_name}",
        as_type="generation",
        model=model,
        usage_details=usage,
        cost_details={"total": cost_usd} if cost_usd > 0 else {},
        level="ERROR" if has_errors else "DEFAULT",
        metadata={
            "stage": stage_name,
            **(getattr(trace, "framework_metrics", None) or {}),
        },
    ) as stage_obs:
        # Record each message as a nested observation
        for msg in getattr(trace, "messages", []):
            obs_type = "generation" if msg.role == "assistant" else None
            kwargs: dict[str, Any] = {
                "name": f"{msg.role}-message",
                "input": msg.content[:200] if msg.content else "",
                "metadata": {"role": msg.role, **(msg.metadata or {})},
            }
            if obs_type:
                kwargs["as_type"] = obs_type
                kwargs["model"] = model
            with stage_obs.start_as_current_observation(**kwargs):
                pass

        # Record each tool call as a nested span
        for tc in getattr(trace, "tool_calls", []):
            with stage_obs.start_as_current_observation(
                name=f"tool-{tc.tool_name}",
                input=tc.arguments,
                output=str(tc.result)[:500] if tc.result else None,
                level="ERROR" if not tc.success else "DEFAULT",
                metadata={
                    "tool_name": tc.tool_name,
                    "success": tc.success,
                    "duration_ms": tc.duration_ms,
                },
            ):
                pass
