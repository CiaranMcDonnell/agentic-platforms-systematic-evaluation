"""
DESMET Evaluation CLI

Pipeline stages (executed in order):
    requirements  -- Generate requirements & UML from user stories
    codegen       -- Generate code from story and requirements
    testing       -- Generate and run tests against generated code
    deploy        -- Build the project and verify deployment readiness

Usage:
    desmet-eval run --platform langgraph --story US-001
    desmet-eval run --platform langgraph --story US-001 --stage codegen
    desmet-eval run --all --dry-run
    desmet-eval list-platforms
    desmet-eval list-stories
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from desmet.adapters.registry import (
    AdapterNotImplementedError,
    get_adapter,
    list_all_platforms,
    list_available_platforms,
)
from desmet.harness.loader import (
    StoryLoadError,
    load_all_stories,
    resolve_baseline_dir,
)
from desmet.harness.runner import EvaluationRunner, RunnerConfig
from desmet.harness.story import DifficultyLevel
from desmet.observability import configure_logging, init_langfuse, shutdown_langfuse

# Valid pipeline stage names (matches runner._STAGES keys)
VALID_STAGES = ("requirements", "codegen", "testing", "deploy", "all")

app = typer.Typer(
    name="desmet-eval",
    help="DESMET Agentic Platforms Evaluation Framework",
)

console = Console()


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

@app.command()
def run(
    platform: str = typer.Option(None, help="Platform ID to evaluate"),
    story: str = typer.Option(None, help="Story ID to run"),
    all_platforms: bool = typer.Option(False, "--all", help="Run all implemented platforms"),
    difficulty: str = typer.Option(None, help="Filter by difficulty: basic, intermediate, advanced"),
    stage: str = typer.Option(
        "all",
        help="Pipeline stage to run: requirements, codegen, testing, deploy, or all (default: all)",
    ),
    dry_run: bool = typer.Option(False, help="Dry run without executing"),
    verbose: bool = typer.Option(False, "-v", help="Verbose output"),
    baseline_dir: str = typer.Option(None, help="Path to baseline repository (default: data/baseline/)"),
    results_dir: str = typer.Option(None, help="Path to results directory (default: ./results)"),
):
    """Run the SDLC evaluation pipeline on one or more platforms.

    The pipeline consists of four stages executed in order:
    requirements -> codegen -> testing -> deploy.
    Use --stage to run only a specific stage instead of the full pipeline.
    """
    # -- Validate args -------------------------------------------------------
    if not platform and not all_platforms:
        console.print("[red]Error:[/red] Provide --platform <id> or --all")
        raise typer.Exit(code=1)
    if platform and all_platforms:
        console.print("[red]Error:[/red] --platform and --all are mutually exclusive")
        raise typer.Exit(code=1)
    if story and all_platforms:
        console.print("[red]Error:[/red] --story cannot be combined with --all")
        raise typer.Exit(code=1)

    stage_lower = stage.lower()
    if stage_lower not in VALID_STAGES:
        console.print(
            f"[red]Error:[/red] Invalid --stage '{stage}'. "
            f"Valid values: {', '.join(VALID_STAGES)}"
        )
        raise typer.Exit(code=1)

    # -- Environment & observability ------------------------------------------
    load_dotenv()
    configure_logging(verbose=verbose)
    init_langfuse()

    # -- Load stories --------------------------------------------------------
    try:
        stories = load_all_stories(difficulty=difficulty)
    except StoryLoadError as exc:
        console.print(f"[red]Error loading stories:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not stories:
        console.print("[yellow]No stories found.[/yellow]")
        raise typer.Exit(code=1)

    # -- Resolve baseline dir ------------------------------------------------
    baseline = resolve_baseline_dir(baseline_dir)

    # -- Resolve platform(s) -------------------------------------------------
    if all_platforms:
        platform_ids = list_available_platforms()
        if not platform_ids:
            console.print("[yellow]No implemented adapters available.[/yellow]")
            raise typer.Exit(code=1)
    else:
        platform_ids = [platform]

    adapters = {}
    for pid in platform_ids:
        try:
            adapters[pid] = get_adapter(pid)
        except KeyError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        except AdapterNotImplementedError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1) from exc

    # -- Build runner config -------------------------------------------------
    resolved_stage = None if stage_lower == "all" else stage_lower
    config = RunnerConfig(
        dry_run=dry_run,
        verbose=verbose,
        stage=resolved_stage,
    )
    if results_dir:
        config.results_dir = Path(results_dir)
        config.logs_dir = Path(results_dir) / "logs"

    if difficulty:
        config.difficulty_levels = [DifficultyLevel(difficulty)]

    # -- Print summary -------------------------------------------------------
    _print_run_header(platform_ids, stories, story, dry_run, baseline, resolved_stage)

    # -- Execute -------------------------------------------------------------
    runner = EvaluationRunner(
        config=config,
        platforms=adapters,
        stories=stories,
        baseline_repo=baseline,
    )

    try:
        if story:
            # Single story on a single platform
            result = asyncio.run(runner.run_single_story(platform_ids[0], story))
            _print_single_result(result)
        else:
            # Full evaluation for selected platform(s)
            summary = asyncio.run(runner.run_full_evaluation())
            _print_summary(summary)
    finally:
        shutdown_langfuse()


# ---------------------------------------------------------------------------
# list-platforms
# ---------------------------------------------------------------------------

@app.command()
def list_platforms():
    """List available platform adapters."""
    available = set(list_available_platforms())
    all_ids = list_all_platforms()

    table = Table(title="DESMET Platform Adapters")
    table.add_column("Platform ID", style="cyan")
    table.add_column("Status")

    for pid in all_ids:
        if pid in available:
            table.add_row(pid, "[green]implemented[/green]")
        else:
            table.add_row(pid, "[dim]stub[/dim]")

    console.print(table)
    console.print(f"\n{len(available)} implemented / {len(all_ids)} total")


# ---------------------------------------------------------------------------
# list-stories
# ---------------------------------------------------------------------------

@app.command()
def list_stories(
    difficulty: str = typer.Option(None, help="Filter by difficulty: basic, intermediate, advanced"),
):
    """List available user stories."""
    try:
        stories = load_all_stories(difficulty=difficulty)
    except StoryLoadError as exc:
        console.print(f"[red]Error loading stories:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not stories:
        console.print("No stories found.")
        return

    table = Table(title="User Stories")
    table.add_column("ID", style="cyan")
    table.add_column("Difficulty")
    table.add_column("Title")
    table.add_column("AC", justify="right")

    for s in stories:
        diff_color = {"basic": "green", "intermediate": "yellow", "advanced": "red"}.get(
            s.difficulty.value, "white"
        )
        table.add_row(
            s.id,
            f"[{diff_color}]{s.difficulty.value}[/{diff_color}]",
            s.title,
            str(len(s.acceptance_criteria)),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print_run_header(
    platform_ids: list[str],
    stories: list,
    story_filter: str | None,
    dry_run: bool,
    baseline: Path,
    stage: str | None = None,
):
    console.rule("[bold]DESMET Evaluation Runner[/bold]")
    console.print(f"  Platforms : {', '.join(platform_ids)}")
    if story_filter:
        console.print(f"  Story     : {story_filter}")
    else:
        console.print(f"  Stories   : {len(stories)}")
    console.print(f"  Stage     : {stage or 'all'}")
    console.print(f"  Baseline  : {baseline}")
    if dry_run:
        console.print("  [yellow]DRY RUN — no execution[/yellow]")
    console.print()


def _print_single_result(result):
    console.rule("[bold]Result[/bold]")
    console.print(f"  Story    : {result.story_id}")
    console.print(f"  Platform : {result.platform_id}")
    console.print(f"  Status   : {result.status.value}")
    if result.wall_clock_seconds:
        console.print(f"  Duration : {result.wall_clock_seconds:.1f}s")
    if result.error_message:
        console.print(f"  [red]Error: {result.error_message}[/red]")


def _print_summary(summary: dict):
    console.rule("[bold]Evaluation Summary[/bold]")
    console.print(f"  Platforms evaluated : {summary['platforms_evaluated']}")
    console.print(f"  Total stories      : {summary['stories_total']}")

    if summary.get("rankings"):
        table = Table(title="Rankings")
        table.add_column("#", justify="right")
        table.add_column("Platform")
        table.add_column("Score", justify="right")
        table.add_column("Completion", justify="right")

        for r in summary["rankings"]:
            table.add_row(
                str(r["rank"]),
                r["platform_name"],
                f"{r['overall_score']:.2f}",
                f"{r['completion_rate']:.0%}",
            )

        console.print(table)


def main():
    app()


if __name__ == "__main__":
    main()
