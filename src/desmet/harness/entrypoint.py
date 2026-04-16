"""Container adapter entrypoint.

Runs inside a per-platform Docker container. Reads a StageContext JSON
file, executes the requested stage via the platform adapter, and writes
the StageResult JSON to stdout.  Progress lines go to stderr.

Usage::

    python -m desmet.harness.entrypoint <context_file>
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# Send WARNING-and-above log records to stderr so the host runner's
# _stream_stderr forwards them to the webui progress stream.  This is
# how loop-detector "[DEFENSE]" fires become visible in the live log.
# Format is minimal — the host already prefixes lines with [stage/tool].
logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    stream=sys.stderr,
    force=True,
)

from desmet.harness.context import StageContext
from desmet.harness.results import StageResult

_STAGE_METHODS = {
    "requirements": "generate_requirements",
    "codegen": "generate_code",
    "testing": "generate_tests",
    "deploy": "build_and_deploy",
}


def _attach_parent_trace_context() -> None:
    """Attach the host's OTel context from W3C env vars.

    The host runner (``container_runner.run_stage_in_container``)
    serialises the current OTel span as ``TRACEPARENT`` (and optionally
    ``TRACESTATE``) and passes it through ``docker exec -e``.  We extract
    it here so that any spans created inside the container — Langfuse
    SDK observations, LangChain CallbackHandler events, OpenInference
    auto-instrumentation — become children of the host's stage span and
    land in the same Langfuse trace.
    """
    traceparent = os.environ.get("TRACEPARENT")
    if not traceparent:
        return
    try:
        from opentelemetry.context import attach
        from opentelemetry.propagate import extract

        carrier: dict[str, str] = {"traceparent": traceparent}
        tracestate = os.environ.get("TRACESTATE")
        if tracestate:
            carrier["tracestate"] = tracestate
        attach(extract(carrier))
    except Exception as exc:  # pragma: no cover — degrade gracefully
        print(f"warn: failed to attach parent trace context: {exc}", file=sys.stderr)


def _try_init_langfuse() -> None:
    """Initialise Langfuse inside the container, degrading on failure.

    The host already passes ``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY``
    / ``LANGFUSE_HOST`` through ``docker run -e``.  Calling ``init_langfuse``
    here registers a Langfuse client (and its OTel TracerProvider) inside
    the container so that adapter-side instrumentation actually delivers
    spans to Langfuse:

      * LangGraph: ``get_langchain_callback()`` returns a real
        ``CallbackHandler`` instead of ``None``
      * CrewAI: ``CrewAIInstrumentor`` (OpenInference) emits into a real
        TracerProvider rather than the noop default
      * OpenAI Agents: ``get_openai_agents_tracing_processor()`` returns
        a real bridge
      * Agent Framework: ``record_generation(get_langfuse(), ...)`` is
        no longer a no-op

    Failure here must not abort the stage — the host-side
    ``replay_trace_to_langfuse`` will still produce a synthetic trace.
    """
    try:
        from desmet.observability import init_langfuse

        init_langfuse()
    except Exception as exc:
        print(f"warn: langfuse init skipped in container: {exc}", file=sys.stderr)


async def _run(context: StageContext, stage_name: str) -> StageResult:
    """Import the adapter, initialize, run the stage, shutdown."""
    from desmet.adapters.registry import get_adapter

    adapter = get_adapter(context.platform_id)

    # Progress goes to stderr so stdout stays clean for the result JSON
    context.progress_callback = lambda msg: print(msg, file=sys.stderr, flush=True)

    await adapter.initialize()
    try:
        method_name = _STAGE_METHODS[stage_name]
        stage_method = getattr(adapter, method_name)
        result = await stage_method(context)
        return result
    finally:
        await adapter.shutdown()


def run_entrypoint(context_path: str) -> None:
    """Main entrypoint: read context, run stage, write result."""
    import asyncio

    path = Path(context_path)
    with open(path) as f:
        data = json.load(f)

    stage_name = data.get("metadata", {}).get("stage_name", "codegen")
    context = StageContext.from_dict(data)

    # Order matters: attach the host's OTel context FIRST so that the
    # Langfuse client (which registers a TracerProvider on construction)
    # picks up the propagated trace_id, then run the adapter so all of
    # its spans become children of the host's stage span.
    _attach_parent_trace_context()
    _try_init_langfuse()

    try:
        result = asyncio.run(_run(context, stage_name))
        json.dump(result.to_dict(), sys.stdout, ensure_ascii=True, default=str)
        sys.stdout.flush()
    except Exception as e:
        # Return a failed result so the host can handle it
        error_result = StageResult(
            platform_id=context.platform_id,
            stage_name=stage_name,
            success=False,
            error_message=str(e),
        )
        json.dump(error_result.to_dict(), sys.stdout, ensure_ascii=True, default=str)
        sys.stdout.flush()
        sys.exit(1)
    finally:
        # Flush Langfuse so buffered observations reach the server
        # before the container process exits.
        try:
            from desmet.observability import get_langfuse

            lf = get_langfuse()
            if lf is not None:
                lf.flush()
        except Exception:
            pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m desmet.harness.entrypoint <context_file>", file=sys.stderr)
        sys.exit(2)
    run_entrypoint(sys.argv[1])
