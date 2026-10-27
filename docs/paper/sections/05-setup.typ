= Evaluation Setup <sec-setup>

== Platforms

The validation covers the five programmatic platforms in @tab-platforms: three multi-agent frameworks and two agent SDK runtimes. Adapters for three visual platforms (Flowise, LangFlow, n8n) are implemented to the point of building flows from the live component catalogue and authenticating, but end-to-end runs against them are outstanding; Dify is integrated only partially because, since v1.0, its LLM providers ship solely as marketplace plugins that resist unattended installation. Library versions are those pinned in the project lockfile at the time of the reported runs.

#figure(
  table(
    columns: (1.25fr, 0.85fr, 1.9fr, 0.75fr),
    align: left,
    stroke: 0.4pt,
    inset: 3.5pt,
    table.header([*Platform*], [*Category*], [*Orchestration primitive used*], [*Version*]),
    [LangGraph], [Multi-agent], [Three-node `StateGraph` with checkpointing; reviewer→executor conditional edge], [1.1.7],
    [CrewAI], [Multi-agent], [Sequential `Crew` of role agents; `check_completion` termination tool], [1.6.1],
    [Microsoft Agent Framework], [Multi-agent], [Magentic manager-driven team; 4 rounds, 2 stalls], [1.0.1],
    [OpenAI Agents SDK], [SDK runtime], [Three-agent handoff chain; reviewer output guardrail], [0.4.2],
    [Google ADK], [SDK runtime], [`SequentialAgent` → `LoopAgent` (executor, reviewer); `exit_loop`], [1.16.0],
  ),
  caption: [Platforms under evaluation and the native orchestration each adapter's `_run_agent` uses. Versions are the lockfile pins of April 2026.],
) <tab-platforms>

== Scenario

The reported runs use the basic scenario US-001, _Add email validation utility function_: a single-file task (`utils/validation.py`) with four acceptance criteria (correct signature and type hints; valid inputs accepted; invalid inputs rejected; edge cases handled), expressed as a user story, a prompt template, and a Gherkin feature file. It is deliberately minimal so that pipeline failures can be attributed to the framework rather than to task difficulty; every platform must nonetheless drive all four stages, including rendering a Mermaid diagram, running the test suite, and deploying to the remote host. Three further scenarios of intermediate and advanced complexity (an API endpoint, a full-stack feature, an authentication system) are defined and executable but not reported here. Acceptance-criteria coverage is treated as a control variable rather than a score: with one model throughout, similar coverage is expected and divergence would itself indicate a framework issue.

== Models, budgets, and runs

The baseline uses `gpt-4.1-mini` at temperature~0 on every platform. A cross-model pass repeats the scenario with `claude-sonnet-4.6` (routed through each platform's provider integration) to check that framework-level patterns survive a change of model and provider. Budgets are 300~s wall-clock, 100,000 tokens, \$0.50, and 50 iterations per scenario. Stage~4 deploys over SSH to a dedicated host on a per-run branch and probes the service with a health check.

Each (platform, scenario, model) cell is a single execution ($n = 1$); the study is descriptive and comparative, not inferential, and no hypothesis tests are reported. The reported run per platform is its complete end-to-end execution; runs aborted part-way during adapter development are excluded. All five baseline platforms were run on one day except Google ADK, whose reported run is from two days earlier; all five Sonnet rows come from one run. Run identifiers are listed in the data-availability statement.
