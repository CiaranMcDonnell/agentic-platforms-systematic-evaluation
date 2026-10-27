= Results <sec-results>

== Baseline: five platforms, one model, one task

All five platforms completed all four stages of US-001 under `gpt-4.1-mini`, and no platform produced meaningfully different source artefacts; the divergence is entirely framework-level orchestration behaviour (@tab-results). Token cost spans roughly 2.4× between the two multi-agent/SDK incumbents at the extremes---OpenAI Agents SDK at 100,383 tokens, \$0.047 and 3.4~min against Microsoft Agent Framework at 239,801 tokens, \$0.105 and 6.2~min---with Google ADK below the SDK-runtime floor at 56,764 tokens. Wall-clock does not track token count, and peak memory varies 5.3× (236~MB for LangGraph to 1,242~MB for CrewAI), driven by each runtime's in-process session store.

#figure(
  scope: "parent",
  placement: top,
  table(
    columns: (1.6fr, 0.55fr, 0.75fr, 0.6fr, 0.7fr, 0.45fr, 0.5fr, 0.5fr, 0.5fr, 0.5fr, 0.55fr),
    align: (left, right, right, right, right, right, right, right, right, right, right),
    stroke: 0.4pt,
    inset: 3.5pt,
    table.header(
      [*Platform*], [*Wall*], [*Tokens*], [*Cost*], [*Peak mem*], [*rtc*],
      [*PC*], [*Eff.*], [*Orch.*], [*Aut.*], [*Overall*],
    ),
    [OpenAI Agents SDK], [*3.4~m*], [100,383], [\$0.047], [491~MB], [0.00], [5.00], [*5.00*], [*4.44*], [5.00], [*4.86*],
    [Google ADK], [4.9~m], [*56,764*], [*\$0.026*], [871~MB], [0.00], [5.00], [4.69], [*4.44*], [5.00], [4.78],
    [LangGraph], [4.0~m], [190,309], [\$0.088], [*236~MB*], [0.06], [5.00], [4.55], [4.41], [5.00], [4.74],
    [Microsoft Agent Framework], [6.2~m], [239,801], [\$0.105], [278~MB], [0.00], [5.00], [4.18], [*4.44*], [5.00], [4.66],
    [CrewAI], [5.3~m], [103,776], [\$0.051], [1,242~MB], [0.33], [5.00], [4.24], [4.28], [5.00], [4.63],
  ),
  caption: [US-001 under `gpt-4.1-mini`: resource consumption, redundant-tool-call rate (rtc, mean over stages), and the four cross-cutting scores (1--5) with their mean. Best value per numeric column in bold; lower is better for wall-clock, tokens, cost, and memory.],
) <tab-results>

*OpenAI Agents SDK* sets the efficiency baseline. Native function calling and a trimmed conversation history keep accumulated context from dominating later turns, and no stage recorded a redundant call (rtc~=~0.00 throughout). *Google ADK* records the lowest absolute token count and cost; its `SequentialAgent`/`LoopAgent` composition keeps iterations modest (41 iterations over 24 tool calls) and rtc at zero on every stage, but its wall-clock and iteration ratios pull its _Efficiency_ to 4.69. ADK also showed run-to-run variability on the Testing stage in repeated development passes (an intermittent JSON-parse regression); the reported run is a representative clean one. *LangGraph* completes in 4.0~min at 190,309 tokens, but the cost is concentrated: the Testing stage alone consumed roughly 151k tokens over 23 tool calls, reflecting heavier test-fixture generation rather than history replay, since the supervisor-checkpoint architecture bounds each stage to three supervisor rounds regardless of tool-call count. *CrewAI* sits within 4% of the SDK-runtime cost floor at 103,776 tokens, after two adapter changes---the `check_completion` termination tool and restored native function calling for OpenAI-compatible providers---but the Crew pattern preserves the full inter-agent message log across planner, developer, QA and reviewer handoffs and produces the highest rtc in the dataset (0.33). *Microsoft Agent Framework* carries the largest cost: the Magentic manager can continue to cycle executor and reviewer after real work has ended, resubmitting accumulated history; the Deploy stage, which hit the round cap, accounted for roughly 87k tokens on its own. The four-round, two-stall cap bounds the worst case rather than fixing the underlying completion semantics.

_Pipeline Completeness_ and _Autonomy_ saturate at 5.00 for every platform: all runs completed all stages with zero logged interventions. On a basic task the discriminating scores are _Efficiency_ (5.00 down to 4.18) and _Orchestration_ (clustered at 4.28--4.44, with CrewAI lowest because its rtc weighs on the tool-integration component).

== Cross-model pass

