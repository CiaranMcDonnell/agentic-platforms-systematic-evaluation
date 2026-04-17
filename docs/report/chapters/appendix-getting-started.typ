#import "../template.typ": *

= Getting Started <appendix-getting-started>

This appendix covers installing the DESMET evaluation framework and launching the management console.

== Prerequisites

- *Python 3.11+* --- managed via `uv`
- *uv* --- Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- *Bun* --- JavaScript runtime for Mermaid diagram rendering (`curl -fsSL https://bun.sh/install | bash`)
- *Docker* --- required for platform isolation (SDK adapters run in per-platform containers), Langfuse observability, and visual/workflow platform adapters; the daemon (or Docker Desktop) must be running before starting a benchmark run
- An API key for at least one LLM provider (OpenAI, Anthropic, or OpenRouter)

== Installation

#figure(
  ```bash
  git clone https://github.com/<user>/desmet-agentic-platforms.git
  cd desmet-agentic-platforms
  uv sync
  ```,
  caption: [Installing the DESMET framework],
)

`uv sync` resolves all dependencies from the lockfile, creates a virtual environment, and installs the core `desmet` package (harness and web UI) without any platform-specific SDKs. Platform SDKs are installed only inside their respective Docker containers at evaluation time.

== Configuration

Copy the example environment file and fill in API keys:

#figure(
  ```bash
  cp .env.example .env
  ```,
  caption: [Creating the environment configuration],
)

At minimum, set `OPENAI_API_KEY` (or the key for your chosen provider). The pre-configured Langfuse keys in `.env.example` connect to the local instance automatically. The framework reads all configuration from this `.env` file.

== Launching the Management Console

#figure(
  ```bash
  uv run desmet
  ```,
  caption: [Starting the management console],
)

This starts the web-based management console on `http://127.0.0.1:8042`. All evaluation operations --- starting benchmark runs, viewing results, scoring platforms, and inspecting traces --- are performed through this interface.

== Platform Isolation

#include "../diagrams/implementation/platform-isolation.typ"

Each SDK platform (LangGraph, CrewAI, Agent Framework, OpenAI Agents SDK, Google ADK) runs inside its own Docker container with only its dependencies installed, as shown in @fig-platform-isolation. This avoids version conflicts between frameworks (e.g.~incompatible `opentelemetry` pins across CrewAI, Agent Framework, and Google ADK). Platform images are built automatically on the first evaluation run, or manually via the management console. If no Docker image exists for a platform, the runner falls back to in-process execution.

Visual/workflow platforms (Flowise, Dify, n8n, LangFlow) run via Docker Compose --- see the `infrastructure/` directory.

== Running Tests

#figure(
  ```bash
  uv run pytest
  ```,
  caption: [Running the test suite],
)

== Langfuse Observability

The framework relies on a self-hosted Langfuse instance for per-LLM-call tracing, cost tracking, and scoring. Langfuse can be started directly from the management console's infrastructure panel. Once running, traces appear in the Langfuse UI and are linked from the management console's scoring panel.
