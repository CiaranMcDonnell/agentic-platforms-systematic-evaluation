"""
DESMET Evaluation Framework — CLI Entry Point

Launches the DESMET Management Console (browser UI) which provides
full control over evaluation runs, platform management, Docker
infrastructure, and results viewing.

Usage:
    desmet                          # Start on default port 8042
    desmet --port 9000              # Custom port
    desmet --reload                 # Dev mode with auto-reload
    desmet --clean-on-exit          # Remove platform images on shutdown (forces rebuild)
    desmet export-typst             # Emit report tables from the latest run
"""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(
    name="desmet",
    help="DESMET Agentic Platforms Evaluation Framework — launches the Management Console.",
    invoke_without_command=True,
)

console = Console()


def _cleanup_images() -> None:
    """Remove all desmet-eval-* platform images + the base image.

    Called on Ctrl+C / process exit when --clean-on-exit is set.
    Ensures the next ``desmet`` launch rebuilds from scratch, which
    avoids stale Docker layer cache issues where a cached COPY src/
    layer keeps old source code inside the base image.
    """
    from desmet.harness.container_runner import delete_all_eval_images

    console.print("\n[bold yellow]Cleaning up platform images...[/bold yellow]")
    results = delete_all_eval_images(
        include_base=True,
        progress_callback=lambda msg: console.print(f"  {msg}"),
    )
    removed = sum(1 for ok in results.values() if ok)
    total = len(results)
    if removed == total:
        console.print(f"[green]  ✓ Removed {removed}/{total} images[/green]")
    else:
        console.print(
            f"[yellow]  Removed {removed}/{total} images "
            f"(some were not present or in use)[/yellow]"
        )


@app.callback(invoke_without_command=True)
def main_command(
    ctx: typer.Context,
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8042, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
    clean_on_exit: bool = typer.Option(
        False,
        "--clean-on-exit/--no-clean-on-exit",
        help=(
            "Remove all desmet-eval-* platform images and the base image "
            "on shutdown so the next run rebuilds from scratch. "
            "Defaults OFF to avoid the ~60-90s base-image rebuild penalty "
            "on every startup. Enable if you suspect stale Docker layer "
            "cache is holding onto old source code."
        ),
    ),
):
    """Launch the DESMET Management Console (browser UI)."""
    if ctx.invoked_subcommand is not None:
        return

    import atexit
    import uvicorn

    console.print("[bold]DESMET Management Console[/bold]")
    console.print(f"  Starting on [cyan]http://{host}:{port}[/cyan]")
    if clean_on_exit:
        console.print("  [yellow]⚠ --clean-on-exit enabled — images will be removed on shutdown[/yellow]")
    console.print("  Press Ctrl+C to stop.\n")

    # Register cleanup hook BEFORE uvicorn starts so it fires on normal
    # exit, Ctrl+C, and most abnormal exits.  atexit runs LIFO, so this
    # runs after uvicorn's own shutdown handlers.
    if clean_on_exit:
        atexit.register(_cleanup_images)

    reload_kwargs = {}
    if reload:
        reload_kwargs["reload_excludes"] = ["results", "htmlcov", "*.pyc"]

    try:
        uvicorn.run(
            "desmet.webui.api:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info",
            **reload_kwargs,
        )
    except KeyboardInterrupt:
        # Uvicorn usually catches SIGINT itself, but if Ctrl+C arrives
        # during startup before uvicorn's handler is wired up, we land
        # here.  Cleanup still runs via atexit.
        pass


@app.command("export-typst")
def export_typst_command(
    run_id: str = typer.Option(
        None, "--run-id", help="Source run ID (default: latest run in the DuckDB store)."
    ),
    out_dir: str = typer.Option(
        None,
        "--out-dir",
        help="Output directory for generated .typ files (default: docs/report/generated/).",
    ),
):
    """Emit Typst figure files from a run's scoring data.

    Generates ``per-story.typ``, ``capability-tiers.typ``,
    ``cross-cutting.typ`` and ``resource.typ`` so the evaluation
    chapter can ``#include`` them instead of hand-entering numbers.
    """
    from pathlib import Path

    from desmet.harness.typst_export import export_all

    try:
        outputs = export_all(
            run_id=run_id,
            out_dir=Path(out_dir) if out_dir else None,
        )
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    console.print(f"[green]Exported {len(outputs)} tables:[/green]")
    for name, path in outputs.items():
        console.print(f"  [cyan]{name}[/cyan]: {path}")


def main():
    from dotenv import load_dotenv
    load_dotenv()
    app()


if __name__ == "__main__":
    main()
