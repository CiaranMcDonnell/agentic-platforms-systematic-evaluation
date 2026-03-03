# Streamlit Evaluation Dashboard — Design Document

**Date:** 2026-03-03
**Status:** Approved

## Purpose

An interactive Streamlit dashboard that serves as the primary tool for evaluating agentic platforms during the DESMET evaluation process. It provides rubric-based scoring forms, cross-platform comparison charts, and publication-ready chart export for the Typst report.

## Key Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Framework | Streamlit with `st.navigation` | Best fit for data apps, multi-page, built-in form/chart support |
| Data source | `results/evaluation_results.json` (read + write) | No new storage layer, scores live alongside metrics |
| Data layer | Reuse harness dataclasses, `@st.cache_data` | No duplicate models, fast reloads |
| Charts | Plotly with reusable functions | Interactive + static export via kaleido |
| Export | PNG/SVG to `docs/report/figures/` | Publication-ready for Typst report |
| Run model | Single run (latest results) | Simplest; re-run overwrites |
| New deps | `streamlit`, `plotly`, `kaleido` | Minimal additions under `[dashboard]` extra |

## Directory Structure

```
src/desmet/dashboard/
├── app.py              # Entry point, st.navigation setup
├── data.py             # Load/save evaluation_results.json, story/platform metadata
├── charts.py           # Reusable Plotly chart builder functions
├── export.py           # PNG/SVG export helpers (kaleido)
└── pages/
    ├── 01_overview.py      # Platform rankings, radar chart, completion rates
    ├── 02_scoring.py       # Rubric forms for manual scoring
    ├── 03_comparison.py    # Cross-platform dimension charts
    ├── 04_story_detail.py  # Per-story drill-down + traces
    └── 05_export.py        # Batch export charts for report
```

## Data Layer (`data.py`)

### Responsibilities
- Load `results/evaluation_results.json` into existing harness dataclasses (`EvaluationMetrics`, `StoryMetrics`, `DimensionScore`)
- Load `config/platforms.yaml` for platform metadata (names, categories)
- Load story definitions from `data/stories/` via existing `desmet.harness.loader`
- Load trace files from `results/logs/{platform}/{story}/`
- Write scores back to `evaluation_results.json` in place
- Cached with `@st.cache_data`, manual reload button

### No new data models
The dashboard consumes what the harness already produces. Scores are written back to the same `StoryMetrics` and `DimensionScore` fields that are currently 0.

## Pages

### 01 — Overview
- Platform ranking table sorted by overall score (1-5)
- Completion rate bar per platform
- Radar chart: all 7 DESMET dimensions overlaid for all evaluated platforms
- Colour-coded by platform category
- At-a-glance: which platforms are scored vs pending

### 02 — Scoring
- Sidebar: select platform + story
- Displays execution evidence: wall clock time, iterations, tool calls, tokens, acceptance criteria results
- Shows generated code (from workspace artifacts) and trace timeline
- Rubric form: 0-3 sliders for each scoring dimension (correctness, completeness, code_quality, test_quality, time_efficiency, autonomy)
- Text area for qualitative notes per dimension
- Submit button writes scores back to JSON
- Progress tracker: "LangGraph: 3/4 stories scored"

### 03 — Comparison
- Side-by-side platform comparison (select 2-4 platforms)
- Per-dimension bar charts across selected platforms
- Story-level comparison table: same story, different platforms
- Efficiency breakdown: tokens, time, iterations as grouped bars
- Category averages: multi-agent vs SDK vs visual

### 04 — Story Detail
- Select a story, see how all platforms performed
- Acceptance criteria pass/fail matrix (platforms as columns, criteria as rows)
- Trace viewer: tool call timeline, message sequence
- Generated code diff viewer (if git_diff available)

### 05 — Export
- List all available charts with preview thumbnails
- Checkboxes to select which to export
- Format toggle: PNG or SVG
- Dimension presets: A4 full-width (160mm), A4 half-width (75mm), custom
- Exports to `docs/report/figures/` with consistent naming

## Charts (`charts.py`)

### Chart Types
| Function | Type | Used On |
|----------|------|---------|
| `radar_dimensions()` | Radar | Overview, Comparison |
| `bar_platform_rankings()` | Horizontal bar | Overview |
| `bar_story_comparison()` | Grouped bar | Comparison, Story Detail |
| `bar_efficiency_breakdown()` | Grouped bar | Comparison |
| `heatmap_criteria()` | Heatmap | Story Detail |
| `timeline_tool_calls()` | Timeline/Gantt | Story Detail |
| `bar_completion_rates()` | Bar | Overview |

### Colour Scheme
Fixed per platform category, shades within category:
- **Multi-agent** (LangGraph, CrewAI, AutoGen): blues
- **SDK** (OpenAI Agents SDK, Google ADK, Semantic Kernel): greens
- **Visual** (Flowise, LangFlow, Dify, n8n): oranges

Defined once in `PLATFORM_COLOURS` dict.

### Report-Ready Styling
- White background, minimal gridlines
- 14pt labels, 12pt ticks
- Default figure size: 800x500px
- No Plotly toolbar in exported images

## Export Pipeline (`export.py`)

- `export_figure(fig, name, fmt, width, height, output_dir)` wraps `fig.write_image()`
- Default output: `docs/report/figures/`
- Naming: `{chart_type}_{context}.{fmt}` (e.g. `radar_all_platforms.svg`)
- Requires `kaleido>=0.2.1`

## Dependencies

Added to `pyproject.toml` under `[project.optional-dependencies]`:

```toml
dashboard = [
    "streamlit>=1.30.0",
    "plotly>=5.18.0",
    "kaleido>=0.2.1",
]
```

## Launch Command

```bash
streamlit run src/desmet/dashboard/app.py
```

Or via CLI extension:
```bash
desmet-eval dashboard
```
