// =============================================================================
// UML Activity Diagram — DESMET Agentic Platforms Evaluation Pipeline
// =============================================================================

#import "@preview/fletcher:0.5.7" as fletcher: diagram, node, edge, shapes

#set document(
  title: "DESMET Evaluation Pipeline — UML Activity Diagram",
  author: "Ciaran McDonnell",
)

// First page: landscape for the diagram
#set page(
  paper: "a4",
  flipped: true,
  margin: (left: 0.5cm, right: 0.5cm, top: 0.8cm, bottom: 0.8cm),
  footer: context [
    #set align(center)
    #set text(size: 8pt)
    Page #counter(page).display() of #counter(page).final().first()
  ],
)

#set text(font: "Arial", size: 10pt)

// ── Colours ────────────────────────────────────────────────────────────────────

#let stage-fill    = rgb("#e3f2fd")   // light blue
#let stage-stroke  = rgb("#1565c0")   // dark blue
#let dim-fill      = rgb("#fff8e1")   // light amber
#let dim-stroke    = rgb("#f57f17")   // dark amber
#let dec-fill      = rgb("#e8f5e9")   // light green
#let dec-stroke    = rgb("#2e7d32")   // dark green
#let art-fill      = rgb("#f3e5f5")   // light purple
#let art-stroke    = rgb("#6a1b9a")   // dark purple
#let start-fill    = rgb("#212121")
#let fork-fill     = rgb("#424242")

// ── Title ──────────────────────────────────────────────────────────────────────

#align(center)[
  #text(size: 16pt, weight: "bold")[DESMET Evaluation Pipeline]
  #h(1cm)
  #text(size: 10pt, fill: luma(100))[UML Activity Diagram — Systematic Evaluation of Agentic Platforms]
]

#v(0.2cm)

// ── Diagram ────────────────────────────────────────────────────────────────────

// Use a horizontal layout: stages flow left-to-right

