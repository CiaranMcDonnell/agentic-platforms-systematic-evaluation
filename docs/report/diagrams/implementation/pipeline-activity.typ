// Pipeline Activity Diagram — injected into report via #include
// Renders on a landscape page, then reverts to portrait

#import "@preview/fletcher:0.5.7" as fletcher: diagram, node, edge, shapes

// ── Colours (muted, print-safe academic palette) ────────────────────────────

#let stage-fill    = rgb("#DCE7F1")  // muted blue
#let stage-stroke  = rgb("#2C5282")
#let dim-fill      = rgb("#F5EBC8")  // ochre
#let dim-stroke    = rgb("#A8851F")
#let dec-fill      = rgb("#D4E4D0")  // sage
#let dec-stroke    = rgb("#4A7A3F")
#let art-fill      = rgb("#E4DAEA")  // dusty purple
#let art-stroke    = rgb("#6B4B8A")
#let start-fill    = rgb("#2D3748")
#let fork-fill     = rgb("#4A5568")
#let pp-fill       = rgb("#F5E1C8")  // muted terracotta
#let pp-stroke     = rgb("#B8691F")
#let retry-stroke  = rgb("#A0413A")  // brick red for feedback loop

#let nw  = 2.8cm     // shared-stage node width
#let ppw = 2.4cm     // per-platform node width
#let dw  = 1.5cm     // diamond width
#let dh  = 1.1cm     // diamond height
#let ns  = 7pt       // shared node text size
#let pps = 6.5pt     // per-platform text size
#let ds  = 6pt       // decision text size
#let art-s = 5.5pt   // artifact text size

#page(flipped: true, margin: (left: 1.5cm, right: 1.5cm, top: 1.5cm, bottom: 1.5cm))[

