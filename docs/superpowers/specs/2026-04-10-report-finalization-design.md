# Report Finalization & WebUI Integration — Design Spec

## Goal

Complete all remaining TODO sections in the DESMET academic report (Typst, `docs/report/`) and elevate the web-based management console as a primary contribution throughout. The report should be structurally complete after Pass 1, with clearly marked placeholders only for results-dependent content filled in Pass 2.

## Approach

**Two-pass, infrastructure-first strategy:**

- **Pass 1** — Write everything derivable from the codebase and existing design (no evaluation data needed)
- **Pass 2** — Fill results tables, discussion, and final cross-references once evaluations are complete

## File Map

All work targets files under `docs/report/chapters/`. No new chapter files are created — all changes are edits to existing `.typ` files.

| File | Sections affected |
|------|-------------------|
| `implementation.typ` | §4.2 (adapters), §4.3 (stages 1-3), §4.5 (metrics), §4.6 (webui), §4.7 (challenges) |
| `evaluation-method.typ` | §5.1.1 (story rationale), §5.1.2 (story defs), §5.2.1 (data flow), §5.3 (webui as instrument), §5.4 (ethics) |
| `limitations.typ` | §7.1 (limitations), §7.2.1 (internal), §7.2.2 (external), §7.2.3 (construct) |
| `conclusions.typ` | §8.1 (contributions), §8.2 (findings skeleton), §8.3 (goals skeleton), §8.4 (future work) |
| `evaluation.typ` | §6.1-6.5 (all — Pass 2 only) |
| `introduction.typ` | §1.4 findings preview (Pass 2 only) |

`data-considerations.typ` is an abandoned draft — ignore it, `evaluation-method.typ` is canonical.

---

## Pass 1: Write from Code (no evaluation data needed)

### 1.1 — WebUI as Primary Contribution (implementation.typ §4.6)

**Current state:** Single paragraph mentioning FastAPI + Svelte + port 8042.

**Target:** 2-3 page section establishing the webui as a reusable evaluation instrument.

**Content:**

1. **Architecture overview**
   - FastAPI backend serving REST + WebSocket endpoints
   - Svelte 5 SPA frontend with reactive state management
   - Served on port 8042 via `desmet` CLI
   - ~45 API endpoints (platforms, runs, scoring, charts, traces, infrastructure)

2. **Manage pages (5 pages)**
   - *Dashboard:* Infrastructure health cards, LLM provider discovery (live model enumeration per provider), recent runs summary, platform/story counts
   - *Platforms:* Adapter implementation status, Docker container control (start/stop), per-platform readiness indicators
   - *Stories:* YAML-driven story browser with difficulty filtering, acceptance criteria preview
   - *New Run:* Platform + story selector, run configuration, launch with immediate redirect to live view
   - *Run Detail:* Live log streaming via WebSocket, per-stage progress tracking, cancel support, status badge updates

3. **Results pages (4 pages)**
   - *Results Overview:* Completion rate bar charts, dimension bar charts, efficiency breakdowns (ECharts)
   - *Scoring:* Interactive rubric panel — per-dimension 0-3 scoring with notes, integrated trace viewer (Langfuse + LangSmith tabs), agent graph tab, side-by-side scoring with evidence. This operationalizes the rubric from §3.5.
   - *Story Detail:* Per-story cross-platform comparison with navigable "Score this" links to Scoring page
   - *Comparison:* Radar charts (4 dimensions x N platforms), platform rankings, score matrix heatmap

4. **Agent Graph visualization** (novel component)
   - ELK-layouted directed graph showing agent communication topology
   - Built from Langfuse trace data — extracts agent nodes and message edges from observation tree
   - Cluster nodes for multi-agent containers (e.g., CrewAI crews, MagenticOne teams)
   - Observation drill-down drawer for inspecting individual LLM calls
   - Timeline cards showing execution sequence
   - Custom Svelte components: `AgentNode`, `AgentClusterNode`, `ObservationNode`, `TransitionEdge`, `TimelineCard`, `ObservationDrawer`
   - Uses `@xyflow/svelte` for graph rendering
   - Academically significant: makes multi-agent orchestration patterns *visible*, enabling informed qualitative scoring

