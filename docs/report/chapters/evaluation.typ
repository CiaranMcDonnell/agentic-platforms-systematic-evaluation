#import "../template.typ": *

= Results <evaluation>

== Layer 1 Results: Industry Readiness

Layer~1 profiles were compiled in April~2026 from each platform's GitHub repository, official documentation, release notes, and published customer lists. @tab-layer1 summarises the nine platforms against the six criteria defined in @appendix-scoring-rubric.

#figure(
  table(
    columns: (2.1fr, 1.05fr, 1fr, 1fr, 0.8fr, 1fr, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: (left, center, center, center, center, center, center),
    table.header(
      [*Platform*], [*Release \ Maturity*], [*Mainten-\ ance*], [*Commu-\ nity*], [*Docs*], [*Adop-\ tion*], [*Licens-\ ing*],
    ),
    [LangGraph], partial-cell, yes-cell, yes-cell, yes-cell, yes-cell, yes-cell,
    [CrewAI], yes-cell, yes-cell, yes-cell, yes-cell, yes-cell, yes-cell,
    [OpenAI Agents SDK], no-cell, yes-cell, yes-cell, yes-cell, yes-cell, yes-cell,
    [Google ADK], yes-cell, yes-cell, partial-cell, yes-cell, partial-cell, yes-cell,
    [Microsoft Agent Framework], yes-cell, yes-cell, partial-cell, yes-cell, partial-cell, yes-cell,
    [Flowise], yes-cell, yes-cell, yes-cell, yes-cell, partial-cell, yes-cell,
    [LangFlow], yes-cell, yes-cell, yes-cell, yes-cell, yes-cell, yes-cell,
    [Dify], yes-cell, yes-cell, yes-cell, yes-cell, yes-cell, partial-cell,
    [n8n], yes-cell, yes-cell, yes-cell, yes-cell, yes-cell, partial-cell,
  ),
  caption: [Layer 1: Industry Readiness Profiles (Yes / Partial / No)],
) <tab-layer1>

*Release maturity is the cleanest differentiator.* Seven of the nine platforms have crossed a stable 1.0 release: CrewAI (v1.14.2), LangFlow (v1.9.0), n8n (v2.17.3), Dify (v1.13.3), Flowise (v3.1.2), Google ADK (v1.31.1 on Python and v1.0 on Java), and Microsoft Agent Framework (python-1.1.0, promoted from release-candidate to 1.0 GA in early April~2026 as the unified successor to AutoGen and Semantic Kernel). LangGraph scores *Partial* because, although a v1.0 LTS line shipped in October~2025 (current release v1.1.9), the v0.x line is still supported through December~2026 and a substantial fraction of public tutorials continue to target the pre-v1 API. OpenAI Agents SDK scores *No* because it remains at v0.14.3 with the API still evolving around the Responses-API and AgentKit integration; pre-1.0 status is explicit in the project metadata.

*Maintenance is uniformly strong.* Every platform shipped a release within the month preceding the snapshot date. LangGraph (503 releases to date), CrewAI (177 releases), and n8n (583 releases; ~19~000 commits on `master`) indicate weekly release cadences; Microsoft Agent Framework has shipped 73 releases in the six months since preview; even the younger ADK averages a release every two weeks.

*Community scale splits along accessibility lines.* The three no-code visual platforms command the largest audiences---n8n (~185~k stars), LangFlow (~147~k), and Dify (~139~k) are among the most-starred open-source AI repositories on GitHub---and have long-running Discord communities and template marketplaces to match. CrewAI (49.4~k), Flowise (52.1~k), LangGraph (29.9~k), and OpenAI Agents SDK (24.3~k) all clear the 20~k threshold and have established developer communities. Google~ADK (19.2~k) and Microsoft Agent Framework (9.7~k) score *Partial* purely because the absolute star count is below the visual platforms', not because activity is low---MAF inherits the AutoGen and Semantic Kernel communities but the unified repository is only six months old.

*Documentation is a uniform strength across all nine platforms.* Each maintains a dedicated documentation site with tutorials, API reference, and worked examples; LangChain Academy, the CrewAI learn portal, and the ADK codelabs additionally provide structured teaching material. This is the one criterion on which no platform falls short---consistent with Broccia et~al. @broccia2025humainflow, who reported documentation as the most-improved dimension across the visual-platform segment since 2023.

