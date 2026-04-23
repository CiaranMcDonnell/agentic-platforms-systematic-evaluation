#import "../template.typ": *

= Results <evaluation>

This chapter presents the evaluation results across all three layers of the framework and discusses findings and cross-platform patterns.

== Layer 1 Results: Industry Readiness

Layer~1 profiles were compiled in April~2026 from each platform's GitHub repository, official documentation, release notes, and published customer lists. @tab-layer1 summarises the nine platforms against the six criteria defined in @appendix-scoring-rubric; the narrative that follows highlights the patterns and individual deviations that frame the rest of the chapter.

#figure(
  table(
    columns: 7,
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    table.header(
      [*Platform*], [*Release Maturity*], [*Maintenance*], [*Community*], [*Docs*], [*Adoption*], [*Licensing*],
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

*Adoption is well-attested for the established platforms and still building for the two newest.* LangGraph (Klarna, LinkedIn, Uber, Replit), CrewAI (PwC, Piracanjuba, ~2 billion agent executions in the trailing 12~months), OpenAI Agents SDK (Klarna, Clay, Canva, Coinbase), LangFlow (inheriting the DataStax enterprise portfolio---FedEx, Capital One, Home~Depot, Verizon---through its IBM parent following IBM's February~2025 announcement of the DataStax acquisition), Dify (2000+ commercial teams including Maersk, Novartis, RICOH, Panasonic, Deloitte, NTT), and n8n (3000+ enterprise customers including Microsoft and KPMG) all publish named customer lists or case studies. Flowise is rated *Partial* because its adoption is concentrated among agencies and SMBs with fewer published Fortune-500 references. Google~ADK (Renault, Box, Revionics) and Microsoft Agent Framework both rate *Partial* for a common reason: strong vendor backing and clear enterprise positioning, but a narrower set of post-release case studies than the older frameworks.

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

*MCP has become universal; A2A has not.* Model Context Protocol support is now native in every platform evaluated, typically in both client and server roles (LangGraph's `langchain-mcp-adapters`, CrewAI's `MCPServerAdapter`, OpenAI's `MCPServerStdio`/`Sse`/`StreamableHttp`, ADK's `MCPToolset`, MAF's built-in MCP client/server, Flowise's Custom MCP node, LangFlow 1.6's MCP server mode, Dify 1.6's two-way MCP, and n8n's MCP Client Tool / MCP Server Trigger nodes). This is a sharp shift from the state reported by Broccia et~al. @broccia2025humainflow in 2023, when no comparable interoperability protocol existed. Google A2A (released April~2025) shows a different pattern: four of the five SDK/framework platforms ship first-class A2A (LangGraph via LangSmith's Agent Server, CrewAI via the optional `crewai[a2a]` extra, ADK as the reference runtime with auto-generated Agent Cards, and MAF as a headline 1.0 feature), while OpenAI Agents SDK supports A2A only through community adapters despite OpenAI being a co-founder of the governing Linux Foundation AAIF. The four visual platforms lag further: Flowise and LangFlow have no documented A2A support; Dify and n8n provide it only via plugin (Alibaba's Nacos A2A) or community node package respectively. The 12-month lag between MCP (November~2024) and A2A (April~2025) is visible in the matrix.

*SDK independence separates genuinely neutral runtimes from ecosystem clients.* Microsoft Agent Framework, CrewAI, and Dify are rated *Yes* because their runtimes are architecturally independent of any single upstream SDK: MAF explicitly unifies and supersedes AutoGen and Semantic Kernel with first-party connectors for every major provider; CrewAI uses LiteLLM as its own LLM abstraction rather than consuming LangChain's; Dify operates its own workflow engine and plugin-based provider system. LangGraph, OpenAI Agents SDK, and Google~ADK are *Partial* because they lean on their vendors' native LLM integrations and treat alternative providers as second-class extensions (LangGraph via LangChain, OpenAI via the Responses API, ADK via Gemini/Vertex). Flowise, LangFlow, and n8n are *No*: Flowise and LangFlow are fundamentally thin UIs over LangChain.js/LangChain-Python respectively, and n8n's AI capabilities are expressed inside its proprietary node system.

*Local and remote LLM support are nearly universal but with known asymmetries.* Every platform supports a broad range of remote providers (OpenAI, Anthropic, Gemini, Azure, Bedrock, Cohere, Mistral, and others), most through direct SDKs and CrewAI/ADK/OpenAI-SDK via LiteLLM. OpenAI Agents SDK is the single *Partial* on remote LLMs because multi-provider access requires the separate `LitellmModel` extension and is documented as best-effort. Local LLM support (Ollama / vLLM / llama.cpp / LM~Studio) is native in six platforms; OpenAI Agents SDK, Google~ADK, and CrewAI score *Partial* because local execution is reachable only through LiteLLM or a generic OpenAI-compatible base~URL rather than a first-class bundled integration.

*Monitoring shows a clear gap between runtime-native observability and third-party dependence.* LangGraph (native LangSmith plus end-to-end OpenTelemetry since 2025), OpenAI Agents SDK (built-in tracing, enabled by default), Google~ADK (OpenTelemetry GenAI semconv emission in 1.17+), and Microsoft Agent Framework (native OTLP emission with DevUI debugger) all qualify for *Yes*. The remaining five platforms are *Partial*: CrewAI's open-source distribution ships an event bus and structured logs but requires Langfuse, AgentOps, or CrewAI Enterprise for full tracing; Flowise, LangFlow, Dify, and n8n provide run logs and token counts in the UI but defer deeper tracing to external integrations. No platform scores *No*---all nine meet the minimum bar of structured execution logs.

*Sandboxing is the most uneven and the most load-bearing dimension for production use.* Google~ADK (gVisor-sandboxed Pods in `GkeCodeExecutor` plus Agent Engine persistent sandbox), Dify (open-source `dify-sandbox` with Seccomp syscall whitelisting), OpenAI Agents SDK (April~2026 Sandbox Agents with Docker/E2B/Cloudflare/Modal/Daytona providers), and CrewAI (Docker-first `CodeInterpreterTool` with E2B/Modal fallback) are rated *Yes*. Microsoft Agent Framework is *Partial*---the separate Agent Governance Toolkit adds policy-based execution rings, but OS-level isolation is advisory rather than embedded in the runtime. Flowise, LangFlow, and n8n are *No* or *Partial*: each relies on a VM2/Pyodide-style in-process sandbox that has been repeatedly broken by 2025--2026 CVE chains (CVE-2025-34267 and CVE-2025-59528 in Flowise, CVE-2026-33017 in LangFlow at CVSS~9.3, and CVE-2026-1470 / CVE-2026-0863 / CVE-2025-68613 / CVE-2025-68668 in n8n). LangGraph is *No* because it has no built-in sandbox at all; the `PythonREPL` tool explicitly warns users to supply their own isolation. Given that generated agent code is the single most dangerous artefact a platform executes, this is the dimension on which the visual platforms and LangGraph pay the highest hidden cost relative to the SDK runtimes that ship production-grade isolation out of the box.

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

*Memory and multi-agent are the broadest-covered dimensions.* Every platform ships first-class memory, though the surface area differs: LangGraph (`MemorySaver` + `PostgresSaver`/`SqliteSaver`/`RedisSaver` checkpointers plus the `Store` API with vector search), CrewAI (unified `Memory` class covering short-term, long-term SQLite, entity, and knowledge sources), OpenAI Agents SDK (`Sessions` with SQLite/SQLAlchemy/Redis/encrypted variants), ADK (`SessionService` plus `MemoryService` with `add_session_to_memory`/`search_memory`), MAF (agent memory plus context providers and thread state), and all four visual platforms (modular memory nodes including Postgres, Redis, Zep, and Mem0). Multi-agent coordination is first-class in seven platforms---all five SDKs plus Flowise and LangFlow---through dedicated primitives (graphs, crews, handoffs, sub-agents, group chat, supervisor nodes). Dify and n8n score *Partial* because multi-agent patterns are constructed from general-purpose workflow nodes rather than a dedicated primitive: Dify embeds Agent nodes inside Workflows (or vice versa), and n8n's `AI Agent Tool` node lets a root agent call other agents as tools. The universality of multi-agent support contradicts an implicit assumption in Broccia et~al. @broccia2025humainflow that multi-agent coordination differentiates platforms strongly; in the current landscape it does not---orchestration _semantics_ do, which is what Layer~3 measures.

Taken together, the Layer~2 matrices show that the feature gap between the three architectural categories is narrower in 2026 than prior-art surveys reported in 2023--2024: every platform supports MCP, local and remote LLMs, extensibility, memory, and multi-agent coordination; the meaningful differentiation has moved to protocol breadth (A2A), runtime isolation (sandboxing), and orchestration primitives (workflow pattern coverage, HITL primitive class). These are the dimensions that Layer~3 pipeline benchmarking is designed to pressure-test.

== Layer 3 Results: Pipeline Benchmarking

// Tables in this section are generated from the DuckDB result store
// by `desmet export-typst`. Regenerate after each evaluation run or
// after bulk rubric edits — do not hand-edit the files under
// `docs/report/generated/`.

=== Capability Overview

// Tier per (platform, stage): Supported = every scenario completed the
// stage; Partial = at least one but not all; Not Supported = zero.
#include "../generated/capability-tiers.typ"

=== Per-Scenario Results

==== US001: Add Utility Function (Basic)

#include "../generated/per-story-US-001.typ"

Four of the five evaluated platforms completed all four stages of US-001; CrewAI failed the Testing stage (see @table-capability-tiers), yielding a Pipeline Completeness score of 1.00. Token and time costs span roughly half an order of magnitude across the five platforms: OpenAI Agents SDK set the tightest profile at 46,758 tokens and \$0.023 across a 2.3-minute run, while Microsoft Agent Framework consumed 230,431 tokens and \$0.101 across 5.0 minutes---a roughly 4.9× token spread on an identical task driven by the same model (`gpt-4.1-mini`). No platform produced meaningfully different source artefacts; the divergence is attributable to framework-level orchestration behaviour rather than task-related work.

*OpenAI Agents SDK* set the efficiency baseline at 46,758 tokens, \$0.023, and 2.3 minutes (Orchestration = 4.44; @table-cross-cutting). Native function calling and a trimmed conversation history kept accumulated context from dominating later turns, and no stage recorded a redundant-tool-call retry that would have triggered the loop-defence guard. This is the platform against which the other frameworks' orchestration overheads are measured.

*LangGraph* completed all four stages at 59,527 tokens, \$0.028, and 3.3 minutes, scoring 4.41 on Orchestration---the second-lowest token cost in the dataset and within one order of magnitude of the OpenAI SDK baseline. The supervisor-checkpoint architecture bounds iteration overhead by the supervisor budget: when a stage hits a transient tool failure, a bounded number of supervisor rounds retries with preserved state rather than replaying the full inter-agent history. The resulting cost profile is roughly constant per supervisor round, independent of cumulative stage length.

*CrewAI* completed Requirements, Code Gen, and Deploy but failed the Testing stage, producing a Pipeline Completeness score of 1.00 and the lowest Orchestration score in the dataset at 3.25. The total 77,486 tokens / \$0.037 and 8.8-minute wall-clock reflect work performed across the three completed stages; the Testing stage did not produce executable test artefacts despite triggering the harness loop-defence guard, because CrewAI's internal retry policy absorbs the signal without changing behaviour. Two design choices concentrate cost on longer tasks. First, the runtime falls back to ReAct text-mode prompting on non-OpenAI providers---the native function-calling path is currently unavailable for Gemini via OpenRouter---which embeds the full tool catalogue and few-shot parser hints in every prompt. Second, the Crew pattern preserves the full inter-agent message log across Technical~Lead~→~Developer~→~QA~→~Reviewer handoffs. On US-001 the Testing-stage failure is the headline result; whether CrewAI's per-turn cost compounds super-linearly on a longer task is a question that the outstanding US-010 and US-020 runs are specifically designed to answer.

*Google ADK* completed all four stages at 56,764 tokens, \$0.026, and 4.9 minutes (Orchestration = 4.44). An earlier run aborted immediately at Deploy with a swallowed `KeyError` reporting that the context variable `PORT` was not found; the exception originated from ADK's instruction templater matching the literal `\${PORT}` placeholder in the prompt as a session-state lookup. A brace-escape applied to every agent instruction before it reaches the ADK templater has fully resolved this failure, and Deploy now completes cleanly as reflected in @table-capability-tiers.

*Microsoft Agent Framework* completed all four stages at 230,431 tokens and \$0.101---roughly 4.9× the OpenAI SDK baseline and reflected in an Efficiency score of 4.35 (@table-cross-cutting). The residual cost profile traces to a Magentic-orchestrator completion-detection behaviour: the manager can spin on `executor → reviewer → re-executor` cycles long after real work has ended, resubmitting accumulated history and inflating the Deploy stage---which triggered the round-count cap in this run---to roughly 86k tokens on its own. The harness caps MagenticOne at four manager rounds and two stalls (down from twelve and three) to bound the worst-case token cost per stage; this is a cost bound rather than a fix for MagenticOne's underlying completion semantics, and is documented as such in the adapter source. Two recent adapter fixes account for the bulk of the reduction relative to earlier runs: removing a duration catch-up layer that double-counted wall-clock (and the token telemetry tied to it) and tightening the MagenticOne round limits above. A parallel re-ordering of the deploy prompt so that required artefacts appear before the task list stops the replanner from dropping them on the happy path and restored Deploy completion.

*Autonomy* scores at 5.00 uniformly across all five platforms (@table-cross-cutting). Every US-001 run completed with zero logged human interventions, and the autonomy aggregator falls back to that intervention signal when the manual rubric has not yet been scored (see @appendix-scoring-rubric). US-001 is a basic task that requires neither long-running self-correction nor substantial planning revision, so the dimension does not differentiate the platforms at this complexity tier; the outstanding intermediate and advanced scenario runs (@conclusions-future-work) are specifically designed to exercise it.

==== US001 Cross-Model Observations

The five platforms were re-run on US-001 with `anthropic/claude-sonnet-4.6` to verify that the framework-level patterns observed under the primary `gpt-4.1-mini` baseline persisted under a stronger model and a different provider. Results below summarise the observed behaviour; the primary tables above are not regenerated because the Sonnet run exposed four adapter-level or provider-level issues that bias the comparison, and the primary `gpt-4.1-mini` baseline dataset remains the only self-consistent five-platform baseline currently available.

*Confirmed patterns.* LangGraph retained the tightest profile on the new model, finishing all four stages in three supervisor iterations each (49 tool calls, 209,130 tokens, \$0.821) with a redundant-tool-call rate of zero on every stage. OpenAI Agents SDK remained low-token (111,442 tokens, \$0.442 total) with zero redundancy across Code Gen, Testing, and Deploy. CrewAI continued to dominate the cost profile (538,715 tokens, \$1.856 across three completed stages), with Deploy redundancy at 0.29 after a fix---still the highest on any platform but reduced from 0.50 under the primary `gpt-4.1-mini` baseline. The relative platform ranking---LangGraph $<$ OpenAI SDK $<$ CrewAI on cost per completed scenario---held under model swap.

*Four new issues were surfaced by the model swap* and are worth reporting as methodological findings in their own right:

1. *CrewAI internal task timeout* (Requirements stage). CrewAI enforces a default 45-second `max_execution_time` per task that Sonnet could not meet on the Requirements prompt; under the primary `gpt-4.1-mini` baseline the same stage completed in 30 seconds and the limit was never approached. The symptom is stage-level failure with no diagnostic beyond the CrewAI error. The cap is a framework-configuration issue rather than a capability issue.

2. *Google ADK directory-argument handling* (Requirements stage). The stage aborted with `[Errno 21] Is a directory: '/workspace/app/schemas'` during a routine `list_directory` call. The fault is an adapter wrapper issue, not an ADK or Sonnet behaviour; it went undetected under the primary `gpt-4.1-mini` baseline because the baseline workspace navigation under that model did not touch the affected path.

3. *Microsoft Agent Framework via AWS Bedrock* (all stages). Every stage failed with a Claude `tool_use_id`/`tool_result` message-ordering error originating from MAF's Magentic orchestrator stitching sub-agent histories for Bedrock's strict message format. Zero tool calls executed in any stage, making the Sonnet MAF row unreportable until the provider routing is switched from Bedrock to direct Anthropic.

4. *False-positive success under zero work*. A separate harness guard was added during the run analysis to flip stages to FAIL when the orchestration error was accompanied by zero tool calls; without it, MAF's codegen and testing stages reported PASS purely because earlier stages' baseline artefacts satisfied the file-presence validator.

*Methodological conclusion.* Three of the four issues---the CrewAI task timeout, the ADK `list_directory` error, and the MAF Bedrock incompatibility---were not visible under single-model evaluation on the primary `gpt-4.1-mini` baseline. This is direct evidence for a claim the evaluation framework can now make explicitly: even on a task as simple as US-001, a cross-model run surfaces framework and adapter fragilities that a single-model baseline hides. The Sonnet dataset is therefore treated as a validation pass for the primary `gpt-4.1-mini` baseline findings rather than a replacement for them, and the tables and numbers elsewhere in this chapter continue to refer to the primary `gpt-4.1-mini` baseline run.

==== Intermediate and Advanced Scenarios

US-010 (Add API Endpoint, intermediate), US-030 (Design Fullstack App, intermediate), and US-020 (Implement Auth System, advanced) are fully scaffolded---scenario YAML, prompt templates, Gherkin acceptance criteria, and harness tables are version-controlled---but have not been executed end-to-end. These runs are held as specified future work (@conclusions-future-work); their omission is the reason cross-complexity efficiency patterns are reported as a basic-task snapshot rather than a scaling curve in this chapter.

=== Cross-cutting Dimension Scores

#include "../generated/cross-cutting.typ"

The per-platform Likert scores are derived by aggregating the six 0--3 rubric dimensions as defined in @appendix-scoring-rubric. Efficiency saturates at 5.00 for LangGraph and OpenAI Agents SDK, which complete US-001 well within the 100k-token budget, and drops below ceiling for the three platforms whose orchestration overhead pushes them over it: Google ADK at 4.69, CrewAI at 4.62, and MAF at 4.35. Orchestration differentiates the platforms more finely (3.25 for CrewAI, which absorbed the Testing-stage loop-defence signal without converging; 4.41--4.44 for the other four). Pipeline Completeness collapses to a binary signal on a single-scenario dataset (3.00 for full completion, 1.00 for CrewAI's Testing-stage failure), and Autonomy saturates at 5.00 across the board because US-001 did not exercise the dimension and every run logged zero human interventions. A radar-chart visualisation comparing the four dimensions across all nine platforms is deferred until the visual-platform Layer~3 data (@conclusions-future-work) is available to populate it.

=== Resource Consumption Analysis

#include "../generated/resource.typ"

Within the basic-task dataset the token-to-cost ratio is essentially constant across platforms (all five run on the same model), so token count is the primary cost discriminator. Wall-clock does not track token count: CrewAI's 8.8-minute run produced 77,486 tokens (short aggregate text with long tool-retry pauses), whereas MAF's 5.0-minute run produced 230,431 tokens (rapid Magentic round-tripping concentrated on the Deploy stage, which alone accounts for roughly 86k of those tokens). Peak memory varies by roughly 3.4× (242~MB for OpenAI SDK, 831~MB for Google ADK) and is driven by the runtime's in-process session store rather than by task characteristics. Cross-complexity efficiency patterns---whether the MAF and CrewAI profiles widen or compress relative to the baseline as scenario complexity grows---require the outstanding US-010, US-030, and US-020 runs to establish.

== Discussion

=== Scope of the Benchmarking Dataset

Before presenting cross-platform findings, the boundaries of the current Layer~3 dataset must be stated explicitly, because two deliberate scope choices shape every quantitative claim in this chapter.

*Visual platforms are evaluated at Layers~1 and~2 only; Layer~3 benchmarking covers the five programmatic platforms.* Flowise, LangFlow, Dify, and n8n have complete Layer~1 maturity profiles (@tab-layer1) and complete Layer~2 feature matrices (@tab-layer2-system, @tab-layer2-interaction), and adapters exist for Flowise, LangFlow, and n8n that successfully exercise platform initialisation and authentication. However, none of the four visual platforms has been run end-to-end through the four-stage pipeline at the time of writing: the Flowise, LangFlow, and n8n adapters reach the harness entrypoints but a full US-001 pipeline run has not yet been executed against them, and Dify is blocked on the marketplace-only plugin ecosystem discussed in @limitations. Every Layer~3 number, ranking, and finding below therefore refers to the five platforms with completed pipeline data---LangGraph, CrewAI, Microsoft Agent Framework, OpenAI Agents SDK, and Google~ADK---and cross-category claims that would require visual-platform Stage~3 numbers are flagged as outstanding where they arise. Completing visual-platform Layer~3 benchmarking is the single largest piece of future work needed to close the three-category comparison this framework was designed to enable.

*Only US-001 (basic) has been benchmarked end-to-end; US-010, US-030, and US-020 are future work.* The pipeline framework is designed for four scenarios spanning three complexity tiers (@tab-user-scenarios), but only the basic scenario (US-001: add utility function) has been run end-to-end at the time of writing. The two intermediate scenarios (US-010: add API endpoint; US-030: design fullstack app) and the advanced scenario (US-020: implement auth system) are fully defined---scenario YAML, prompt templates, and Gherkin acceptance criteria are version-controlled---and the harness is capable of executing them; what is outstanding is the evaluation run itself. A single-scenario dataset fundamentally cannot separate a platform whose overhead is a fixed per-turn surcharge from one whose overhead compounds with task length. The CrewAI history-replay cost in particular is stated as a conjecture rather than a conclusion because the two hypotheses---constant per-turn surcharge versus super-linear history compounding---are indistinguishable on a basic scenario; the intermediate and advanced scenarios are specifically designed to discriminate between them. Findings that depend on complexity scaling are therefore qualified as such throughout this chapter, and running the three remaining scenarios is the second-largest piece of future work.

Taken together, these two scope constraints mean the present evaluation is best read as an empirical baseline on a single basic task for the programmatic subset of the platform landscape, with the visual-platform and complexity-scaling extensions identified, scaffolded, and left as specified future work rather than as open research questions. The three-layer framework, the nine-platform selection, and the per-scenario harness are designed to accommodate these extensions without architectural change; the outstanding work is evaluation runs, not framework development.

=== Key Findings

Five findings emerge from the US-001 evaluation and its cross-model repeat; each is grounded in specific observed behaviour rather than theoretical expectation. All findings are scoped to the five programmatic platforms covered by the current dataset, per the scope statement above.

*Token cost on an identical task spans roughly half an order of magnitude across platforms.* OpenAI Agents SDK completed US-001 end-to-end in 46,758 tokens under `gpt-4.1-mini`; Microsoft Agent Framework required 230,431 tokens on the same task and the same model---a roughly 4.9× spread attributable entirely to orchestration overhead. No platform produced meaningfully different source artefacts. Even after adapter-level fidelity fixes (removing a double-counted LLM-duration catch-up layer and tightening MagenticOne's round and stall limits), framework choice remains the dominant driver of inference economics for short development tasks.

*Redundant-tool-call rate (rtc) is a reliable early indicator of orchestration pathology.* Stages with elevated rtc in this run correspond one-to-one with stages that triggered the harness loop-defence guard. The metric distinguishes between platforms that converge cleanly (OpenAI Agents SDK and Google ADK at Orchestration = 4.44) and platforms whose retry policies absorb loop-defence warnings without changing behaviour (CrewAI's Testing-stage failure at Orchestration = 3.25 despite loop-defence firing). This differs from the prior-framework evaluations surveyed in @yin2025comprehensive and @mehta2025clear, which report raw task success without instrumenting intra-stage retry loops.

*Framework replay strategy predicts cost scaling.* Three distinct history-management strategies are visible in the dataset: LangGraph's bounded supervisor checkpoints (iteration cost is roughly constant across the stage), OpenAI SDK's trimmed conversation history, and Microsoft Agent Framework's Magentic-orchestrator accumulation (the manager can resubmit the full cycle history on each round when completion detection misfires). Only the third pattern is super-linear in stage length, which is why MAF accounts for roughly 49\% of the entire US-001 run's aggregate token consumption despite completing identical work. CrewAI's full inter-agent log preservation is architecturally in the same family as the Magentic accumulation pattern; whether it produces the same compounding profile on longer tasks is a specific hypothesis the outstanding US-010 and US-020 runs are designed to test.

*Adapter-level fragilities hide under single-model evaluation.* Cross-model repeat under Sonnet 4.6 surfaced three issues---a CrewAI 45-second task timeout, an ADK `list_directory` directory-argument error, and a Microsoft Agent Framework incompatibility with Anthropic via AWS Bedrock---none of which was visible on the primary `gpt-4.1-mini` baseline. On a task as simple as US-001 this is a meaningful methodological result: the framework comparison reported in @derouiche2025agentic, which evaluates visual platforms on a single LLM backend, would not detect these classes of fault.

*File-presence validation is insufficient as a stage success signal.* The MAF Sonnet run demonstrates a degenerate case: four stages reported PASS with zero tool calls and a visible orchestration error, purely because baseline files produced in earlier stages satisfied the validator's file-existence check. Without a harness guard that demotes stages to FAIL when agent work is zero and errors are non-empty, evaluation reports would silently include non-runs as successes. The original harness guard demoted stages with exactly zero tool calls and a non-empty error list, but a subsequent Google~ADK testing-stage failure under `gpt-4.1-mini` exposed a narrower variant: the pipeline crashed with `Unterminated string starting at: line 1 column 46 (char 45)` after a single `read_file` call and produced no test artefacts, yet the baseline workspace's `tests/test_health.py` satisfied the testing validator --- the zero-tool-calls check did not fire because one read had been made. The guard is now keyed on the absence of any *productive* tool call (`write_file`, `execute_shell`, or `deploy_remote`) rather than on an empty tool-call list, so read-only pipeline aborts are also demoted to FAIL regardless of the validator verdict. The broadened guard is described in the Implementation chapter alongside the other defence-in-depth mitigations.

=== Cross-Category Patterns

Of the three platform categories defined in the framework (multi-agent orchestrators, SDK runtimes, visual platforms), only the first two are represented in the current benchmarking dataset; the four visual platforms (Flowise, LangFlow, Dify, n8n) have not yet been run on US-001 and are therefore excluded from category-level analysis.

Within the evaluated set, *SDK runtimes* (OpenAI Agents SDK at 46,758 tokens, Google ADK at 56,764 tokens) and LangGraph (59,527 tokens) cluster tightly in the 45--60k range, while *multi-agent orchestrators* span a much wider band---CrewAI at 77,486 tokens (with a Testing-stage failure) and Microsoft Agent Framework at 230,431 tokens. The separation is not driven by agent count (LangGraph and CrewAI both run multi-agent graphs) but by conversation-history policy, as described under _Framework replay strategy_ above.

LangGraph occupies the lowest-cost position in its category because its supervisor checkpoints effectively bound history replay; this converges the multi-agent orchestrator profile onto the SDK-runtime profile on simple tasks. The hypothesis that architectural category alone predicts performance is therefore not supported by the current data---orchestration strategy is the finer-grained predictor, cutting across category boundaries. A full cross-category claim requires the visual-platform Layer~3 data, which is noted as outstanding in the Limitations chapter.

=== Complexity Scaling

US-001 is the only pipeline-benchmarking scenario completed at the time of writing; complexity scaling across US-010, US-030, and US-020 is outstanding. A single-scenario dataset cannot distinguish a platform whose overhead is constant from one whose overhead scales with task length---the CrewAI token profile in particular is plausibly either (1) a fixed per-turn surcharge that stays constant as tasks grow or (2) a compounding history-replay cost that would widen the gap on more complex scenarios. The planned intermediate and advanced scenarios are specifically designed to discriminate between these hypotheses, and results against them are the highest-priority outstanding item for the evaluation.