5. **Observability integration**
   - Langfuse trace viewer: hierarchical span tree with token counts, timing, input/output inspection
   - LangSmith trace viewer: run tree rendering for LangGraph-specific traces
   - Dual-provider support — evaluator can cross-reference traces from both systems

6. **Infrastructure management**
   - Docker Compose control for Langfuse (core dependency) and visual platform services
   - Service health polling with status badges
   - Container image build/rebuild via WebSocket-streamed build logs

**Contribution argument (weave into prose):** The webui is not a convenience wrapper — it is the evaluation instrument. The scoring panel operationalizes the rubric, the agent graph reveals orchestration patterns that inform qualitative scoring, and the comparison page directly produces the cross-platform analysis. This makes the evaluation *reproducible* and *extensible*: a future evaluator can add a platform adapter and immediately use the full scoring/comparison infrastructure without building their own tooling.

### 1.2 — Pipeline Stage Implementation (implementation.typ §4.3)

**Current state:** Stages 1-3 are empty TODOs. Stage 4 (deploy) is complete.

**Content per stage (~half page each):**

- **Stage 1 (Requirements & Design):**
  - Story YAML loading via `StoryLoader` → `StageContext`
  - Structured planner: `ImplementationPlan` Pydantic model with JSON-parse fallback
  - Enriched executor prompt: `## Plan` section + `## Files` inventory
  - PlantUML generation via `generate_uml` tool call
  - Output: structured requirements JSON + PlantUML diagram string

- **Stage 2 (Code Generation):**
  - Input: requirements + UML from Stage 1 chained via `StageContext`
  - File writing via `write_file` tool into workspace directory
  - Workspace isolation: each platform-story combo gets a clean directory
  - The `_execute_stage` template method handles tool dispatch, retry, and result building

- **Stage 3 (Test Generation):**
  - Input: requirements + generated code from Stage 2
  - `run_tests` tool for pytest/jest invocation
  - Error-recovery loop: failing tests trigger re-generation and re-run
  - Asymmetric tool distribution: reviewer agent gets inspection-only tools (read_file, list_files) — cannot modify code
  - Coverage tool integration via `run_tests` output parsing

Reference shared infrastructure from §4.4 (`ToolAgentAdapter` template-method pattern) — don't repeat it.

### 1.3 — Metrics Collection & Technical Challenges (implementation.typ §4.5, §4.7)

**Metrics Collection (§4.5, ~half page):**
- Token tracking: `_execute_stage` wrapper captures input/output tokens from provider-specific usage objects (OpenAI `usage`, CrewAI `UsageMetrics`)
- Wall-clock timing: context managers in `runner.py` around each stage invocation
- Cost estimation: provider pricing lookup from token counts
- `ResultStore`: DuckDB-backed persistence (`desmet.duckdb`) for structured result querying
- Cross-cutting dimension computation: formulas from §3.6 encoded in `harness/metrics.py`, producing 1-5 Likert scores

**Technical Challenges (§4.7, ~1 page):**
- *CrewAI cost tracking:* litellm dependency removed in CrewAI v1.6 broke token tracking; fixed via native `OpenAICompletion` + `BaseInterceptor` callback
- *CrewAI early termination:* 50-iteration token burn when agent couldn't signal completion; fixed via `check_completion` tool with `result_as_answer=True`
- *CrewAI native function calling:* broken for non-OpenAI providers, forced ReAct text-parsing workaround — still an open issue
- *Adapter parity:* achieving shared prompt structure (planner, executor, tool distribution) while preserving idiomatic patterns per framework (MagenticOne manager, OpenAI guardrails, LangGraph checkpointing, CrewAI sequential crews)
- *Deploy stage security:* restricted SSH user (`desmet`), whitelisted shell (git pull, docker compose, docker ps, curl only), Tailscale VPN — balancing realistic deployment with shared-server safety

### 1.4 — Adapter Implementation Details (implementation.typ §4.2)

**Current state:** Status table exists. TODO asks for per-adapter descriptions.

**Content (~1 paragraph per adapter, ~1.5 pages total):**