*Adoption is well-attested for the established platforms and still building for the two newest.* LangGraph (Klarna, LinkedIn, Uber, Replit), CrewAI (PwC, Piracanjuba, ~2 billion agent executions in the trailing 12~months), OpenAI Agents SDK (Klarna, Clay, Canva, Coinbase), LangFlow (inheriting the DataStax enterprise portfolio---FedEx, Capital One, Home~Depot, Verizon---through its IBM parent following IBM's February~2025 announcement of the DataStax acquisition), Dify (2000+ commercial teams including Maersk, Novartis, RICOH, Panasonic, Deloitte, NTT), and n8n (3000+ enterprise customers including Microsoft and KPMG) all publish named customer lists or case studies.

Flowise is rated *Partial* because its adoption is concentrated among agencies and SMBs with fewer published Fortune-500 references. Google~ADK (Renault, Box, Revionics) and Microsoft Agent Framework both rate *Partial* for a common reason: strong vendor backing and clear enterprise positioning, but a narrower set of post-release case studies than the older frameworks.

*Licensing is the sharpest fault line for downstream commercial use.* Seven platforms ship under permissive MIT or Apache-2.0 licences that permit any form of use, modification, or resale. The two most commercially successful visual platforms adopt source-available models instead: n8n's Sustainable Use License permits internal and personal use but restricts re-hosting the platform as a commercial service, and Dify's Open Source License extends Apache-2.0 with prohibitions on multi-tenant SaaS resale and logo removal. Both score *Partial*. For a practitioner choosing a platform to embed in a commercial product---the implicit viewpoint of the framework---this distinction is load-bearing and is carried forward into the Discussion.

== Layer 2 Results: Platform Characteristics

Layer~2 maps what each platform _can_ do, assessed through documentation review and hands-on verification against the criteria defined in @appendix-scoring-rubric. Results are organised into a system-level feature matrix (protocols, runtime integrations, and non-functional properties) and an interaction-level feature matrix (workflow authoring and orchestration primitives). Both matrices extend the framework of Broccia et~al. @broccia2025humainflow to the three architectural categories covered by this study, with additional criteria (A2A, sandboxing, workflow patterns, memory, multi-agent coordination) drawn from Derouiche et~al. @derouiche2025agentic and Adimulam et~al. @adimulam2026orchestration.

=== System-level Feature Matrix

#figure(
  table(
    columns: (auto, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr),
    stroke: 0.5pt,
    inset: 5pt,
    align: (left, center, center, center, center, center, center, center, center),
    table.header(
      [*Platform*], [*MCP*], [*A2A*], [*SDK \ Indep.*], [*Local \ LLM*], [*Remote \ LLM*], [*Exten-\ sibility*], [*Moni-\ toring*], [*Sand-\ boxing*],
    ),
    [LangGraph], yes-cell, yes-cell, partial-cell, yes-cell, yes-cell, yes-cell, yes-cell, no-cell,
    [CrewAI], yes-cell, yes-cell, yes-cell, partial-cell, yes-cell, yes-cell, partial-cell, yes-cell,
    [OpenAI Agents SDK], yes-cell, partial-cell, partial-cell, partial-cell, partial-cell, yes-cell, yes-cell, yes-cell,
    [Google ADK], yes-cell, yes-cell, partial-cell, partial-cell, yes-cell, yes-cell, yes-cell, yes-cell,
    [Microsoft Agent Framework], yes-cell, yes-cell, yes-cell, yes-cell, yes-cell, yes-cell, yes-cell, partial-cell,
    [Flowise], yes-cell, no-cell, no-cell, yes-cell, yes-cell, yes-cell, partial-cell, partial-cell,
    [LangFlow], yes-cell, no-cell, no-cell, yes-cell, yes-cell, yes-cell, partial-cell, no-cell,
    [Dify], yes-cell, partial-cell, yes-cell, yes-cell, yes-cell, yes-cell, partial-cell, yes-cell,
    [n8n], yes-cell, partial-cell, no-cell, yes-cell, yes-cell, yes-cell, partial-cell, partial-cell,
  ),
  caption: [Layer 2: System-level Feature Matrix],
) <tab-layer2-system>

