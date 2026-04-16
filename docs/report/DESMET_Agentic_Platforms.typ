// =============================================================================
// UCD CS FYP Report — Entry Point (compile this file)
// Systematic Evaluation of Agentic Platforms
// =============================================================================

#import "template.typ": *

#show: template

// ---------------------------------------------------------------------------
// Title page
// ---------------------------------------------------------------------------

#page(header: [], footer: [])[
  #set align(center)
  #v(1fr)

  #text(size: 24pt)[Final Year Project]
  #v(0.5cm)
  #line(length: 4cm, stroke: 1pt)
  #v(0.7cm)
  #text(size: 24pt, weight: "bold")[#project-title]
  #v(1cm)

  #text(size: 18pt)[#student-name]
  #v(0.5cm)
  #line(length: 4cm, stroke: 1pt)
  #v(0.5cm)
  #text(size: 16pt)[Student ID: #student-id]
  #v(0.5cm)
  #line(length: 4cm, stroke: 1pt)
  #v(0.5cm)

  #text(size: 16pt)[
    A thesis submitted in part fulfilment of the degree of \
    #text(weight: "bold")[BSc. (Hons.) in Computer Science]
  ]
  #v(0.5cm)
  #text(size: 16pt)[#text(weight: "bold")[Supervisor:] #supervisor-name]
  #v(1.8cm)

  #image("UCD_Logo.pdf", height: 6cm)
  #v(1cm)

  #text(size: 16pt)[
    UCD School of Computer Science \
    University College Dublin
  ]
  #v(1fr)
  #text(size: 12pt)[March 2026]
  #v(1fr)
]

// ---------------------------------------------------------------------------
// Front matter (roman numeral page numbering)
// ---------------------------------------------------------------------------

#set page(numbering: "I")
#counter(page).update(1)

#outline(title: "Table of Contents", depth: 3, indent: auto)

#heading(level: 1, numbering: none)[Abstract]

Agentic platforms are emerging as transformative tools in software engineering, integrating autonomous or semi-autonomous agents into the development lifecycle to enhance productivity and workflow automation. However, existing literature provides limited comparative evaluation across heterogeneous agentic frameworks, multi-agent systems, and workflow-based LLM platforms, leaving practitioners without clear guidance for tool selection. This study applies a systematic DESMET-based evaluation framework to compare agentic platforms using a three-layer approach: industry readiness assessment, platform characteristic mapping (extending Broccia et al.'s system-level and interaction-level feature analysis), and pipeline-based benchmarking across a four-stage software engineering workflow (requirements and design, code generation, test generation, and build and deployment). The evaluation covers nine platforms representing three architectural categories: multi-agent frameworks (LangGraph, CrewAI), agent SDK runtimes (OpenAI Agents SDK, Google ADK, Microsoft Agent Framework), and visual workflow platforms (Flowise, LangFlow, Dify, N8n). Each platform is assessed by executing user stories of increasing complexity through the pipeline, with metrics focusing on framework capability: pipeline completeness, orchestration quality (tool integration, error recovery, trace fidelity), efficiency (token and time overhead), and degree of autonomy. The results aim to provide practical guidance for practitioners, highlight capability gaps across different tool categories, and offer a structured methodology for evaluating emerging agentic technologies.

// ---------------------------------------------------------------------------
// Body matter (arabic page numbering, reset to 1)
// ---------------------------------------------------------------------------

#set page(numbering: "1")
#counter(page).update(1)

#include "chapters/introduction.typ"
#include "chapters/related-work.typ"
#include "chapters/approach-and-design.typ"
#include "chapters/implementation.typ"
#include "chapters/evaluation-method.typ"
#include "chapters/evaluation.typ"
#include "chapters/limitations.typ"
#include "chapters/conclusions.typ"

// ---------------------------------------------------------------------------
// Acknowledgements
// ---------------------------------------------------------------------------

#heading(level: 1, numbering: none)[Acknowledgements]

// ---------------------------------------------------------------------------
// Bibliography
// ---------------------------------------------------------------------------

// Keep DOI links the same color as body text in the bibliography
#show bibliography: it => {
  show link: set text(fill: black)
  it
}
#bibliography("references.bib", style: "springer-mathphys")

// ---------------------------------------------------------------------------
// Appendices
// ---------------------------------------------------------------------------

#set heading(numbering: "A.1")
#counter(heading).update(0)

#include "chapters/appendix-getting-started.typ"
#include "chapters/appendix-scoring-rubric.typ"
#include "chapters/appendix-adding-adapter.typ"
#include "chapters/appendix-deploy-setup.typ"