- **LangGraph:** Graph-based state machine with checkpointing. Nodes map to agent roles (planner, coder, reviewer). LangGraph's native state persistence enables conversation replay. Tool format: OpenAI-compatible function calling.
- **CrewAI:** Role-based sequential crews. Agents assigned explicit roles with backstories. `check_completion` tool controls iteration budget. Tool format: CrewAI `@tool` decorator wrapping shared tool functions.
- **OpenAI Agents SDK:** 3-agent handoff chain (planner → coder → reviewer). Structured output via Pydantic response models. Output guardrails for validation. Tool format: native OpenAI function definitions.
- **Google ADK:** `SequentialAgent` orchestrating specialist sub-agents + `LoopAgent` for iterative refinement. ADK's native tool format mapped to shared tool set. Tool format: ADK `FunctionTool`.
- **Microsoft Agent Framework:** MagenticOne manager-driven teams. Manager agent delegates tasks to specialist agents, aggregates results. Tool format: Agent Framework `KernelFunction`.

Focus on *what makes each idiomatically different* — the shared infrastructure (tool creation, prompt templates, validation, retry) is already in §4.4.

### 1.5 — Evaluation Method: Remaining TODOs (evaluation-method.typ)

**Story Selection Rationale (§5.1.1, ~1 paragraph):**
- Coverage of 3 complexity tiers (basic, intermediate, advanced)
- Each story exercises all 4 pipeline stages
- Range from single-file utility function to multi-component auth system
- Representative of real SE tasks practitioners encounter
- Sufficient differentiation to reveal capability gaps between platforms

**Story Definitions (§5.1.2, ~half page):**
- Annotated YAML example showing US001 schema structure
- Fill in acceptance criteria counts in summary table (read from `data/stories/` YAML files)

**Data format flow (§5.2.1, ~1 paragraph):**
- YAML stories → prompt templates → pipeline stages → JSON result artefacts
- Gherkin features as ground truth cross-reference for acceptance criteria coverage
- `StageResult` model: stage name, completion status, output artefacts, token usage, timing, tool call log

**WebUI as execution instrument (§5.3, ~2 sentences within Execution Methodology):**
- Evaluator uses New Run page to configure platform + story + model, launches run
- Monitors via live WebSocket log stream in Run Detail page
- Scores via Scoring panel with Langfuse/LangSmith trace evidence and agent graph visible alongside rubric dimensions

**Ethical Considerations (§5.4, ~half page):**
- No personal or sensitive data in user stories (all synthetic SE tasks)
- API cost transparency: estimated costs recorded per stage
- Open-source licensing of all evaluated platforms (MIT/Apache/fair-code)
- Reproducibility: all prompts, configurations, and results version-controlled in git
- Single-evaluator bias mitigated through structured rubrics with explicit criteria at each score level

### 1.6 — Limitations Chapter (limitations.typ)

**Limitations (§7.1, ~half page):**
- 4 user stories limits generalisability across the full range of SE tasks
- Single evaluator for all qualitative rubric scores
- Point-in-time snapshot — platform versions evolve rapidly (state evaluation date)
- 5 of 9 platforms benchmarked at Layer 3; visual platforms assessed at Layers 1-2 only
- LLM model choice (state which model) as a confound — results may differ with other models

**Internal Validity (§7.2.1, ~half page):**
- Single evaluator bias: mitigated by structured rubrics with explicit criteria at each score level
- Rubric subjectivity: borderline cases (e.g., 1 vs 2) require judgement despite criteria
- Prompt sensitivity: same prompts used across platforms, but platform-specific prompt handling may affect results
- Order effects: sequential platform evaluation — later evaluations benefit from evaluator learning
- LLM non-determinism: mitigated by recording all prompts, configurations, and outputs

**External Validity (§7.2.2, ~half page):**
- 4 stories may not represent broader SE task population
- Platform version sensitivity: findings are a snapshot, may not generalise to future versions
- LLM model dependency: single model used; results may not transfer to other models
- Category representativeness: 9 platforms across 3 categories — reasonable but not exhaustive

**Construct Validity (§7.2.3, ~half page):**
- Framework-centric metrics vs output quality: does platform prompt engineering affect quality in ways the metrics miss? Mitigated by using same model, but platform-specific system prompts and tool descriptions may influence output
- 0-3 rubric scale: trades measurement granularity for single-evaluator reliability; may obscure meaningful differences between scores 2 and 3
- Aggregation formula design: equal weighting across dimensions is a default choice; sensitivity analysis with alternative weightings recommended