*MCP has become universal; A2A has not.* Model Context Protocol support is now native in every platform evaluated, typically in both client and server roles (LangGraph's `langchain-mcp-adapters`, CrewAI's `MCPServerAdapter`, OpenAI's `MCPServerStdio`/`Sse`/`StreamableHttp`, ADK's `MCPToolset`, MAF's built-in MCP client/server, Flowise's Custom MCP node, LangFlow 1.6's MCP server mode, Dify 1.6's two-way MCP, and n8n's MCP Client Tool / MCP Server Trigger nodes). This is a sharp shift from the state reported by Broccia et~al. @broccia2025humainflow in 2023, when no comparable interoperability protocol existed.

Google A2A (released April~2025) shows a different pattern: four of the five SDK/framework platforms ship first-class A2A (LangGraph via LangSmith's Agent Server, CrewAI via the optional `crewai[a2a]` extra, ADK as the reference runtime with auto-generated Agent Cards, and MAF as a headline 1.0 feature), while OpenAI Agents SDK supports A2A only through community adapters despite OpenAI being a co-founder of the governing Linux Foundation AAIF. The four visual platforms lag further: Flowise and LangFlow have no documented A2A support; Dify and n8n provide it only via plugin (Alibaba's Nacos A2A) or community node package respectively. The 12-month lag between MCP (November~2024) and A2A (April~2025) is visible in the matrix.

*SDK independence separates genuinely neutral runtimes from ecosystem clients.* Microsoft Agent Framework, CrewAI, and Dify are rated *Yes* because their runtimes are architecturally independent of any single upstream SDK: MAF explicitly unifies and supersedes AutoGen and Semantic Kernel with first-party connectors for every major provider; CrewAI uses LiteLLM as its own LLM abstraction rather than consuming LangChain's; Dify operates its own workflow engine and plugin-based provider system. LangGraph, OpenAI Agents SDK, and Google~ADK are *Partial* because they lean on their vendors' native LLM integrations and treat alternative providers as second-class extensions (LangGraph via LangChain, OpenAI via the Responses API, ADK via Gemini/Vertex). Flowise, LangFlow, and n8n are *No*: Flowise and LangFlow are fundamentally thin UIs over LangChain.js/LangChain-Python respectively, and n8n's AI capabilities are expressed inside its proprietary node system.

*Local and remote LLM support are nearly universal but with known asymmetries.* Every platform supports a broad range of remote providers (OpenAI, Anthropic, Gemini, Azure, Bedrock, Cohere, Mistral, and others), most through direct SDKs and CrewAI/ADK/OpenAI-SDK via LiteLLM. OpenAI Agents SDK is the single *Partial* on remote LLMs because multi-provider access requires the separate `LitellmModel` extension and is documented as best-effort. Local LLM support (Ollama / vLLM / llama.cpp / LM~Studio) is native in six platforms; OpenAI Agents SDK, Google~ADK, and CrewAI score *Partial* because local execution is reachable only through LiteLLM or a generic OpenAI-compatible base~URL rather than a first-class bundled integration.

*Monitoring shows a clear gap between runtime-native observability and third-party dependence.* LangGraph (native LangSmith plus end-to-end OpenTelemetry since 2025), OpenAI Agents SDK (built-in tracing, enabled by default), Google~ADK (OpenTelemetry GenAI semconv emission in 1.17+), and Microsoft Agent Framework (native OTLP emission with DevUI debugger) all qualify for *Yes*. The remaining five platforms are *Partial*: CrewAI's open-source distribution ships an event bus and structured logs but requires Langfuse, AgentOps, or CrewAI Enterprise for full tracing; Flowise, LangFlow, Dify, and n8n provide run logs and token counts in the UI but defer deeper tracing to external integrations. No platform scores *No*---all nine meet the minimum bar of structured execution logs.

*Sandboxing is the most uneven and the most load-bearing dimension for production use.* Google~ADK (gVisor-sandboxed Pods in `GkeCodeExecutor` plus Agent Engine persistent sandbox), Dify (open-source `dify-sandbox` with Seccomp syscall whitelisting), OpenAI Agents SDK (April~2026 Sandbox Agents with Docker/E2B/Cloudflare/Modal/Daytona providers), and CrewAI (Docker-first `CodeInterpreterTool` with E2B/Modal fallback) are rated *Yes*. Microsoft Agent Framework is *Partial*---the separate Agent Governance Toolkit adds policy-based execution rings, but OS-level isolation is advisory rather than embedded in the runtime.

Flowise, LangFlow, and n8n are *No* or *Partial*: each relies on a VM2/Pyodide-style in-process sandbox that has been repeatedly broken by 2025--2026 CVE chains (CVE-2025-34267 and CVE-2025-59528 in Flowise, CVE-2026-33017 in LangFlow at CVSS~9.3, and CVE-2026-1470 / CVE-2026-0863 / CVE-2025-68613 / CVE-2025-68668 in n8n). LangGraph is *No* because it has no built-in sandbox at all; the `PythonREPL` tool explicitly warns users to supply their own isolation. Given that generated agent code is the single most dangerous artefact a platform executes, this is the dimension on which the visual platforms and LangGraph pay the highest hidden cost relative to the SDK runtimes that ship production-grade isolation out of the box.

=== Interaction-level Feature Matrix

#figure(
  table(
    columns: (auto, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr),
    stroke: 0.5pt,
    inset: 5pt,
    align: (left, center, center, center, center, center, center),
    table.header(
      [*Platform*], [*Code \ Level*], [*Collab-\ oration*], [*HITL*], [*Workflow \ Patterns*], [*Memory*], [*Multi-\ Agent*],
    ),
    [LangGraph], no-cell, partial-cell, yes-cell, yes-cell, yes-cell, yes-cell,
    [CrewAI], no-cell, partial-cell, yes-cell, partial-cell, yes-cell, yes-cell,
    [OpenAI Agents SDK], no-cell, partial-cell, partial-cell, partial-cell, yes-cell, yes-cell,
    [Google ADK], no-cell, partial-cell, yes-cell, yes-cell, yes-cell, yes-cell,
    [Microsoft Agent Framework], no-cell, partial-cell, yes-cell, yes-cell, yes-cell, yes-cell,
    [Flowise], yes-cell, yes-cell, yes-cell, yes-cell, yes-cell, yes-cell,
    [LangFlow], partial-cell, no-cell, partial-cell, partial-cell, yes-cell, yes-cell,
    [Dify], yes-cell, yes-cell, yes-cell, yes-cell, yes-cell, partial-cell,
    [n8n], yes-cell, yes-cell, yes-cell, yes-cell, yes-cell, partial-cell,
  ),
  caption: [Layer 2: Interaction-level Feature Matrix],
) <tab-layer2-interaction>

