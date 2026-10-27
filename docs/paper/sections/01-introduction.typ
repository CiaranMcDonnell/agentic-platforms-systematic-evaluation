= Introduction

Agentic platforms---multi-agent frameworks such as LangGraph and CrewAI, vendor SDK runtimes such as OpenAI Agents SDK and Google ADK, and visual workflow builders such as Flowise and n8n---are being adopted to automate the stages of a software engineering pipeline: eliciting requirements, generating code and tests, and building and deploying the result @dong2025survey @wang2024survey. A practitioner choosing among them has surveys of agent architectures @bandi2025rise @jin2024llmagents_se and benchmarks of what a language model can produce @jimenez2024swebench @chen2021humaneval, but little evidence about what the _platform_ contributes once the model is fixed: how reliably it dispatches tools, whether it recovers from a failing build, how much of the token bill is orchestration overhead, and whether it can be observed well enough to tell. Existing comparisons either restrict themselves to one architectural category @broccia2025humainflow, describe architecture without measuring it @derouiche2025agentic, or benchmark a different set of frameworks on isolated tasks @yin2025comprehensive.

Answering that question requires driving architecturally dissimilar platforms through the same multi-stage task under the same conditions, and doing so repeatably. This paper presents `desmet`, an evaluation harness built for that purpose, and the five-platform study that validates it. The harness defines a single adapter contract behind which a graph-based framework, a role-based crew, a manager-driven team, a handoff chain, and a sequential-loop composition all execute the same four-stage pipeline with the same model, prompts, tools, and scoring. Because the model is held constant, the harness's metrics---pipeline completeness, tool-call reliability, error recovery, trace quality, and a redundant-tool-call rate---measure the framework. The methodology follows DESMET @kitchenham1997desmet, combining benchmarking with rubric-based screening.

Two research questions structure the paper.

- *RQ1.* Can a single harness drive architecturally heterogeneous agentic platforms through the same four-stage software engineering pipeline and yield comparable framework-level metrics?
- *RQ2.* What framework-level behaviour does it surface when the model is held constant?

The contributions are:

+ an open evaluation harness with a template-method adapter contract (one platform-specific method per adapter), a four-stage pipeline with real test execution and remote deployment, and per-call token, cost, timing, and trace capture across five SDKs with different instrumentation surfaces (@sec-harness);
+ a framework-centric metric set and DESMET-style rubric, including the redundant-tool-call rate as a stage-level indicator of orchestration pathology and a productive-tool-call guard that prevents false-positive stage success (@sec-framework);
+ an evaluation of five platforms on one task with one model, plus a cross-model repeat, showing a ~2.4× token-cost spread on identical work, that conversation-history policy rather than architectural category predicts that spread, and that a second model exposes fragilities the first does not (@sec-results).

@sec-related positions the work, @sec-framework defines the pipeline and rubric, @sec-harness describes the harness, @sec-setup and @sec-results report the evaluation, @sec-threats discusses validity, and @sec-conclusion concludes.
