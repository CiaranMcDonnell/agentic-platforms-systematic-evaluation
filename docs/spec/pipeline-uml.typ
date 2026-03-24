// =============================================================================
// UML Activity Diagram — DESMET Agentic Platforms Evaluation Pipeline
// Updated to match three-layer evaluation framework (4 stages, 4 dimensions)
// =============================================================================

#import "@preview/fletcher:0.5.7" as fletcher: diagram, node, edge, shapes

#set document(
  title: "DESMET Evaluation Pipeline — UML Activity Diagram",
  author: "Ciaran McDonnell",
)

#set page(
  paper: "a4",
  flipped: true,
  margin: (left: 0.3cm, right: 0.3cm, top: 0.6cm, bottom: 0.6cm),
  footer: context [
    #set align(center)
    #set text(size: 8pt)
    Page #counter(page).display() of #counter(page).final().first()
  ],
)

#set text(font: "Arial", size: 10pt)

// ── Colours ────────────────────────────────────────────────────────────────────

#let stage-fill    = rgb("#e3f2fd")
#let stage-stroke  = rgb("#1565c0")
#let dim-fill      = rgb("#fff8e1")
#let dim-stroke    = rgb("#f57f17")
#let dec-fill      = rgb("#e8f5e9")
#let dec-stroke    = rgb("#2e7d32")
#let art-fill      = rgb("#f3e5f5")
#let art-stroke    = rgb("#6a1b9a")
#let start-fill    = rgb("#212121")
#let fork-fill     = rgb("#424242")
#let pp-fill       = rgb("#fff3e0")
#let pp-stroke     = rgb("#e65100")

// ── Shared sizes ─────────────────────────────────────────────────────────────

#let nw  = 1.8cm    // shared-stage node width
#let ppw = 1.5cm    // per-platform node width
#let dw  = 1.3cm    // diamond width
#let dh  = 1.05cm   // diamond height
#let ns  = 6.5pt    // shared node text size
#let pps = 5.5pt    // per-platform text size
#let ds  = 5.5pt    // decision text size
#let art-s = 5pt    // artifact text size

// ── Title ──────────────────────────────────────────────────────────────────────

#align(center)[
  #text(size: 14pt, weight: "bold")[DESMET Evaluation Pipeline]
  #h(0.8cm)
  #text(size: 9pt, fill: luma(100))[UML Activity Diagram — Systematic Evaluation of Agentic Platforms]
]

#v(0.15cm)

// ── Diagram ────────────────────────────────────────────────────────────────────
//
// Grid layout (x positions):
//   0   1   [2 3]   4    5    6    7   [8 9]  10  [11 12]  13   14  [15]  16   17
//   ●  Inp   ···   Fork  S1   S2   S3   ···   Dec  ····    S4  Join   ·   An    ●
//

