"""
Observability: structured logging (structlog) and optional Langfuse tracing.

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
from contextlib import contextmanager
from typing import Any, Generator

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
    from langfuse import Langfuse as _Langfuse  # noqa: N811

    _langfuse_available = True
except ImportError:
    _langfuse_available = False

_langfuse_client: Any | None = None

_log = get_logger("desmet.observability")


def init_langfuse() -> Any | None:
    """Initialise the Langfuse client from environment variables.

    Returns the client instance, or ``None`` when Langfuse is not installed or
    the required env vars are missing.
    """
    global _langfuse_client  # noqa: PLW0603

    if not _langfuse_available:
        _log.info("langfuse_status", status="not installed — tracing disabled")
        return None

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        _log.info("langfuse_status", status="not configured — set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY")
        return None

    _langfuse_client = _Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
    )
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
# Trace / span context managers  (Langfuse SDK v3 API)
# ---------------------------------------------------------------------------

@contextmanager
def langfuse_trace(
    name: str,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Generator[Any | None, None, None]:
    """Open a top-level Langfuse span (acts as trace root).

    Yields the ``LangfuseSpan`` or ``None`` when unavailable.
    """
    client = get_langfuse()
    if client is None:
        yield None
        return

    # v3: start_as_current_span returns a context manager that auto-ends
    with client.start_as_current_span(name=name, metadata=metadata or {}) as span:
        # Tags are set via update_trace on the span
        if tags:
            span.update_trace(tags=tags)
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

    # v3: start_as_current_span on the parent span
    with parent.start_as_current_span(name=name, metadata=metadata or {}, input=input) as span:
        yield span


def record_generation(
    parent: Any | None,
    name: str,
    model: str | None = None,
    input: Any | None = None,  # noqa: A002
    output: Any | None = None,
    usage: dict[str, int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record an LLM generation observation on *parent*.  No-op if ``None``."""
    if parent is None:
        return

    with parent.start_as_current_generation(
        name=name,
        model=model,
        input=input,
        output=output,
        usage_details=usage or {},
        metadata=metadata or {},
    ):
        pass  # generation is recorded and ended on context exit
