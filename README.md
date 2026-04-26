# Systematic Evaluation of Agentic Platforms

A DESMET-based evaluation framework for comparing 9 agentic platforms across a standardized software development pipeline. All platforms run the same model against the same tasks, isolating what each framework contributes independently of LLM performance.

## Platforms

| Category | Platforms |
|----------|-----------|
| Multi-Agent Frameworks | LangGraph, CrewAI, Microsoft Agent Framework |
| Agent SDK Runtimes | OpenAI Agents SDK, Google ADK |
| Visual / Workflow Platforms | Flowise, LangFlow, Dify, n8n |

## Pipeline

Each platform adapter implements a 5-stage SDLC pipeline:

| Stage | Name | Purpose |
|-------|------|---------|
| 1 | Story Loading | Load user stories and prepare evaluation context |
| 2 | Requirements Analysis | Analyse stories into structured requirements and UML diagrams |
| 3 | Code Generation | Implement the solution using platform-specific agents |
| 4 | Test Generation | Write and execute a test suite against generated code |
| 5 | Build & Deploy | Build the project and verify deployment readiness |

Scoring uses 6 rubric dimensions (0-3 scale) mapped to 4 cross-cutting evaluation dimensions (1-5 Likert): Pipeline Completeness, Efficiency, Orchestration, and Autonomy.

## Project Structure

```
src/desmet/
    harness/             Evaluation engine (adapter ABC, runner, metrics, trace)
    adapters/            Platform adapters (one per platform)
    stages/              Pipeline stages (stage1_stories through stage5_deploy)
    webui/               Management Console (FastAPI + Svelte)
    dashboard/           Results dashboard (Plotly charts)
    cli.py               CLI entrypoint
    llm_config.py        Centralised LLM configuration
    observability.py     Langfuse tracing + structlog
    cost_calculator.py   Token cost estimation

config/                  Platform definitions (platforms.yaml), environment config
data/stories/            YAML user story definitions (basic/intermediate/advanced)
infrastructure/          Per-platform Dockerfiles, Docker Compose, base eval image
docs/report/             Academic report (Typst)
tests/                   Test suite
```

## Prerequisites

- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — Python package manager.
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
- **Docker Engine** — used to isolate each platform adapter. Must be running before starting a benchmark run.
  - macOS/Windows: install [Docker Desktop](https://docs.docker.com/desktop/) and launch it before using the console.
  - Linux: install [Docker Engine](https://docs.docker.com/engine/install/) and ensure the `docker` service is active.

## Quick Start

```bash
# Install frontend
cd src/desmet/webui/frontend && bun install && bun run build

# Install core dependencies (harness, webui — no platform SDKs)
uv sync

# Launch the Management Console
uv run desmet

# Run tests
uv run pytest
```

## Platform Isolation

Each SDK platform runs inside its own Docker container with only its dependencies installed. This avoids version conflicts between frameworks (e.g. incompatible opentelemetry pins across CrewAI, Agent Framework, and Google ADK).

Platform images are built automatically on first evaluation run, or manually via the webui. If no Docker image exists for a platform, the runner falls back to in-process execution.

Visual platforms (Flowise, Dify, n8n, LangFlow) run via Docker Compose — see `infrastructure/`.

## Adding a New Platform

1. Write an adapter extending `ToolAgentAdapter` (see `src/desmet/adapters/` for examples)
2. Add an entry to `config/platforms.yaml`
3. Add your framework's dependencies as an optional extra in `pyproject.toml`
4. Copy `infrastructure/Dockerfile.framework.example` and update the extra name

## Methodology

This project applies the DESMET methodology (Determining an Evaluation Method for Software Engineering Methods and Tools) to systematically compare agentic platforms using representative software engineering tasks.

## References

- Kitchenham, B., Linkman, S., & Law, D. (1997). DESMET: a methodology for evaluating software engineering methods and tools.
- Ferrari, A., Mazzanti, F., Basile, D., & ter Beek, M. H. (2021). Systematic evaluation and usability analysis of formal methods tools for railway signaling system design.