#figure(
  kind: image,
  [
    // Grid layout — tighter, no unnecessary spacer gaps:
    //  0    1   [2]   3    4    5    6    7   [8]   9    10   [11]  12    13
    //  ●   Inp   ·   Fork  S1   S2   S3  Dec   ·   S4  Join   ·   An    ●

    #align(center)[
      #diagram(
        spacing: (0.35cm, 0.9cm),
        node-stroke: 0.7pt,

        // Spacer nodes — only where needed for visual breathing room
        node((2, 2), [], stroke: none, fill: none, width: 0.01cm, height: 0.01cm),
        node((8, 2), [], stroke: none, fill: none, width: 0.01cm, height: 0.01cm),
        node((11, 2), [], stroke: none, fill: none, width: 0.01cm, height: 0.01cm),

        // ── ROW 0 — Main pipeline ──────────────────────────────────────

        // Start
        node((0, 0), [], shape: circle, width: 0.45cm, height: 0.45cm,
          fill: start-fill, stroke: none),

        // Scenario Input — shared harness infrastructure
        node((1, 0),
          align(center, text(size: ns, weight: "bold")[Scenario Input \ #text(weight: "regular", size: 5.5pt)[(YAML loading, context prep.)]]),
          shape: rect, corner-radius: 4pt, width: nw,
          fill: stage-fill, stroke: 0.8pt + stage-stroke, inset: 4pt),

        // Fork bar
        node((3, 0), [], shape: rect, width: 0.12cm, height: 1.3cm,
          fill: fork-fill, stroke: none),

        // Stage 1 — Requirements & Design
        node((4, 0),
          align(center, text(size: pps, weight: "bold")[Stage 1 \ Requirements \ & Design]),
          shape: rect, corner-radius: 4pt, width: ppw,
          fill: pp-fill, stroke: 0.8pt + pp-stroke, inset: 4pt),

        // Stage 2 — Code Generation
        node((5, 0),
          align(center, text(size: pps, weight: "bold")[Stage 2 \ Code \ Generation]),
          shape: rect, corner-radius: 4pt, width: ppw,
          fill: pp-fill, stroke: 0.8pt + pp-stroke, inset: 4pt),

        // Stage 3 — Test Generation
        node((6, 0),
          align(center, text(size: pps, weight: "bold")[Stage 3 \ Test \ Generation]),
          shape: rect, corner-radius: 4pt, width: ppw,
          fill: pp-fill, stroke: 0.8pt + pp-stroke, inset: 4pt),

        // Decision: Build Ready?
        node((7, 0),
          align(center, text(size: ds)[Build \ Ready?]),
          shape: shapes.diamond, width: dw, height: dh,
          fill: dec-fill, stroke: 0.8pt + dec-stroke, inset: 2pt),

        // Stage 4 — Build & Deploy
        node((9, 0),
          align(center, text(size: pps, weight: "bold")[Stage 4 \ Build & \ Deploy]),
          shape: rect, corner-radius: 4pt, width: ppw,
          fill: pp-fill, stroke: 0.8pt + pp-stroke, inset: 4pt),

        // Join bar
        node((10, 0), [], shape: rect, width: 0.12cm, height: 1.3cm,
          fill: fork-fill, stroke: none),

        // Comparative Analysis — shared
        node((12, 0),
          align(center, text(size: ns, weight: "bold")[Comparative \ Analysis & \ DESMET Report]),
          shape: rect, corner-radius: 4pt, width: nw,
          fill: stage-fill, stroke: 0.8pt + stage-stroke, inset: 4pt),

        // End
        node((13, 0), [], shape: circle, width: 0.45cm, height: 0.45cm,
          fill: start-fill, stroke: 2.5pt + start-fill, outset: 2pt),

        // ── Parallel region label (above pipeline, framing stages 1-4) ──

        node((6.5, -0.45),
          text(size: 7pt, weight: "bold", fill: pp-stroke)[Per-Platform Parallel Execution (×9 platforms × 4 scenarios)],
          stroke: none, fill: none),

        // ── ROW 1 — Artifacts ──────────────────────────────────────────

        node((1, 1),
          align(center)[#text(size: art-s, fill: art-stroke)[Scenario Backlog (YAML) \ Gherkin Features \ Prompt Templates]],
          shape: rect, corner-radius: 2pt, width: nw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

        node((4, 1),
          align(center)[#text(size: art-s, fill: art-stroke)[Requirements \ Acceptance Criteria \ UML Diagrams]],
          shape: rect, corner-radius: 2pt, width: ppw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

        node((5, 1),
          align(center)[#text(size: art-s, fill: art-stroke)[Source Code \ Execution Logs \ Token Usage Data]],
          shape: rect, corner-radius: 2pt, width: ppw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

        node((6, 1),
          align(center)[#text(size: art-s, fill: art-stroke)[Test Suites \ Coverage Reports \ Test Pass Rates]],
          shape: rect, corner-radius: 2pt, width: ppw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

        node((9, 1),
          align(center)[#text(size: art-s, fill: art-stroke)[Build Artifacts \ Deploy Evidence \ Health Checks]],
          shape: rect, corner-radius: 2pt, width: ppw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

        node((12, 1),
          align(center)[#text(size: art-s, fill: art-stroke)[Dimension Scores \ Feature Matrices \ Radar Charts]],
          shape: rect, corner-radius: 2pt, width: nw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

        // ── ROW -1 — Cross-cutting dimensions (closer to pipeline) ─────

        node((6.5, -1),
          align(center)[
            #text(size: 7.5pt, weight: "bold", fill: dim-stroke)[Layer 3 Cross-Cutting Dimensions]
            #v(3pt)
            #set text(size: 7pt)
            #grid(
              columns: (auto, auto, auto, auto),
              column-gutter: 14pt,
              [1. Pipeline Completeness], [2. Efficiency], [3. Orchestration], [4. Autonomy],
            )
          ],
          shape: rect, corner-radius: 5pt, width: 11cm,
          fill: dim-fill, stroke: 1pt + dim-stroke, inset: 8pt),

        // Layer 3 span indicator: a dashed bracket below the dimensions box
        // covering Stage 1 → Comparative Analysis (the measured span), plus a
        // single down-arrow from the dimensions box to the bracket.
        edge((6.5, -1), (6.5, -0.55), "->",
          stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.7pt)),
        edge((4, -0.5), (12, -0.5), "-",
          stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.5pt)),
        edge((4, -0.5), (4, -0.35), "-",
          stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.5pt)),
        edge((12, -0.5), (12, -0.35), "-",
          stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.5pt)),

        // ── Edges — Main flow ──────────────────────────────────────────

        edge((0, 0), (1, 0), "->"),
        edge((1, 0), (3, 0), "->"),
        edge((3, 0), (4, 0), "->"),
        edge((4, 0), (5, 0), "->"),
        edge((5, 0), (6, 0), "->"),
        edge((6, 0), (7, 0), "->"),

        edge((7, 0), (9, 0), "->",
          label: box(fill: white, inset: (x: 2pt, y: 0.5pt),
            text(size: 7pt, weight: "bold", fill: dec-stroke)[Yes]),
          label-pos: 0.5),
        edge((7, 0), (5, 0), "->",
          stroke: 0.8pt + retry-stroke, bend: 30deg),

        // "No" label placed manually on the retry curve (fletcher's edge
        // labels don't render reliably on bent edges)
        node((6.7, 0.5),
          box(fill: white, inset: (x: 3pt, y: 1pt), stroke: 0.4pt + retry-stroke,
            radius: 2pt,
            text(size: 7pt, weight: "bold", fill: retry-stroke)[No]),
          stroke: none, fill: none),

        edge((9, 0), (10, 0), "->"),
        edge((10, 0), (12, 0), "->"),
        edge((12, 0), (13, 0), "->"),

        // Artifact edges (dashed, downward)
        edge((1, 0), (1, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
        edge((4, 0), (4, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
        edge((5, 0), (5, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
        edge((6, 0), (6, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
        edge((9, 0), (9, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
        edge((12, 0), (12, 1), "-->", stroke: (dash: "dashed", paint: art-stroke, thickness: 0.4pt)),
      )
    ]

    #v(0.3cm)
    #line(length: 100%, stroke: 0.4pt + luma(180))
    #v(0.15cm)

    #grid(
      columns: (auto, 1fr, 1fr, 1fr),
      gutter: 0.8cm,
      align: (left + horizon,) * 4,
      [#text(size: 8pt, weight: "bold")[Legend:]],
      [
        #box(width: 0.6cm, height: 0.35cm, fill: stage-fill, stroke: 0.7pt + stage-stroke, radius: 3pt)
        #text(size: 7pt)[ Shared / Harness]
        #h(0.6cm)
        #box(width: 0.6cm, height: 0.35cm, fill: pp-fill, stroke: 0.7pt + pp-stroke, radius: 3pt)
        #text(size: 7pt)[ Per-platform Stage]
      ],
      [
        #box(width: 0.6cm, height: 0.35cm, fill: dec-fill, stroke: 0.7pt + dec-stroke)
        #text(size: 7pt)[ Decision Gate]
        #h(0.6cm)
        #box(width: 0.6cm, height: 0.35cm, fill: art-fill, stroke: 0.7pt + art-stroke, radius: 2pt)
        #text(size: 7pt)[ Output Artifact]
      ],
      [
        #box(width: 0.6cm, height: 0.14cm, fill: fork-fill, radius: 0pt)
        #text(size: 7pt)[ Fork / Join]
        #h(0.6cm)
        #box(width: 0.6cm, height: 0.35cm, fill: dim-fill, stroke: 0.7pt + dim-stroke, radius: 3pt)
        #text(size: 7pt)[ Cross-cutting Dimension]
      ],
    )

    #v(0.15cm)

    #grid(
      columns: (1fr, 1fr, 1fr),
      gutter: 0.5cm,
      [
        #text(size: 7pt, weight: "bold")[Multi-Agent Frameworks] \
        #text(size: 7.5pt)[LangGraph · CrewAI]
      ],
      [
        #text(size: 7pt, weight: "bold")[Agent SDK Runtimes] \
        #text(size: 7.5pt)[OpenAI Agents SDK · Google ADK · Microsoft Agent Framework]
      ],
      [
        #text(size: 7pt, weight: "bold")[Visual / Workflow Platforms] \
        #text(size: 7.5pt)[Flowise · LangFlow · Dify · N8n]
      ],
    )
  ],
  caption: [Evaluation pipeline UML activity diagram.],
) <fig-pipeline-activity>

]