#align(center)[
  #diagram(
    spacing: (0.25cm, 0.85cm),
    node-stroke: 0.7pt,

    // ══════════════════════════════════════════════════════════════════════
    // Spacer nodes at y=2 — create extra grid columns for wider gaps
    // S1(5)→S2(6)→S3(7) have NO spacers = tight cluster
    // ══════════════════════════════════════════════════════════════════════
    node((2, 2), [], stroke: none, fill: none, width: 0.01cm, height: 0.01cm),
    node((3, 2), [], stroke: none, fill: none, width: 0.01cm, height: 0.01cm),
    node((8, 2), [], stroke: none, fill: none, width: 0.01cm, height: 0.01cm),
    node((9, 2), [], stroke: none, fill: none, width: 0.01cm, height: 0.01cm),
    node((11, 2), [], stroke: none, fill: none, width: 0.01cm, height: 0.01cm),
    node((12, 2), [], stroke: none, fill: none, width: 0.01cm, height: 0.01cm),
    node((15, 2), [], stroke: none, fill: none, width: 0.01cm, height: 0.01cm),

    // ── Parallel region label ──
    node((9, 0.48),
      text(size: 6.5pt, weight: "bold", fill: pp-stroke)[Per-Platform Parallel Execution (×10 platforms × 4 stories)],
      stroke: none, fill: none),

    // ══════════════════════════════════════════════════════════════════════
    // ROW 0 — Main pipeline
    // ══════════════════════════════════════════════════════════════════════

    node((0, 0), [], shape: circle, width: 0.4cm, height: 0.4cm,
      fill: start-fill, stroke: none),

    node((1, 0),
      align(center, text(size: ns, weight: "bold")[Story Input \ #text(weight: "regular", size: 5pt)[(YAML loading, \ context preparation)]]),
      shape: rect, corner-radius: 4pt, width: nw,
      fill: stage-fill, stroke: 0.8pt + stage-stroke, inset: 3pt),

    node((4, 0), [], shape: rect, width: 0.1cm, height: 1.1cm,
      fill: fork-fill, stroke: none),

    node((5, 0),
      align(center, text(size: pps, weight: "bold")[Stage 1 \ Requirements \ & Design]),
      shape: rect, corner-radius: 4pt, width: ppw,
      fill: pp-fill, stroke: 0.8pt + pp-stroke, inset: 3pt),

    // Stage 2 — Code Generation (per-platform)
    node((6, 0),
      align(center, text(size: pps, weight: "bold")[Stage 2 \ Code \ Generation]),
      shape: rect, corner-radius: 4pt, width: ppw,
      fill: pp-fill, stroke: 0.8pt + pp-stroke, inset: 3pt),

    // Stage 3 — Test Generation (per-platform)
    node((7, 0),
      align(center, text(size: pps, weight: "bold")[Stage 3 \ Test \ Generation]),
      shape: rect, corner-radius: 4pt, width: ppw,
      fill: pp-fill, stroke: 0.8pt + pp-stroke, inset: 3pt),

    // Decision: Build Ready?
    node((10, 0),
      align(center, text(size: ds)[Build \ Ready?]),
      shape: shapes.diamond, width: dw, height: dh,
      fill: dec-fill, stroke: 0.8pt + dec-stroke, inset: 2pt),

    // Stage 4 — Build & Deploy (per-platform)
    node((13, 0),
      align(center, text(size: pps, weight: "bold")[Stage 4 \ Build & \ Deploy]),
      shape: rect, corner-radius: 4pt, width: ppw,
      fill: pp-fill, stroke: 0.8pt + pp-stroke, inset: 3pt),

    // Join bar
    node((14, 0), [], shape: rect, width: 0.1cm, height: 1.1cm,
      fill: fork-fill, stroke: none),

    // Comparative Analysis — shared
    node((16, 0),
      align(center, text(size: ns, weight: "bold")[Comparative \ Analysis & \ DESMET Report]),
      shape: rect, corner-radius: 4pt, width: nw,
      fill: stage-fill, stroke: 0.8pt + stage-stroke, inset: 3pt),

    // End
    node((17, 0), [], shape: circle, width: 0.4cm, height: 0.4cm,
      fill: start-fill, stroke: 2.5pt + start-fill, outset: 2pt),

    // ══════════════════════════════════════════════════════════════════════
    // ROW 1 — Artifacts
    // ══════════════════════════════════════════════════════════════════════

    node((1, 1),
      align(center)[#text(size: art-s, fill: art-stroke)[Story Backlog (YAML) \ Gherkin Features \ Prompt Templates]],
      shape: rect, corner-radius: 2pt, width: nw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

    node((5, 1),
      align(center)[#text(size: art-s, fill: art-stroke)[Requirements \ Acceptance Criteria \ UML Diagrams (PlantUML)]],
      shape: rect, corner-radius: 2pt, width: ppw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

    node((6, 1),
      align(center)[#text(size: art-s, fill: art-stroke)[Source Code \ Execution Logs \ Token Usage Data]],
      shape: rect, corner-radius: 2pt, width: ppw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

    node((7, 1),
      align(center)[#text(size: art-s, fill: art-stroke)[Test Suites \ Coverage Reports \ Test Pass Rates]],
      shape: rect, corner-radius: 2pt, width: ppw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

    node((13, 1),
      align(center)[#text(size: art-s, fill: art-stroke)[Build Artifacts \ Deploy Evidence \ Health Checks]],
      shape: rect, corner-radius: 2pt, width: ppw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

    node((16, 1),
      align(center)[#text(size: art-s, fill: art-stroke)[Dimension Scores \ Feature Matrices \ Radar Charts]],
      shape: rect, corner-radius: 2pt, width: nw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

    // ══════════════════════════════════════════════════════════════════════
    // ROW -1 — Cross-cutting dimensions (Layer 3)
    // ══════════════════════════════════════════════════════════════════════

    node((9, -1),
      align(center)[
        #text(size: 7pt, weight: "bold", fill: dim-stroke)[Layer 3 Cross-Cutting Dimensions]
        #v(2pt)
        #set text(size: 6.5pt)
        #grid(
          columns: (1fr, 1fr, 1fr, 1fr),
          gutter: 6pt,
          [1. Effectiveness], [2. Efficiency], [3. Quality], [4. Autonomy],
        )
      ],
      shape: rect, corner-radius: 5pt, width: 7cm,
      fill: dim-fill, stroke: 1pt + dim-stroke, inset: 6pt),

    // Dashed arrows from dimensions to pipeline stages
    edge((9, -1), (5, 0), "-->", stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.5pt)),
    edge((9, -1), (7, 0), "-->", stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.5pt)),
    edge((9, -1), (13, 0), "-->", stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.5pt)),
    edge((9, -1), (16, 0), "-->", stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.5pt)),

    // ══════════════════════════════════════════════════════════════════════
    // Edges — Main flow
    // ══════════════════════════════════════════════════════════════════════

    edge((0, 0), (1, 0), "->"),
    edge((1, 0), (4, 0), "->"),
    edge((4, 0), (5, 0), "->"),
    edge((5, 0), (6, 0), "->"),
    edge((6, 0), (7, 0), "->"),
    edge((7, 0), (10, 0), "->"),

    edge((10, 0), (13, 0), "->",
      label: text(size: 5pt, fill: dec-stroke)[Yes], label-side: left),
    edge((10, 0), (6, 0), "->",
      label: text(size: 5pt, fill: red)[No], stroke: 0.6pt + red, bend: -40deg),

    edge((13, 0), (14, 0), "->"),
    edge((14, 0), (16, 0), "->"),
    edge((16, 0), (17, 0), "->"),

    // Artifact edges
    edge((1, 0), (1, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
    edge((5, 0), (5, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
    edge((6, 0), (6, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
    edge((7, 0), (7, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
    edge((13, 0), (13, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
    edge((16, 0), (16, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
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
    #box(width: 0.6cm, height: 0.35cm, fill: stage-fill, stroke: 0.7pt + stage-stroke, radius: 3pt)
    #text(size: 7pt)[ Shared / Harness]
    #h(0.5cm)
    #box(width: 0.6cm, height: 0.35cm, fill: pp-fill, stroke: 0.7pt + pp-stroke, radius: 3pt)
    #text(size: 7pt)[ Per-platform Stage]
  ],
  [
    #box(width: 0.6cm, height: 0.35cm, fill: dec-fill, stroke: 0.7pt + dec-stroke)
    #text(size: 7pt)[ Decision Gate]
    #h(0.5cm)
    #box(width: 0.6cm, height: 0.35cm, fill: art-fill, stroke: 0.7pt + art-stroke, radius: 2pt)
    #text(size: 7pt)[ Output Artifact]
  ],
  [
    #box(width: 0.6cm, height: 0.12cm, fill: fork-fill, radius: 0pt)
    #text(size: 7pt)[ Fork / Join (parallel)]
    #h(0.5cm)
    #box(width: 0.6cm, height: 0.35cm, fill: dim-fill, stroke: 0.7pt + dim-stroke, radius: 3pt)
    #text(size: 7pt)[ Cross-cutting Dimension]
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
  #text(size: 10pt, fill: luma(100))[Per-Stage Metrics and Outputs — Layer 3 Benchmarking]
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
  table.cell(fill: luma(230))[#text(weight: "bold", size: 8pt)[Stage-Specific Metrics]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 8pt)[Key Outputs]],

  [#text(weight: "bold", size: 7.5pt)[1 — Requirements \ & Design]],
  [#text(size: 7pt)[
    - Requirement completeness (%) \
    - Requirement quality (rubric 0–3) \
    - Traceability (rubric 0–3) \
    - Design completeness (rubric 0–3) \
    - Design correctness (rubric 0–3) \
    - Parseable UML (binary)
  ]],
  [#text(size: 7pt)[
    - Structured requirements \
    - Acceptance criteria \
    - UML class diagrams (PlantUML) \
    - UML sequence diagrams
  ]],

  [#text(weight: "bold", size: 7.5pt)[2 — Code \ Generation]],
  [#text(size: 7pt)[
    - Functional correctness (binary) \
    - Completeness (%) \
    - Code quality (rubric 0–3) \
    - Adherence to design (rubric 0–3)
  ]],
  [#text(size: 7pt)[
    - Source code files \
    - Execution logs \
    - Agent traces
  ]],

  [#text(weight: "bold", size: 7.5pt)[3 — Test \ Generation]],
  [#text(size: 7pt)[
    - Test pass rate (%) \
    - Test coverage (%) \
    - Test quality (rubric 0–3)
  ]],
  [#text(size: 7pt)[
    - Test suites \
    - Coverage reports \
    - Test execution logs
  ]],

  [#text(weight: "bold", size: 7.5pt)[4 — Build & \ Deploy]],
  [#text(size: 7pt)[
    - Build success (binary) \
    - Deploy success (binary) \
    - Configuration effort (rubric 0–3)
  ]],
  [#text(size: 7pt)[
    - Build artifacts \
    - Container images \
    - Health check evidence
  ]],
)

#v(0.2cm)

#align(center)[
  #text(size: 8pt, fill: luma(100))[
    All stages also record: token usage (input/output/total), API cost (USD), wall-clock time (s), human interventions (count)
  ]
]

#v(0.3cm)

#text(size: 12pt, weight: "bold")[Cross-Cutting Evaluation Dimensions]
#v(0.1cm)
#text(size: 9pt, fill: luma(80))[Aggregated from per-stage metrics — Layer 3 benchmarking scores (1–5 Likert scale)]
#v(0.15cm)

#table(
  columns: (0.5cm, 2.5cm, 1fr, 1fr),
  align: (center, left, left, left),
  stroke: 0.5pt + luma(180),
  inset: 7pt,

  table.cell(fill: dim-fill)[#text(weight: "bold", size: 7.5pt)[\#]],
  table.cell(fill: dim-fill)[#text(weight: "bold", size: 7.5pt)[Dimension]],
  table.cell(fill: dim-fill)[#text(weight: "bold", size: 7.5pt)[What Is Measured]],
  table.cell(fill: dim-fill)[#text(weight: "bold", size: 7.5pt)[Aggregation Formula]],

  [1], [#text(weight: "bold", size: 7.5pt)[Effectiveness]],
  [#text(size: 7pt)[Capability tier, correctness, completeness across all stages]],
  [#text(size: 6.5pt)[$(S_"supported" / S_"total") times 0.4 + overline(C_"correct") times 0.3 + overline(C_"complete") times 0.3$\ scaled to 1–5]],

  [2], [#text(weight: "bold", size: 7.5pt)[Efficiency]],
  [#text(size: 7pt)[Token usage, wall-clock time, API cost]],
  [#text(size: 6.5pt)[Rank-normalised across platforms:\ lowest resource consumption = 5]],

  [3], [#text(weight: "bold", size: 7.5pt)[Quality]],
  [#text(size: 7pt)[All qualitative rubric scores (0–3) across stages]],
  [#text(size: 6.5pt)[$overline(R_"all") times 5 / 3$]],

  [4], [#text(weight: "bold", size: 7.5pt)[Autonomy]],
  [#text(size: 7pt)[Human interventions across all stages]],
  [#text(size: 6.5pt)[$5 - min(4, overline(I_"per-stage"))$]],
)

#v(0.3cm)

#text(size: 12pt, weight: "bold")[Three-Layer Framework Summary]
#v(0.15cm)

#table(
  columns: (2.5cm, 2cm, 1fr, 1fr),
  align: (left, left, left, left),
  stroke: 0.5pt + luma(180),
  inset: 6pt,

  table.cell(fill: luma(230))[#text(weight: "bold", size: 7.5pt)[Layer]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 7.5pt)[Scale]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 7.5pt)[Method]],
  table.cell(fill: luma(230))[#text(weight: "bold", size: 7.5pt)[Practitioner Question]],

  [#text(size: 7pt)[Layer 1 — Industry Readiness]],
  [#text(size: 7pt)[Factual profile]],
  [#text(size: 7pt)[Desk research, GitHub data, documentation review]],
  [#text(size: 7pt, style: "italic")[Should I consider it?]],

  [#text(size: 7pt)[Layer 2 — Platform Characteristics]],
  [#text(size: 7pt)[Yes / Partial / No]],
  [#text(size: 7pt)[Documentation review + hands-on verification]],
  [#text(size: 7pt, style: "italic")[What can it do?]],

  [#text(size: 7pt)[Layer 3 — Pipeline Benchmarking]],
  [#text(size: 7pt)[1–5 Likert]],
  [#text(size: 7pt)[Automated pipeline execution + qualitative rubric scoring]],
  [#text(size: 7pt, style: "italic")[How well does it do it?]],
)

#v(0.15cm)

#align(center)[
  #text(size: 8pt, fill: luma(120))[
    Layer 3 Overall Score = average(Effectiveness, Efficiency, Quality, Autonomy)
    · Sensitivity analysis explores alternative weightings for different practitioner scenarios
  ]
]