### 1.7 — Conclusions Skeleton (conclusions.typ)

**Summary of Contributions (§8.1, ~1 page — fully writeable now):**

1. *Methodology contribution:* DESMET-based three-layer evaluation framework combining qualitative screening (industry readiness, platform characteristics) with pipeline benchmarking. Extends Broccia et al.'s visual-platform-only comparison to all three architectural categories.

2. *Empirical contribution:* Cross-platform comparison of 9 agentic platforms across multi-agent frameworks, SDK runtimes, and visual workflow platforms — a different and broader platform set than prior work (Yin et al., Derouiche et al.).

3. *Tooling contribution:* The `desmet` evaluation harness and web-based management console. Emphasize:
   - Template-method adapter pattern requiring one method to implement
   - WebUI as reusable evaluation instrument — scoring panel operationalizes rubric, agent graph visualization reveals orchestration patterns, comparison page produces cross-platform analysis
   - Extensible to future platforms without changes to runner, metrics, or UI
   - Open-source, version-controlled, reproducible

**Key Findings (§8.2, placeholder):**
Write template paragraph with bracketed placeholders:
> "The evaluation reveals that [cross-category patterns]. Across the benchmarked platforms, [completeness/autonomy finding]. [Orchestration finding]. [Efficiency finding]. These findings suggest [practical implication for practitioners]."

Mark with `// RESULTS-DEPENDENT: fill after evaluations`.

**Goals Achieved (§8.3, ~half page skeleton):**
List the 5 aims from §1.3. For each, write the framework ("Aim N was to..."). Leave verdict (fully met / partially met / not met) as placeholder.

**Future Work (§8.4, ~half page — fully writeable now):**
- Multi-evaluator studies: multiple scorers for inter-rater reliability (Cohen's kappa)
- Adapter coverage extension: implement visual platform adapters (Flowise, LangFlow, Dify, N8n) for full Layer 3 coverage
- Longitudinal evaluation: track platform evolution across versions
- Additional pipeline stages: debugging, refactoring, code review
- Community-contributed adapters: reference the extension guide (§4.4 + Appendix)
- Alternative LLM models: repeat evaluation with different models to test model-independence claim

---

## Pass 2: Results-Dependent (after evaluations)

### 2.1 — Layer 1 & 2 Results (evaluation.typ §6.1, §6.2)

Fill Industry Readiness table (9 platforms x 6 criteria) from desk research + GitHub API data. Fill System-level and Interaction-level feature matrices from documentation review and hands-on verification. Write brief narrative per platform.

**Note:** This can overlap with Pass 1 — doesn't require pipeline runs, only desk research.

### 2.2 — Layer 3 Results (evaluation.typ §6.3)

Fill capability overview table, per-story result tables (US001-US020), cross-cutting dimension scores table, resource consumption analysis. All data comes from completed evaluation runs scored via the webui Scoring panel.

### 2.3 — Discussion (evaluation.typ §6.4)

Write Key Findings, Cross-Category Patterns, and Complexity Scaling subsections. Synthesize data from 2.1 and 2.2 to answer the three research questions (RQ1-RQ3).

### 2.4 — Finalization Pass

- Fill Introduction §1.4 findings preview paragraph (currently TODO)
- Complete Conclusions §8.2 key findings
- Fill Conclusions §8.3 goals-achieved verdicts
- Write Acknowledgements
- Final consistency check: cross-references, figure numbering, citation completeness

---

## Estimated Scope

| Pass | Items | Est. pages | Blocked by |
|------|-------|-----------|------------|
| Pass 1 | 1.1-1.7 | 12-15 | Nothing (ready now) |
| Pass 2 | 2.1-2.4 | 10-15 | Evaluation runs + scoring |

**WebUI surfaces in:**
- Implementation §4.6 (2-3 pages, primary treatment)
- Evaluation Method §5.3 (scoring workflow reference)
- Conclusions §8.1 (primary contribution)
- Introduction §1.4 (already mentioned, no change needed)

## Out of Scope

- Creating new chapter files
- Changing the report structure or chapter ordering
- Writing actual evaluation results (Pass 2 depends on running evaluations)
- Modifying the webui code
- Changing the scoring rubric or dimension formulas
