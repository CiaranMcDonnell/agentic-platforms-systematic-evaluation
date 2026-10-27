= Evaluation Framework <sec-framework>

The evaluation follows DESMET's hybrid of _benchmarking_ (a standard task run on every platform) and _qualitative screening_ (feature assessment where benchmarks cannot reach) @kitchenham1997desmet. The wider study from which this paper is drawn applies three layers---industry readiness, platform characteristics, and pipeline benchmarking---to nine platforms; this paper concerns only the third layer and the harness that implements it.

== Framework-centric stance

The central design decision is to measure the *framework*, not the model. Every platform receives the same model at the same temperature, the same prompt templates, the same tool set, and the same scoring, so that any difference in outcome is attributable to how the platform orchestrates the model rather than to what the model knows. Stage outputs (requirements, code, tests, build logs) are retained as evidence but are not scored for quality; the metrics capture pipeline completion, tool-call reliability, error recovery, trace fidelity, and resource cost. This separation is imperfect---platforms also differ in how they construct system prompts and replay history---and @sec-threats returns to it.

== The four-stage pipeline

Rather than isolated tasks, each platform receives a scenario and drives it through the four stages of @tab-stages, mirroring how a practitioner would use the platform. Design (UML in Mermaid) is folded into the first stage, following Broccia et~al. @broccia2025humainflow. Each stage's output is the next stage's input, so a failure propagates rather than being masked.

#figure(
  table(
    columns: (0.9fr, 0.9fr, 1.3fr, 1.3fr),
    align: left,
    stroke: 0.4pt,
    inset: 3.5pt,
    table.header([*Stage*], [*Input*], [*Output*], [*Key metrics*]),
    [1 Requirements \& design], [Scenario (YAML)], [Structured requirements, acceptance criteria, Mermaid UML], [Completion, parseable UML, tool calls, tokens, time],
    [2 Code generation], [Requirements + UML], [Source files in an isolated workspace], [Completion, files produced, tool reliability, tokens, time],
    [3 Test generation], [Requirements + source], [Test suite; runner invoked], [Completion, test-runner invocation, tokens, time],
    [4 Build \& deploy], [Source + tests], [Pushed branch, restarted service, health check], [Build/deploy success, error recovery, tokens, time],
  ),
  caption: [The four-stage software engineering pipeline every platform executes.],
) <tab-stages>

== Rubric and cross-cutting scores

Each (platform, scenario) run is scored on six framework-centric dimensions using a 0--3 ordinal rubric rather than a 1--5 Likert scale: DESMET recommends coarser scales when a single evaluator cannot cross-validate judgements @kitchenham1997desmet @taherdoost2019likert. The six scores aggregate into four cross-cutting 1--5 scores (@tab-rubric). Three of the four are derived automatically from trace signals; _Autonomy_ remains a manual judgement because deciding whether an intervention was substantive requires reading the trace. Budgets are fixed per scenario---300~s wall-clock, 100,000 tokens, and \$0.50---and _Efficiency_ is the mean of components of the form $max(1, 5 - 2(r - 1))$, where $r$ is the ratio of consumption to budget.

#figure(
  table(
    columns: (1fr, 2.1fr, 0.65fr, 1.05fr),
    align: left,
    stroke: 0.4pt,
    inset: 3.5pt,
    table.header([*Dimension (0--3)*], [*What it measures*], [*Source*], [*Aggregates into*]),
    [Pipeline completeness], [Stages completed end-to-end without manual bridging], [Auto], [Pipeline Completeness],
    [Tool integration], [Tool-call reliability and argument-schema correctness], [Auto-init], [Orchestration],
    [Error recovery], [Detection, diagnosis and retry on tool or build failures], [Auto-init], [Orchestration],
    [Trace quality], [Completeness of the trace: messages, tool calls, tokens, timing, state], [Auto-init], [Orchestration],
    [Time efficiency], [Wall-clock and token cost relative to budget], [Auto], [Efficiency],
    [Autonomy], [Inverse of human interventions required], [Manual], [Autonomy],
  ),
  caption: [Six rubric dimensions and the four cross-cutting scores they feed. _Auto_: fully derived from harness signals. _Auto-init_: seeded from the trace, confirmed or adjusted by the evaluator. _Manual_: assigned by the evaluator.],
) <tab-rubric>

== Framework metrics

Alongside the rubric, every stage records token usage (input and output), estimated API cost from provider price tables, wall-clock time, iteration count, tool-call count, and peak memory. Four derived signals are computed from the trace. The *iteration ratio* is iterations over the scenario's iteration budget. *First-action latency* is the time from stage start to the first tool call. *Framework overhead* is wall-clock time minus the summed duration of LLM calls, i.e. the time the framework spends outside the model. The *redundant-tool-call rate* (rtc), introduced by this work, is the fraction of calls to idempotent inspection tools (`read_file`, `list_directory`, `search_code`) within a stage whose tool name and argument set exactly repeat an earlier call. A platform that converges on a stage scores rtc~=~0; a platform whose retry policy re-reads the same files on every round scores higher, and we show in @sec-results that rtc isolates a class of orchestration pathology that is otherwise visible only in aggregate token totals. Tool integration is scored as $3 dot (0.7(1 - f) + 0.3(1 - "rtc"))$ where $f$ is the tool-failure rate, so dispatch failures weigh more heavily than wasted dispatch.