#align(center)[
  #diagram(
    spacing: (0.2cm, 1.1cm),
    node-stroke: 0.8pt,

    // ══════════════════════════════════════════════════════════════════════════
    // ROW 0: Main pipeline flow (left to right)
    // ══════════════════════════════════════════════════════════════════════════

    // Start node
    node(
      (0, 0), [], shape: circle,
      width: 0.5cm, height: 0.5cm,
      fill: start-fill, stroke: none,
    ),

    // Stage 0
    node(
      (1, 0),
      align(center, text(size: 6.5pt, weight: "bold")[Stage 0 \ Framework Setup \ & Onboarding]),
      shape: rect, corner-radius: 5pt, width: 2cm,
      fill: stage-fill, stroke: 1pt + stage-stroke, inset: 4pt,
    ),

    // Decision: Setup OK?
    node(
      (2, 0),
      align(center, text(size: 6pt)[Setup \ Successful?]),
      shape: shapes.diamond, width: 1.5cm, height: 1.2cm,
      fill: dec-fill, stroke: 1pt + dec-stroke, inset: 2pt,
    ),

    // Stage 1
    node(
      (3, 0),
      align(center, text(size: 6.5pt, weight: "bold")[Stage 1 \ Requirements \ Engineering]),
      shape: rect, corner-radius: 5pt, width: 2cm,
      fill: stage-fill, stroke: 1pt + stage-stroke, inset: 4pt,
    ),

    // Stage 2
    node(
      (4, 0),
      align(center, text(size: 6.5pt, weight: "bold")[Stage 2 \ Requirements → \ User Stories]),
      shape: rect, corner-radius: 5pt, width: 2cm,
      fill: stage-fill, stroke: 1pt + stage-stroke, inset: 4pt,
    ),

    // Fork bar (per-platform split)
    node(
      (5, 0), [],
      shape: rect, width: 0.12cm, height: 1.4cm,
      fill: fork-fill, stroke: none,
    ),

    // Stage 3
    node(
      (6, 0),
      align(center, text(size: 6.5pt, weight: "bold")[Stage 3 \ Code Generation \ #text(weight: "regular", style: "italic")[(per platform)]]),
      shape: rect, corner-radius: 5pt, width: 2cm,
      fill: stage-fill, stroke: 1pt + stage-stroke, inset: 4pt,
    ),

    // Stage 4
    node(
      (7, 0),
      align(center, text(size: 6.5pt, weight: "bold")[Stage 4 \ Testing Generation \ #text(weight: "regular", style: "italic")[(per platform)]]),
      shape: rect, corner-radius: 5pt, width: 2cm,
      fill: stage-fill, stroke: 1pt + stage-stroke, inset: 4pt,
    ),

    // Decision: Build Ready?
    node(
      (8, 0),
      align(center, text(size: 6pt)[Build \ Ready?]),
      shape: shapes.diamond, width: 1.5cm, height: 1.2cm,
      fill: dec-fill, stroke: 1pt + dec-stroke, inset: 2pt,
    ),

    // Stage 5
    node(
      (9, 0),
      align(center, text(size: 6.5pt, weight: "bold")[Stage 5 \ Building & \ Deploying]),
      shape: rect, corner-radius: 5pt, width: 2cm,
      fill: stage-fill, stroke: 1pt + stage-stroke, inset: 4pt,
    ),

    // Join bar
    node(
      (10, 0), [],
      shape: rect, width: 0.12cm, height: 1.4cm,
      fill: fork-fill, stroke: none,
    ),

    // Final analysis
    node(
      (11, 0),
      align(center, text(size: 6.5pt, weight: "bold")[Comparative \ Analysis & \ DESMET Report]),
      shape: rect, corner-radius: 5pt, width: 2cm,
      fill: stage-fill, stroke: 1pt + stage-stroke, inset: 4pt,
    ),

    // End node
    node(
      (12, 0), [],
      shape: circle,
      width: 0.5cm, height: 0.5cm,
      fill: start-fill, stroke: 3pt + start-fill,
      outset: 2pt,
    ),

    // ══════════════════════════════════════════════════════════════════════════
    // ROW 1: Output artifacts (below each stage)
    // ══════════════════════════════════════════════════════════════════════════

    node(
      (1, 1),
      align(center)[#text(size: 6pt, fill: art-stroke)[Setup Log \ Dependency Manifest \ Setup Scorecard]],
      shape: rect, corner-radius: 2pt, fill: art-fill, stroke: 0.6pt + art-stroke, inset: 5pt,
    ),

    node(
      (3, 1),
      align(center)[#text(size: 6pt, fill: art-stroke)[Requirements Catalogue \ Traceability Matrix \ Evaluation Plan]],
      shape: rect, corner-radius: 2pt, fill: art-fill, stroke: 0.6pt + art-stroke, inset: 5pt,
    ),

    node(
      (4, 1),
      align(center)[#text(size: 6pt, fill: art-stroke)[Story Backlog \ Gherkin Features \ Scoring Rubrics \ Prompt Templates]],
      shape: rect, corner-radius: 2pt, fill: art-fill, stroke: 0.6pt + art-stroke, inset: 5pt,
    ),

    node(
      (6, 1),
      align(center)[#text(size: 6pt, fill: art-stroke)[Implementation Branches \ Execution Logs \ Metrics Dataset]],
      shape: rect, corner-radius: 2pt, fill: art-fill, stroke: 0.6pt + art-stroke, inset: 5pt,
    ),

    node(
      (7, 1),
      align(center)[#text(size: 6pt, fill: art-stroke)[Test Suites \ Coverage Reports \ CI Logs]],
      shape: rect, corner-radius: 2pt, fill: art-fill, stroke: 0.6pt + art-stroke, inset: 5pt,
    ),

    node(
      (9, 1),
      align(center)[#text(size: 6pt, fill: art-stroke)[Build Artifacts \ Container Images \ Deployment Evidence]],
      shape: rect, corner-radius: 2pt, fill: art-fill, stroke: 0.6pt + art-stroke, inset: 5pt,
    ),

    node(
      (11, 1),
      align(center)[#text(size: 6pt, fill: art-stroke)[DESMET Report \ Dimension Scorecards \ Recommendation Matrix]],
      shape: rect, corner-radius: 2pt, fill: art-fill, stroke: 0.6pt + art-stroke, inset: 5pt,
    ),

    // ══════════════════════════════════════════════════════════════════════════
    // ROW -1: Cross-cutting dimensions (above, spanning the pipeline)
    // ══════════════════════════════════════════════════════════════════════════

    node(
      (6, -1),
      align(center)[
        #text(size: 7pt, weight: "bold", fill: dim-stroke)[Cross-Cutting Evaluation Dimensions (DESMET)]
        #v(3pt)
        #set text(size: 6.5pt)
        #grid(
          columns: (1fr, 1fr, 1fr, 1fr),
          gutter: 6pt,
          [1. Effectiveness], [2. Efficiency], [3. Quality], [4. Reproducibility],
          [5. Usability / DX], [6. Observability], [7. Failure Handling], [],
        )
      ],
      shape: rect, corner-radius: 6pt,
      width: 9cm,
      fill: dim-fill, stroke: 1.2pt + dim-stroke, inset: 8pt,
    ),

    // Dashed arrows from dimensions box to pipeline
    edge((6, -1), (1, 0), "-->", stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.6pt)),
    edge((6, -1), (6, 0), "-->", stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.6pt)),
    edge((6, -1), (11, 0), "-->", stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.6pt)),

    // ══════════════════════════════════════════════════════════════════════════
    // Main flow edges (left to right)
    // ══════════════════════════════════════════════════════════════════════════

    edge((0, 0), (1, 0), "->"),
    edge((1, 0), (2, 0), "->"),

    // Decision: Setup OK
    edge((2, 0), (3, 0), "->", label: text(size: 6pt, fill: dec-stroke)[Yes]),
    edge((2, 0), (1, 0), "->",
      label: text(size: 6pt, fill: red)[No],
      stroke: 0.7pt + red,
      bend: -40deg,
    ),

    edge((3, 0), (4, 0), "->"),
    edge((4, 0), (5, 0), "->"),
    edge((5, 0), (6, 0), "->"),
    edge((6, 0), (7, 0), "->"),
    edge((7, 0), (8, 0), "->"),

    // Decision: Build Ready
    edge((8, 0), (9, 0), "->", label: text(size: 6pt, fill: dec-stroke)[Yes]),
    edge((8, 0), (6, 0), "->",
      label: text(size: 6pt, fill: red)[No],
      stroke: 0.7pt + red,
      bend: -40deg,
    ),

    edge((9, 0), (10, 0), "->"),
    edge((10, 0), (11, 0), "->"),
    edge((11, 0), (12, 0), "->"),

    // ══════════════════════════════════════════════════════════════════════════
    // Artifact edges (dashed, downward)
    // ══════════════════════════════════════════════════════════════════════════

    edge((1, 0), (1, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.5pt)),
    edge((3, 0), (3, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.5pt)),
    edge((4, 0), (4, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.5pt)),
    edge((6, 0), (6, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.5pt)),
    edge((7, 0), (7, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.5pt)),
    edge((9, 0), (9, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.5pt)),
    edge((11, 0), (11, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.5pt)),
  )
]

#v(0.3cm)

// ── Legend ──────────────────────────────────────────────────────────────────────

#line(length: 100%, stroke: 0.4pt + luma(180))
#v(0.15cm)

#grid(
  columns: (auto, 1fr, 1fr, 1fr),
  gutter: 0.6cm,
  align: (left + horizon,) * 4,
  [#text(size: 8pt, weight: "bold")[Legend:]],
  [
    #box(width: 0.7cm, height: 0.4cm, fill: stage-fill, stroke: 0.8pt + stage-stroke, radius: 4pt)
    #text(size: 7pt)[ Pipeline Stage]
    #h(0.6cm)
    #box(width: 0.7cm, height: 0.4cm, fill: dec-fill, stroke: 0.8pt + dec-stroke)
    #text(size: 7pt)[ Decision Gate]
  ],
  [
    #box(width: 0.7cm, height: 0.4cm, fill: art-fill, stroke: 0.8pt + art-stroke, radius: 2pt)
    #text(size: 7pt)[ Output Artifact]
    #h(0.6cm)
    #box(width: 0.7cm, height: 0.4cm, fill: dim-fill, stroke: 0.8pt + dim-stroke, radius: 4pt)
    #text(size: 7pt)[ Cross-cutting Dimension]
  ],
  [
    #box(width: 0.7cm, height: 0.15cm, fill: fork-fill, radius: 0pt)
    #text(size: 7pt)[ Fork / Join (parallel)]
    #h(0.6cm)
    #text(size: 7pt, fill: luma(120))[--- Produces →]
  ],
)

#v(0.15cm)

#grid(
  columns: (1fr, 1fr, 1fr),
  gutter: 0.4cm,
  [
    #text(size: 6.5pt, weight: "bold")[Multi-Agent Frameworks] \
    #text(size: 7pt)[LangGraph · CrewAI · AutoGen]
  ],
  [
    #text(size: 6.5pt, weight: "bold")[Agent SDK Runtimes] \
    #text(size: 7pt)[OpenAI Agents SDK · Google ADK · Semantic Kernel]
  ],
  [
    #text(size: 6.5pt, weight: "bold")[Visual / Workflow Platforms] \
    #text(size: 7pt)[Flowise · LangFlow · Dify · N8n]
  ],
)

// ═══════════════════════════════════════════════════════════════════════════════
// Page 2: Stage Detail Reference
// ═══════════════════════════════════════════════════════════════════════════════

#pagebreak()

#set page(flipped: false, margin: (left: 2cm, right: 2cm, top: 2cm, bottom: 2cm))

#align(center)[
  #text(size: 16pt, weight: "bold")[Pipeline Stage Detail]
  #v(0.1cm)
  #text(size: 10pt, fill: luma(100))[Metrics, Inputs & Outputs per Stage]
  #v(0.1cm)
  #line(length: 7cm, stroke: 0.5pt + luma(160))
]

#v(0.4cm)

#table(
  columns: (2.5cm, 1fr, 1fr),
  align: (left, left, left),
  stroke: 0.5pt + luma(180),
  inset: 7pt,

  table.cell(fill: luma(230))[#text(weight: "bold", size: 8pt)[Stage]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 8pt)[Key Metrics]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 8pt)[Key Outputs]],

  [#text(weight: "bold", size: 7.5pt)[0 — Setup & \ Onboarding]],
  [#text(size: 7pt)[
    - Time to environment ready (min) \
    - Time to first agent (min) \
    - Manual steps required \
    - Documentation clarity (1–5) \
    - Errors encountered \
    - Dependencies count
  ]],
  [#text(size: 7pt)[
    - Setup log (timestamped) \
    - Dependency manifest (JSON) \
    - First working agent code \
    - Setup scorecard
  ]],

  [#text(weight: "bold", size: 7.5pt)[1 — Requirements \ Engineering]],
  [#text(size: 7pt)[
    - Requirements completeness \
    - Traceability coverage \
    - Stakeholder alignment \
    - Priority distribution
  ]],
  [#text(size: 7pt)[
    - Scope definition document \
    - Functional requirements catalogue \
    - Non-functional requirements \
    - Traceability matrix \
    - Evaluation plan
  ]],

  [#text(weight: "bold", size: 7.5pt)[2 — Requirements \ → User Stories]],
  [#text(size: 7pt)[
    - Story coverage (% of reqs) \
    - Acceptance criteria count \
    - Difficulty distribution \
    - Constraint standardisation
  ]],
  [#text(size: 7pt)[
    - Story backlog \
    - Gherkin feature files \
    - Scoring rubrics \
    - Baseline repository \
    - Prompt templates
  ]],

  [#text(weight: "bold", size: 7.5pt)[3 — Code \ Generation]],
  [#text(size: 7pt)[
    - Correctness score (0–3) \
    - Completeness score (0–3) \
    - Code quality score (0–3) \
    - Iterations to completion \
    - Wall-clock time (s) \
    - Tokens consumed \
    - Human interventions \
    - Acceptance tests passed (%)
  ]],
  [#text(size: 7pt)[
    - Implementation branches \
    - Execution logs (agent traces) \
    - Run reports (JSON + MD) \
    - Metrics dataset (CSV/JSON) \
    - Git commit history
  ]],

  [#text(weight: "bold", size: 7.5pt)[4 — Testing \ Generation]],
  [#text(size: 7pt)[
    - Tests generated (count) \
    - Tests passing (count) \
    - Coverage delta (%) \
    - Flaky tests (count) \
    - Test quality score (0–3) \
    - Assertions per test (avg)
  ]],
  [#text(size: 7pt)[
    - Test suites \
    - Test quality assessment \
    - Coverage reports (before/after) \
    - CI logs
  ]],

  [#text(weight: "bold", size: 7.5pt)[5 — Building & \ Deploying]],
  [#text(size: 7pt)[
    - Build success rate (%) \
    - CI pass rate (%) \
    - Build time (s) \
    - Container build (pass/fail) \
    - Secrets exposed (count)
  ]],
  [#text(size: 7pt)[
    - Build artifacts \
    - Container images \
    - CI pipeline logs \
    - Deployment evidence \
    - Operational notes
  ]],
)

