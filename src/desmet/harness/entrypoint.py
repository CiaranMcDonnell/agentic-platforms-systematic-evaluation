"""Container adapter entrypoint.

Runs inside a per-platform Docker container. Reads a StageContext JSON
file, executes the requested stage via the platform adapter, and writes
the StageResult JSON to stdout.  Progress lines go to stderr.

Usage::

    python -m desmet.harness.entrypoint <context_file>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from desmet.harness.context import StageContext
from desmet.harness.results import StageResult


_STAGE_METHODS = {
    "requirements": "generate_requirements",
    "codegen": "generate_code",
    "testing": "generate_tests",
    "deploy": "build_and_deploy",
}


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

    try:
        result = asyncio.run(_run(context, stage_name))
        json.dump(result.to_dict(), sys.stdout)
        sys.stdout.flush()
    except Exception as e:
        # Return a failed result so the host can handle it
        error_result = StageResult(
            platform_id=context.platform_id,
            stage_name=stage_name,
            success=False,
            error_message=str(e),
        )
        json.dump(error_result.to_dict(), sys.stdout)
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m desmet.harness.entrypoint <context_file>", file=sys.stderr)
        sys.exit(2)
    run_entrypoint(sys.argv[1])
