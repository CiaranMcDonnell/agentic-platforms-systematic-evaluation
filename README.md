# Systematic Evaluation of Agentic Platforms

A DESMET-based evaluation framework for comparing agentic platforms across effectiveness, efficiency, quality, reproducibility, usability, observability, and failure handling.

## Selected Platforms

| Category | Platforms |
|----------|-----------|
| Multi-Agent Frameworks | LangGraph, CrewAI, Microsoft AutoGen |
| Agent SDK Runtimes | OpenAI Agents SDK, Google ADK, Semantic Kernel |
| Visual / Workflow Platforms | Flowise, LangFlow, Dify, N8n |

## Pipeline

The evaluation follows a 6-stage pipeline (see `docs/spec/PIPELINE_SPECIFICATION.md`):

| Stage | Name | Purpose |
|-------|------|---------|
| 0 | Framework Setup & Onboarding | Measure setup friction and time-to-value |
| 1 | Requirements Engineering | Define testable requirements for all platforms |
| 2 | Requirements → User Stories | Translate into executable benchmark tasks |
| 3 | Code Generation | Execute stories per platform, capture metrics |
| 4 | Testing Generation | Evaluate generated test quality and coverage |
| 5 | Building & Deploying | Verify code builds, passes CI, and deploys |

Seven cross-cutting **evaluation dimensions** are assessed throughout: Effectiveness, Efficiency, Quality, Reproducibility, Usability/DX, Observability, and Failure Handling.

## Project Structure

```
├── src/desmet/              # Source code
│   ├── harness/             #   Evaluation engine (adapter ABC, runner, metrics)
│   ├── stages/              #   Pipeline stage implementations (stage0–stage5)
│   ├── adapters/            #   Platform adapters (one per platform)
│   ├── dimensions/          #   Cross-cutting dimension scorers
│   ├── analysis/            #   Scoring, comparison, report generation
│   └── cli.py               #   `desmet-eval` CLI entrypoint
│
├── config/                  # Platform definitions (platforms.yaml)
├── data/                    # Input data: user stories, prompts, baseline repo
│   └── stories/             #   YAML story definitions (basic/intermediate/advanced)
├── results/                 # Evaluation outputs per platform per story
├── docs/                    # All documentation
│   ├── spec/                #   Pipeline specification, UML diagrams
│   ├── report/              #   Academic report (Typst)
│   ├── report-latex/        #   Academic report (LaTeX)
│   └── literature/          #   Reference papers
├── platforms/               # Deep-dive platform explorations
├── infrastructure/          # Docker Compose, Dockerfiles
├── notebooks/               # Jupyter analysis notebooks
└── tests/                   # Test suite
```

## Quick Start

```bash
# Install uv (if not already installed)
# https://docs.astral.sh/uv/getting-started/installation/

# Install core framework + dev dependencies
uv sync

# Install with a specific platform adapter
uv sync --extra langgraph

# Run evaluation
uv run desmet-eval run --platform langgraph --story US-001

# Run tests
uv run --group test pytest
```

> **Note:** Platform extras are mutually exclusive in many cases due to
> conflicting transitive dependencies. Install one platform extra per
> virtual environment. Visual platforms (Flowise, Dify, n8n) run via
> Docker — see `infrastructure/`.

## Methodology

This project applies the DESMET (Determining an Evaluation Method for Software Engineering Methods and Tools) methodology to systematically compare agentic platforms using representative software engineering tasks.

## References

- Kitchenham, B., Linkman, S., & Law, D. (1997). DESMET: a methodology for evaluating software engineering methods and tools.
- Ferrari, A., Mazzanti, F., Basile, D., & ter Beek, M. H. (2021). Systematic evaluation and usability analysis of formal methods tools for railway signaling system design.
