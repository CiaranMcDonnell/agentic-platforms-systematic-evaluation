"""
DESMET Evaluation Framework — CLI Entry Point

Launches the DESMET Management Console (browser UI) which provides
full control over evaluation runs, platform management, Docker
infrastructure, and results viewing.

Usage:
    desmet                          # Start on default port 8042
    desmet --port 9000              # Custom port
    desmet --reload                 # Dev mode with auto-reload
"""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

app = typer.Typer(
    name="desmet",
    help="DESMET Agentic Platforms Evaluation Framework — launches the Management Console.",
    invoke_without_command=True,
)

console = Console()


@app.callback(invoke_without_command=True)
def main_command(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8042, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
):
    """Launch the DESMET Management Console (browser UI)."""
    import uvicorn

    console.print("[bold]DESMET Management Console[/bold]")
    console.print(f"  Starting on [cyan]http://{host}:{port}[/cyan]")
    console.print("  Press Ctrl+C to stop.\n")

    reload_kwargs = {}
    if reload:
        reload_kwargs["reload_excludes"] = ["results", "htmlcov", "*.pyc"]

    uvicorn.run(
        "desmet.webui.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        **reload_kwargs,
    )


def main():
    app()


if __name__ == "__main__":
    main()