#v(0.5cm)

// ── Cross-cutting dimensions detail ──

#text(size: 12pt, weight: "bold")[Cross-Cutting Evaluation Dimensions]
#v(0.15cm)
#text(size: 9pt, fill: luma(80))[Evaluated continuously across all pipeline stages (DESMET methodology)]
#v(0.25cm)

#table(
  columns: (0.5cm, 2.8cm, 1fr),
  align: (center, left, left),
  stroke: 0.5pt + luma(180),
  inset: 7pt,

  table.cell(fill: dim-fill)[#text(weight: "bold", size: 7.5pt)[\#]],
  table.cell(fill: dim-fill)[#text(weight: "bold", size: 7.5pt)[Dimension]],
  table.cell(fill: dim-fill)[#text(weight: "bold", size: 7.5pt)[What Is Measured]],

  [1], [#text(weight: "bold", size: 7.5pt)[Effectiveness]],
  [#text(size: 7pt)[Task completion rate, functional correctness, requirement coverage, goal achievement]],

  [2], [#text(weight: "bold", size: 7.5pt)[Efficiency]],
  [#text(size: 7pt)[Time per task, tokens consumed, agent turns, human effort, cost per successful task]],

  [3], [#text(weight: "bold", size: 7.5pt)[Quality]],
  [#text(size: 7pt)[Code quality rubric scores, test quality, documentation quality, maintainability]],

  [4], [#text(weight: "bold", size: 7.5pt)[Reproducibility]],
  [#text(size: 7pt)[Determinism (same input → same output), consistency variance, version stability, env independence]],

  [5], [#text(weight: "bold", size: 7.5pt)[Usability / DX]],
  [#text(size: 7pt)[Learning curve, documentation clarity, error message helpfulness, IDE integration, API intuitiveness]],

  [6], [#text(weight: "bold", size: 7.5pt)[Observability]],
  [#text(size: 7pt)[State visibility, decision transparency, tool-call visibility, step-through debugging, replay capability]],

  [7], [#text(weight: "bold", size: 7.5pt)[Failure Handling]],
  [#text(size: 7pt)[Failure detection, self-correction, graceful degradation, human handoff, state recovery, idempotency]],
)

#v(0.5cm)

// ── Scoring & Weighting ──

#text(size: 12pt, weight: "bold")[Dimension Weighting by Scenario]
#v(0.2cm)

#table(
  columns: (2.8cm, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr, 1fr),
  align: (left, center, center, center, center, center, center, center),
  stroke: 0.5pt + luma(180),
  inset: 5pt,

  table.cell(fill: luma(230))[#text(weight: "bold", size: 7pt)[Scenario]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 7pt)[Eff.]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 7pt)[Effi.]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 7pt)[Qual.]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 7pt)[Repr.]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 7pt)[Usab.]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 7pt)[Obs.]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 7pt)[Fail.]],

  [#text(size: 7pt)[Default]],
  [#text(size: 7pt)[1.0]], [#text(size: 7pt)[1.0]], [#text(size: 7pt)[1.0]],
  [#text(size: 7pt)[1.0]], [#text(size: 7pt)[1.0]], [#text(size: 7pt)[1.0]], [#text(size: 7pt)[1.0]],

  [#text(size: 7pt)[Rapid Prototyping]],
  [#text(size: 7pt)[1.5]], [#text(size: 7pt)[1.5]], [#text(size: 7pt)[0.5]],
  [#text(size: 7pt)[0.5]], [#text(size: 7pt)[1.5]], [#text(size: 7pt)[0.5]], [#text(size: 7pt)[0.5]],

  [#text(size: 7pt)[Production Deploy]],
  [#text(size: 7pt)[1.0]], [#text(size: 7pt)[0.5]], [#text(size: 7pt)[1.5]],
  [#text(size: 7pt)[1.5]], [#text(size: 7pt)[0.5]], [#text(size: 7pt)[1.5]], [#text(size: 7pt)[1.5]],

  [#text(size: 7pt)[Research / Exp.]],
  [#text(size: 7pt)[1.5]], [#text(size: 7pt)[0.5]], [#text(size: 7pt)[0.5]],
  [#text(size: 7pt)[1.5]], [#text(size: 7pt)[1.0]], [#text(size: 7pt)[1.5]], [#text(size: 7pt)[0.5]],
)

#v(0.2cm)
#align(center)[
  #text(size: 8pt, fill: luma(120))[
    Overall Score = Σ (Dimension Score × Weight) / Σ Weights
  ]
]