*Code level partitions the platforms cleanly into three camps.* The five SDKs (LangGraph, CrewAI, OpenAI Agents~SDK, ADK, MAF) are full-code Python/TypeScript and score *No*---they ship no visual editor, though ADK and MAF include inspection DevUIs. Flowise, Dify, and n8n are no-code-first with a drag-and-drop canvas and a Code node as an escape hatch and score *Yes*. LangFlow sits uniquely between: every visual component is a Python object that users can edit in an embedded code pane, giving it a genuine low-code character and a *Partial* rating. This three-way split is the most architecturally load-bearing distinction in the matrix and echoes the "no-code / low-code / full-code" taxonomy used by Broccia et~al. @broccia2025humainflow.

*Collaboration tracks hosting model rather than capability.* Dify, Flowise, and n8n all ship first-class multi-user workspaces with role-based access control (Dify's four-role Owner/Admin/Editor/Member, Flowise Enterprise Workspaces with SSO and encrypted credentials, n8n's Projects with Admin/Editor/Viewer roles plus custom project roles). The five SDKs score *Partial* because collaboration is delegated to git; proprietary add-ons (LangSmith, CrewAI Enterprise/AMP, Foundry, Vertex AI~Agent~Engine) exist but are not part of the open-source core. LangFlow is the outlier at *No*---it offers no native multi-user support, and enterprise RBAC is only available when fronted by IBM watsonx Orchestrate; the open feature requests on the GitHub repository (#1864, #7824, #8531) have been tracked since 2024.

*Human-in-the-loop is the most uneven interaction-level dimension.* Seven platforms ship a first-class pause/resume primitive: LangGraph's `interrupt()` plus `interrupt_before`/`interrupt_after` breakpoints resumed via `Command(resume=...)`, CrewAI's `human_input=True` task flag plus Enterprise Pending Human Input state, ADK's `ToolConfirmation`/`RequireConfirmation` flow with `adk_request_confirmation` events, MAF's `RequestInfo` and approval-required tools, Flowise's `Human Input` node, Dify~1.13's `Human Input` workflow node with Approve/Reject/Escalate buttons, and n8n's `Wait` node for webhook-driven approval. OpenAI Agents SDK and LangFlow both score *Partial*: the former supports HITL only through user-assembled patterns over sessions and guardrails (no named primitive); the latter supports HITL at the component level but lacks a core-runtime pause/resume. Notably, HITL is a dimension that has moved quickly---Dify's node shipped in October~2025, ADK for Java landed it at 1.0 in April~2026, and MAF introduced its current form at 1.0---so the snapshot here is meaningfully newer than the 2023 state reported by Broccia et~al.

*Workflow pattern coverage splits by orchestration primitive.* LangGraph (sequential edges + `add_conditional_edges` + `Send`-based parallel supersteps + subgraphs), ADK (`SequentialAgent` / `ParallelAgent` / `LoopAgent`), MAF (sequential, concurrent, handoff, group chat, Magentic-One), Flowise (Agentflow V2 sequential + conditional + parallel + hierarchical supervisors), Dify, and n8n all support all four patterns (sequential, parallel, conditional, hierarchical/sub-workflow) and score *Yes*. CrewAI's `Process.sequential` and `Process.hierarchical` are first-class but parallelism requires per-task `async_execution=True` and conditional branching falls out of manager-agent delegation, earning *Partial*. OpenAI Agents SDK is similarly *Partial*---sequential and conditional emerge from handoffs and Python control flow, parallel runs via `asyncio.gather`, but there is no first-class parallel or hierarchical workflow abstraction. LangFlow is *Partial*: sequential and conditional are native, parallel fan-out and true hierarchical subflows are not.

*Memory and multi-agent are the broadest-covered dimensions.* Every platform ships first-class memory, though the surface area differs: LangGraph (`MemorySaver` + `PostgresSaver`/`SqliteSaver`/`RedisSaver` checkpointers plus the `Store` API with vector search), CrewAI (unified `Memory` class covering short-term, long-term SQLite, entity, and knowledge sources), OpenAI Agents SDK (`Sessions` with SQLite/SQLAlchemy/Redis/encrypted variants), ADK (`SessionService` plus `MemoryService` with `add_session_to_memory`/`search_memory`), MAF (agent memory plus context providers and thread state), and all four visual platforms (modular memory nodes including Postgres, Redis, Zep, and Mem0).

Multi-agent coordination is first-class in seven platforms---all five SDKs plus Flowise and LangFlow---through dedicated primitives (graphs, crews, handoffs, sub-agents, group chat, supervisor nodes). Dify and n8n score *Partial* because multi-agent patterns are constructed from general-purpose workflow nodes rather than a dedicated primitive: Dify embeds Agent nodes inside Workflows (or vice versa), and n8n's `AI Agent Tool` node lets a root agent call other agents as tools. The universality of multi-agent support contradicts an implicit assumption in Broccia et~al. @broccia2025humainflow that multi-agent coordination differentiates platforms strongly; in the current landscape it does not---orchestration _semantics_ do, which is what Layer~3 measures.

The feature gap between the three architectural categories is narrower in 2026 than prior-art surveys reported in 2023--2024: every platform supports MCP, local and remote LLMs, extensibility, memory, and multi-agent coordination. Meaningful differentiation has moved to protocol breadth (A2A), runtime isolation (sandboxing), and orchestration primitives (workflow pattern coverage, HITL primitive class)---the dimensions Layer~3 is designed to pressure-test.

== Layer 3 Results: Pipeline Benchmarking

=== Capability Overview

#include "../generated/capability-tiers.typ"

=== Per-Scenario Results

==== US001: Add Utility Function (Basic)

#include "../generated/per-story-US-001.typ"

All five evaluated platforms completed all four stages of US-001 (see @table-capability-tiers). Token and time costs span ~2.4× among the multi-agent and SDK-runtime incumbents: OpenAI Agents SDK at 100,383 tokens / \$0.047 / 3.4~min, Microsoft Agent Framework at 239,801 tokens / \$0.105 / 6.2~min on an identical task with the same model (`gpt-4.1-mini`); Google~ADK sits below the SDK-runtime floor at 56,764 tokens / \$0.026 / 4.9~min. No platform produced meaningfully different source artefacts; the divergence is framework-level orchestration behaviour.

*OpenAI Agents SDK* set the efficiency baseline at 100,383 tokens, \$0.047, and 3.4 minutes (Orchestration = 4.44; @table-cross-cutting). Native function calling and a trimmed conversation history kept accumulated context from dominating later turns, and no stage recorded a redundant-tool-call retry that would have triggered the loop-defence guard (rtc = 0.00 across all stages). This is the platform against which the other frameworks' orchestration overheads are measured.

*LangGraph* completed all four stages at 190,309 tokens, \$0.088, and 4.0 minutes, scoring 4.41 on Orchestration. LangGraph's token cost on US-001 is concentrated in a single stage rather than distributed across the pipeline: the Testing stage alone consumed roughly 151k of the 190k-token total across 23 tool calls, reflecting heavier test-fixture generation in that stage rather than history-replay blow-up across the run. The supervisor-checkpoint architecture keeps per-iteration cost bounded (three supervisor rounds per stage regardless of tool-call count) and rtc stayed low at 0.06, so the concentration is a task-level property of what the Testing stage needed to write, not an orchestration pathology.

*CrewAI* completed all four stages at 103,776 tokens, \$0.051, and 5.3 minutes, scoring 4.28 on Orchestration. Testing now produces executable test artefacts after two adapter changes: (1) an explicit `check_completion` tool with `result_as_answer` terminates the crew when the reviewer signals pass, avoiding the 50-iteration runaway loop that previously burned the Testing budget; (2) native function calling was restored for OpenAI-compatible providers, eliminating the ReAct-text-mode fallback that had embedded the full tool catalogue in every prompt. The Crew pattern preserves the full inter-agent message log across Technical~Lead~→~Developer~→~QA~→~Reviewer handoffs, producing the highest rtc in the dataset (0.33). Whether this cost compounds super-linearly on longer tasks is what the outstanding US-010 and US-020 runs are designed to answer.

*Google ADK* completed all four stages at 56,764 tokens, \$0.026, and 4.9 minutes---the lowest absolute token and cost figures in the dataset (Orchestration = 4.44; Efficiency = 4.69; Overall = 4.78). ADK's `SequentialAgent` + `LoopAgent` composition keeps iteration counts modest (41 iterations across 24 tool calls, `iteration_ratio = 0.21`), and rtc stayed at 0.00 on every stage. An earlier ADK failure mode---a swallowed `KeyError` at Deploy caused by the instruction templater matching the literal `\${PORT}` placeholder as a session-state lookup---was resolved in a prior iteration via a brace-escape applied to every agent instruction. ADK runs show some run-to-run variability on the Testing stage (a `JSON-parse` regression has intermittently surfaced in later repeated passes); the values reported here are from a representative clean run, and run-variance characterisation is listed as specified future work in @conclusions-future-work.

*Microsoft Agent Framework* completed all four stages at 239,801 tokens and \$0.105---roughly 2.4× the OpenAI SDK baseline and reflected in an Efficiency score of 4.18 (@table-cross-cutting). The residual cost profile traces to a Magentic-orchestrator completion-detection behaviour: the manager can spin on `executor → reviewer → re-executor` cycles long after real work has ended, resubmitting accumulated history and inflating the Deploy stage---which triggered the round-count cap in this run---to roughly 87k tokens on its own. The harness caps MagenticOne at four manager rounds and two stalls (down from twelve and three) to bound the worst-case token cost per stage; this is a cost bound rather than a fix for MagenticOne's underlying completion semantics, and is documented as such in the adapter source.

*Autonomy* scores at 5.00 uniformly across all five platforms (@table-cross-cutting). Every US-001 run completed with zero logged human interventions, and the autonomy aggregator falls back to that signal when the manual rubric is unscored (see @appendix-scoring-rubric). US-001 does not differentiate the platforms on this dimension; the outstanding intermediate and advanced scenarios (@conclusions-future-work) are designed to exercise it.

==== US001 Cross-Model Observations

The five platforms were re-run on US-001 with `anthropic/claude-sonnet-4.6` to verify that framework-level patterns from the `gpt-4.1-mini` baseline persisted under a stronger model and a different provider. The primary tables above are not regenerated because the Sonnet run exposed several adapter- and provider-level issues that bias the comparison; the `gpt-4.1-mini` baseline remains the only self-consistent five-platform dataset.

*Confirmed patterns.* LangGraph finished all four stages in three supervisor iterations each (49 tool calls, 209,130 tokens, \$0.821) with a redundant-tool-call rate of zero on every stage---the per-iteration-bounded profile is preserved under model swap. OpenAI Agents SDK remained the lowest-cost completion (111,442 tokens, \$0.442 total) with zero redundancy across all four stages. CrewAI dominated the cost profile (538,715 tokens, \$1.856 across three completed stages after a Requirements-stage task timeout), with redundant-tool-call rate elevated to 0.40 on the completed stages (highest in the dataset)---consistent with the full inter-agent log replay pattern observed on the primary baseline. The relative cost ordering across completed scenarios---*OpenAI SDK \< LangGraph \< CrewAI*---held under model swap.

*Four issues surfaced by the model swap* are worth reporting as methodological findings in their own right:

1. *CrewAI internal task timeout* (Requirements stage). CrewAI's task-level execution cap was not met on the Requirements prompt under Sonnet; the stage aborted after two iterations at 8,919 tokens with a CrewAI task-level error. Under the primary `gpt-4.1-mini` baseline the same stage completes comfortably within the cap. The cap is a framework-configuration issue rather than a capability issue, but it is only visible under a slower-responding model.

2. *Google ADK provider rate limiting* (Testing and Deploy stages). Testing and Deploy both aborted with `litellm.RateLimitError: AnthropicException` from the LiteLLM wrapper routing ADK to Anthropic. The earlier preliminary-run `list_directory` adapter wrapper error, reported in earlier drafts of this chapter, has been resolved by an adapter-level fix; the current failure mode is a Sonnet-provider throughput limit rather than an ADK bug. Requirements and Code Gen completed successfully before the limit was hit (103,256 and 25,348 tokens respectively).

3. *Microsoft Agent Framework via Anthropic* (all stages). Every stage failed immediately with an `OpenAIChatClient service failed to complete the prompt` error, zero tool calls executed. The underlying routing issue has evolved across preliminary runs (from a tool-message-ordering error via AWS Bedrock to the current prompt-completion failure via the OpenAI-compatible Anthropic endpoint), but MAF remains unreportable under Sonnet until provider routing is stabilised.

4. *False-positive success under zero work*. The harness guard added to handle earlier runs---demoting stages to FAIL when agent work is zero---continues to fire correctly on the MAF Sonnet rows, where every stage has zero tool calls and a non-empty error string. Without the guard, MAF's Sonnet codegen and testing stages would have reported PASS purely because earlier stages' baseline artefacts satisfied the file-presence validator.

*Methodological conclusion.* The Sonnet pass surfaces a distinct set of fragilities (CrewAI task timeout, ADK provider rate-limit, MAF provider-routing failure) that the `gpt-4.1-mini` baseline does not expose. *No single (model, provider) run is sufficient to characterise a platform's operational reliability.* The Sonnet dataset is treated as a cross-model validation pass; primary tables and numbers continue to refer to the `gpt-4.1-mini` run.

==== Model Sensitivity

The two-model pass permits one additional descriptive observation not available from either run alone: the *amount by which each framework amplifies model-level variance*. Holding the task constant (US-001) and taking `gpt-4.1-mini` and `claude-sonnet-4.6` as the two model conditions, @tab-model-sensitivity summarises three observable signals per platform: stage-completion delta (stages passing under baseline minus stages passing under Sonnet), token amplification (Sonnet tokens / baseline tokens on successfully-completed work), and the distinct error classes that surfaced under only one of the two models.

#figure(
  placement: none,
  table(
    columns: (auto, auto, auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: (left, center, center, left),
    table.header(
      [*Platform*], [*Stage delta*], [*Token amp.*], [*New error classes*],
    ),
    [OpenAI Agents SDK], [0], [1.11×], [—],
    [LangGraph], [0], [1.10×], [—],
    [Google ADK], [+2 under Sonnet], [N/A], [rate-limit (Sonnet)],
    [CrewAI], [+1 under Sonnet], [*5.19×*], [task-timeout (Sonnet)],
    [Microsoft Agent Framework], [+4 under Sonnet], [N/A], [provider-routing failure (Sonnet)],
  ),
  caption: [US-001 model sensitivity across `gpt-4.1-mini` and `claude-sonnet-4.6`. Token amplification is computed on successfully-completed work only; _N/A_ indicates that Sonnet-side provider errors (ADK rate-limit, MAF routing failure) truncate the comparable work. Under Sonnet, CrewAI's failing stage shifts from Testing to Requirements.],
) <tab-model-sensitivity>

Two findings fall out of this view and neither is visible from either model run in isolation.

First, *LangGraph and OpenAI Agents SDK are effectively model-invariant on this task*: zero stage delta, ~1.10× token amplification (close to the floor that any task would exhibit from one model being slightly more verbose per turn than another), and no new error classes surfaced by the model swap. Whatever model-level drift exists, these frameworks do not amplify it.

Second, *CrewAI materially amplifies model-level variance*: 5.19× tokens on identical work is far larger than the ~1.10× floor, and the amplification is consistent with the Crew pattern's full inter-agent log preservation---a marginally more verbose per-turn model compounds non-linearly when the entire conversation is replayed into every successor turn. This is the same architectural mechanism identified in the Key Findings replay-strategy taxonomy earlier in the chapter; the model-swap exposes it as a second symptom of the same root cause.

The remaining two rows (Google ADK and MAF) reflect provider-level rather than framework-level issues (Anthropic rate-limiting on ADK's Testing and Deploy; MAF provider routing failing wholesale under Sonnet) and are properly attributable to the (model, provider) combination. They are included in @tab-model-sensitivity for completeness but do not support a framework-level fragility claim.

Two model conditions is insufficient to calibrate a general model-fragility score; a formal _Model Robustness_ dimension anchored in multiple model conditions is listed as future work in @conclusions-future-work.

==== Intermediate and Advanced Scenarios

US-010 (Add API Endpoint), US-030 (Design Fullstack App), and US-020 (Implement Auth System) are fully scaffolded but have not been executed end-to-end; runs are held as specified future work (@conclusions-future-work).

=== Cross-cutting Dimension Scores

#include "../generated/cross-cutting.typ"

The per-platform Likert scores are derived by aggregating the six 0--3 rubric dimensions as defined in @appendix-scoring-rubric. Pipeline Completeness and Autonomy both saturate at 5.00 for all five platforms on US-001 (every run completed all four stages with zero human interventions); these dimensions are designed to discriminate when scenarios differ in completion or require intervention, and are carried forward for the intermediate and advanced scenarios. The discriminating dimensions on a basic scenario are Efficiency and Orchestration. Efficiency saturates at 5.00 for OpenAI Agents SDK (on the 100k-token budget); Google ADK (4.69) sits just below despite a lower absolute token count because its wall-clock and iteration ratios pull slightly; LangGraph (4.55), CrewAI (4.24), and MAF (4.18) drop progressively as orchestration overhead pushes them over the token budget. Orchestration clusters tightly at 4.28--4.44 across the five platforms, with CrewAI (4.28) slightly lower because its elevated rtc weighs on the trace-quality component.

=== Resource Consumption Analysis

#include "../generated/resource.typ"

Within the basic-task dataset the token-to-cost ratio is constant across platforms (same model), so token count is the primary cost discriminator. Wall-clock does not track token count: OpenAI Agents SDK's 3.4-minute run produced 100,383 tokens, while MAF's 6.2-minute run produced 239,801 (Magentic round-tripping concentrated on Deploy, ~87k tokens alone). LangGraph's 190,309 tokens are concentrated in Testing (151k). Peak memory varies by ~5.3× (236~MB LangGraph, 1,242~MB CrewAI), driven by each runtime's in-process session store. Cross-complexity patterns require the outstanding US-010, US-030, and US-020 runs.

== Discussion

=== Key Findings

Six findings emerge from the US-001 evaluation and its cross-model repeat, scoped to the five programmatic platforms covered by the current dataset (LangGraph, CrewAI, Microsoft Agent Framework, OpenAI Agents SDK, Google~ADK); visual-platform Layer~3 benchmarking and intermediate/advanced scenario runs are outstanding future work (@limitations, @conclusions-future-work).

*Framework replay strategy is the finer-grained predictor of cost, cutting across architectural category.* Three distinct history-management strategies are visible in the dataset and produce three distinct cost profiles: LangGraph's bounded supervisor checkpoints (three supervisor rounds per stage regardless of tool-call count, so per-iteration cost is roughly constant), OpenAI SDK's trimmed conversation history, and Microsoft Agent Framework's Magentic-orchestrator accumulation (the manager resubmits the full cycle history on each round when completion detection misfires, concentrated in the Deploy stage which alone produced ~87k tokens). CrewAI's full inter-agent log preservation is architecturally in the same family as the Magentic accumulation pattern and produces the dataset's highest rtc; whether it compounds on longer tasks is a specific hypothesis the outstanding US-010 and US-020 runs are designed to test. This is the central methodological finding: category-level guidance ("use a multi-agent framework vs. an SDK runtime") is too coarse, because within the multi-agent-framework category CrewAI sits near the SDK-runtime cost floor while MAF sits at the top.

*Redundant-tool-call rate (rtc) is a reliable stage-level indicator of orchestration pathology.* The metric---introduced in this evaluation---cleanly separates platforms that converge on a stage (OpenAI Agents SDK, Google ADK, and MAF at rtc = 0.00 across every stage) from CrewAI (rtc = 0.33 on US-001, driven by the Crew pattern's full inter-agent log preservation) and LangGraph (rtc = 0.06, a single codegen-stage retry). Stages with elevated rtc correspond one-to-one with stages that triggered the harness loop-defence guard. This differs from the prior-framework evaluations surveyed in @yin2025comprehensive and @mehta2025clear, which report raw task success without instrumenting intra-stage retry loops, and gives a single observable signal for detecting a class of framework pathology that otherwise only shows up in aggregated token totals.

*Token cost on an identical task spans roughly 2.4× across platforms---evidence for the two findings above.* OpenAI Agents SDK completed US-001 in 100,383 tokens under `gpt-4.1-mini`; Microsoft Agent Framework required 239,801 tokens on the same task and the same model. No platform produced meaningfully different source artefacts. The spread is consistent with the replay-strategy taxonomy (accumulated-history MAF at the top, trimmed-history OpenAI SDK at the floor) and with the rtc ordering. The absolute magnitude of the spread has narrowed relative to earlier preliminary runs as several adapter fixes landed (removing a double-counted LLM-duration catch-up layer, tightening MagenticOne's round and stall limits, restoring CrewAI native function calling, adding a crew-level `check_completion` termination tool); the 2.4× figure therefore underestimates the effect an unhardened adapter could show and should be read as a conservative bound on framework-induced cost variance.

*No single (model, provider) run surfaces all framework fragilities.* The Sonnet 4.6 cross-model pass surfaced a CrewAI task timeout (Requirements stage), a Google~ADK provider rate-limit (Testing and Deploy stages via LiteLLM routing to Anthropic), and a Microsoft Agent Framework provider-routing failure (all stages); none of these are visible on the `gpt-4.1-mini` baseline. The framework comparison reported in @derouiche2025agentic, which evaluates visual platforms on a single LLM backend, would not detect these classes of fault on any given model in isolation, and this is the class of observation the framework-centric methodology developed here makes visible.

*Frameworks differ meaningfully in how much they amplify model-level variance.* Holding the task constant across `gpt-4.1-mini` and `claude-sonnet-4.6`, LangGraph and OpenAI Agents SDK amplify model-level token variance by ~1.1× (close to the floor any task would exhibit from one model being slightly more verbose than another), while CrewAI amplifies by ~5.2×---a framework-specific signal attributable to the Crew pattern's full-history replay compounding per-turn verbosity non-linearly (@tab-model-sensitivity). The other two platforms (Google ADK and MAF) exhibit provider- rather than framework-level sensitivity and are excluded from the amplification claim. With N = 2 model conditions, this is a descriptive observation rather than a calibrated score; promoting it to a rubric-scored _Model Robustness_ cross-cutting dimension is listed as specified future work (@conclusions-future-work).

*File-presence validation alone is insufficient as a stage success signal.* A harness guard that demotes a stage to FAIL when no *productive* tool call (`write_file`, `execute_shell`, or `deploy_remote`) has occurred fires correctly on the MAF Sonnet run, where four stages would otherwise report PASS with zero tool calls and a visible orchestration error purely because baseline files produced in earlier stages satisfied the validator's file-existence check. The guard also fires on intermittent ADK Testing-stage regressions observed in repeated passes---where the pipeline aborts after a single `read_file` and produces no test artefacts, yet the baseline workspace's `tests/test_health.py` would satisfy a file-presence check. The narrower zero-tool-calls check would not catch the ADK case because one read has been made; the broadened productive-tool-call check catches it. The guard is described in the Implementation chapter alongside the other defence-in-depth mitigations.

=== Cross-Category Patterns

Only two of the three platform categories are represented in the current benchmarking dataset; the four visual platforms have not yet been run on US-001.

*SDK runtimes* (OpenAI Agents SDK at 100k tokens, Google~ADK at 57k) and *multi-agent orchestrators* (CrewAI at 104k, LangGraph at 190k, MAF at 240k) span the 57--240k band. The separation is not driven by agent count---LangGraph and CrewAI both run multi-agent graphs---but by conversation-history policy. The internal spread within the multi-agent category (CrewAI 104k to MAF 240k) is as wide as the gap between the two SDK-runtime points, reinforcing that category alone is too coarse a predictor.

CrewAI sits within 4% of the SDK-runtime cost floor despite carrying the highest rtc, because its sequential-crew orchestration combined with the restored native function-calling path and the `check_completion` termination tool converges cleanly on the basic task. Architectural category alone is not supported as a performance predictor by the current data---orchestration strategy cuts across category boundaries. A full cross-category claim requires the outstanding visual-platform Layer~3 data.

=== Complexity Scaling

A single-scenario dataset cannot distinguish a platform whose overhead is constant from one whose overhead scales with task length---the CrewAI and MAF token profiles in particular are plausibly either a fixed per-turn surcharge or a compounding history-replay cost that would widen the gap on more complex scenarios. The planned intermediate and advanced scenarios are designed to discriminate between these hypotheses.

