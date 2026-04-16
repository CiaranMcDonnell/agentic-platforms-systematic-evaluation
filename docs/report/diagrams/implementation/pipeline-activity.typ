// Pipeline Activity Diagram — injected into report via #include
// Renders on a landscape page, then reverts to portrait

#import "@preview/fletcher:0.5.7" as fletcher: diagram, node, edge, shapes

// ── Colours ──────────────────────────────────────────────────────────────────

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

#let nw  = 2.0cm     // shared-stage node width
#let ppw = 1.6cm     // per-platform node width
#let dw  = 1.4cm     // diamond width
#let dh  = 1.1cm     // diamond height
#let ns  = 7pt       // shared node text size
#let pps = 6pt       // per-platform text size
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

        // Story Input — shared harness infrastructure
        node((1, 0),
          align(center, text(size: ns, weight: "bold")[Story Input \ #text(weight: "regular", size: 5.5pt)[(YAML loading, context prep.)]]),
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
          text(size: 7pt, weight: "bold", fill: pp-stroke)[Per-Platform Parallel Execution (×10 platforms × 4 stories)],
          stroke: none, fill: none),

        // ── ROW 1 — Artifacts ──────────────────────────────────────────

        node((1, 1),
          align(center)[#text(size: art-s, fill: art-stroke)[Story Backlog (YAML) \ Gherkin Features \ Prompt Templates]],
          shape: rect, corner-radius: 2pt, width: nw, fill: art-fill, stroke: 0.5pt + art-stroke, inset: 3pt),

        node((4, 1),
          align(center)[#text(size: art-s, fill: art-stroke)[Requirements \ Acceptance Criteria \ UML Diagrams (Mermaid)]],
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
              columns: (1fr, 1fr, 1fr, 1fr),
              gutter: 8pt,
              [1. Effectiveness], [2. Efficiency], [3. Quality], [4. Autonomy],
            )
          ],
          shape: rect, corner-radius: 5pt, width: 8cm,
          fill: dim-fill, stroke: 1pt + dim-stroke, inset: 8pt),

        // Dashed arrows from dimensions to key pipeline nodes
        edge((6.5, -1), (4, 0), "-->", stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.5pt)),
        edge((6.5, -1), (9, 0), "-->", stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.5pt)),
        edge((6.5, -1), (12, 0), "-->", stroke: (dash: "dashed", paint: dim-stroke, thickness: 0.5pt)),

        // ── Edges — Main flow ──────────────────────────────────────────

        edge((0, 0), (1, 0), "->"),
        edge((1, 0), (3, 0), "->"),
        edge((3, 0), (4, 0), "->"),
        edge((4, 0), (5, 0), "->"),
        edge((5, 0), (6, 0), "->"),
        edge((6, 0), (7, 0), "->"),

        edge((7, 0), (9, 0), "->",
          label: text(size: 5.5pt, fill: dec-stroke)[Yes]),
        edge((7, 0), (5, 0), "->",
          label: text(size: 5.5pt, fill: red)[No], stroke: 0.7pt + red, bend: 30deg),

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
        #text(size: 7.5pt)[LangGraph · CrewAI · AutoGen]
      ],
      [
        #text(size: 7pt, weight: "bold")[Agent SDK Runtimes] \
        #text(size: 7.5pt)[OpenAI Agents SDK · Google ADK · Semantic Kernel]
      ],
      [
        #text(size: 7pt, weight: "bold")[Visual / Workflow Platforms] \
        #text(size: 7.5pt)[Flowise · LangFlow · Dify · N8n]
      ],
    )
  ],
  caption: [Evaluation Pipeline — UML Activity Diagram. User stories flow through four per-platform stages (orange), with cross-cutting dimensions (yellow) measured throughout. Shared harness stages shown in blue.],
) <fig-pipeline-activity>

]