Re-running US-001 under `claude-sonnet-4.6` confirmed the framework-level ordering and exposed faults the baseline does not. LangGraph again finished every stage in three supervisor iterations (49 tool calls, 209,130 tokens) with rtc~=~0 on every stage. OpenAI Agents SDK remained the lowest-cost completion (111,442 tokens) with zero redundancy. CrewAI dominated the cost profile (538,715 tokens over three completed stages, after a Requirements-stage task timeout) with rtc rising to 0.40 on the completed stages. The ordering OpenAI SDK $<$ LangGraph $<$ CrewAI held under model swap.

Four issues surfaced only under the second model. (1)~CrewAI's internal task-level timeout fired on the Requirements prompt, which completes comfortably under the baseline model; a configuration fault, visible only under a slower-responding provider. (2)~Google ADK's Testing and Deploy stages aborted with a provider rate-limit error raised through its LiteLLM routing to Anthropic, after Requirements and Code Generation completed (103,256 and 25,348 tokens). (3)~Microsoft Agent Framework failed every stage immediately through its OpenAI-compatible chat client with zero tool calls. (4)~That MAF run is also the case that motivated the productive-tool-call guard of @sec-harness: without it, the Code Generation and Testing stages would have reported success because baseline artefacts from earlier stages satisfied a file-presence check.

#figure(
  table(
    columns: (1.5fr, 0.9fr, 0.75fr, 1.5fr),
    align: (left, center, center, left),
    stroke: 0.4pt,
    inset: 3.5pt,
    table.header([*Platform*], [*Stage delta*], [*Token amp.*], [*New error class*]),
    [OpenAI Agents SDK], [0], [1.11×], [---],
    [LangGraph], [0], [1.10×], [---],
    [Google ADK], [+2], [n/a], [provider rate-limit],
    [CrewAI], [+1], [*5.19×*], [task timeout],
    [Microsoft Agent Framework], [+4], [n/a], [provider-routing failure],
  ),
  caption: [Model sensitivity on US-001 between `gpt-4.1-mini` and `claude-sonnet-4.6`. Stage delta: stages passing under the baseline minus stages passing under Sonnet. Token amplification is computed on successfully completed work only; n/a where provider errors truncated the comparable work.],
) <tab-sensitivity>

@tab-sensitivity isolates a signal available from neither run alone: how much each framework amplifies model-level variance. LangGraph and OpenAI Agents SDK are effectively model-invariant on this task (zero stage delta, ≈1.1× tokens, no new error class). CrewAI amplifies by 5.19×, far above the floor a slightly more verbose model would produce, consistent with full-history replay compounding per-turn verbosity non-linearly. The ADK and MAF rows reflect provider- rather than framework-level faults and do not support a framework fragility claim.

== Findings

*F1. Conversation-history policy, not architectural category or agent count, is the finer-grained predictor of cost.* Three replay strategies are visible: LangGraph's bounded supervisor checkpoints (per-iteration cost roughly constant), OpenAI SDK's trimmed history, and the Magentic manager's full-cycle accumulation when completion detection misfires; CrewAI's full inter-agent log preservation is in the accumulating family. The spread inside the multi-agent category (CrewAI 104k to MAF 240k) is as wide as the gap between the two SDK runtimes, so category-level guidance is too coarse. (RQ2)

*F2. rtc is a reliable stage-level indicator of orchestration pathology.* It separates platforms that converge on a stage (OpenAI SDK, ADK, MAF at 0.00) from those whose retry policy absorbs loop-defence warnings (CrewAI at 0.33; LangGraph at 0.06 from a single code-generation retry), and stages with elevated rtc correspond one-to-one with stages that triggered the harness loop guard. Prior framework evaluations @yin2025comprehensive @mehta2025clear report task success without instrumenting intra-stage retry. (RQ1)

*F3. Token cost on identical work spans ≈2.4×.* With the same model and task, framework choice alone moves inference cost by a factor that would dominate most model-choice differences. Because several adapter fixes narrowed this spread before the reported runs, 2.4× is a conservative bound on what an unhardened integration shows. (RQ2)

*F4. No single (model, provider) run surfaces all framework fragilities.* The Sonnet pass exposed three distinct fault classes invisible under the baseline; an evaluation on one backend @derouiche2025agentic cannot detect them. The harness makes the comparison cheap enough to repeat. (RQ1)

*F5. Frameworks differ in how much they amplify model-level variance.* ≈1.1× for LangGraph and OpenAI SDK against ≈5.2× for CrewAI on identical work; with two model conditions this is descriptive, and promoting it to a scored _Model Robustness_ dimension needs at least three. (RQ2)

*F6. File-presence validation is insufficient as a success signal.* The productive-tool-call guard demoted four zero-work stages in the MAF Sonnet run and an intermittent ADK Testing-stage abort after a single read; a narrower zero-tool-call check would miss the latter. (RQ1)
