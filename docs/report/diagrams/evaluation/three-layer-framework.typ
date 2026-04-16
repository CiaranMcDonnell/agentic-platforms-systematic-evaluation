// Three-Layer Evaluation Framework — injected into report via #include
// Portrait A4 — designed to fit within standard report margins

#import "@preview/fletcher:0.5.7" as fletcher: diagram, node, edge, shapes

// ── Colours ──────────────────────────────────────────────────────────────────

#let l1-fill   = rgb("#e8f5e9")   // light green  — Layer 1
#let l1-stroke = rgb("#2e7d32")
#let l2-fill   = rgb("#e3f2fd")   // light blue   — Layer 2
#let l2-stroke = rgb("#1565c0")
#let l3-fill   = rgb("#fff3e0")   // light orange — Layer 3 (per-platform, matching pipeline diagram)
#let l3-stroke = rgb("#e65100")
#let arrow-col = luma(80)

// ── Shared sizing ─────────────────────────────────────────────────────────────

#let lw = 12cm   // layer box width
#let ls = 8pt    // standard body text size

// ── Arrow connector ───────────────────────────────────────────────────────────
// Simple native Typst arrow — avoids fletcher zero-size node divide-by-zero.

#let down-arrow = align(center)[
  #pad(y: 3pt)[
    #line(length: 0pt)  // zero-width anchor
    #box(
      width: 1pt,
      height: 10pt,
      fill: arrow-col,
    )
    #v(-2pt)
    #polygon(
      fill: arrow-col,
      stroke: none,
      (0pt, 0pt), (5pt, 0pt), (2.5pt, 5pt),
    )
  ]
]

// ── Helper — draw one layer block ─────────────────────────────────────────────

#let layer-block(
  number: "",
  name: "",
  question: "",
  method: "",
  outputs: "",
  fill: white,
  stroke-col: black,
  header-extra: none,
  extra-body: none,
  border-weight: 1.2pt,
) = {
  rect(
    width: lw,
    fill: fill,
    stroke: border-weight + stroke-col,
    radius: 6pt,
    inset: 0pt,
  )[
    // Header bar
    #block(
      width: 100%,
      fill: stroke-col,
      radius: (top-left: 5pt, top-right: 5pt, bottom-left: 0pt, bottom-right: 0pt),
      inset: (x: 10pt, y: 6pt),
    )[
      #grid(
        columns: (1fr, auto),
        align: (left + horizon, right + horizon),
        [
          #text(size: 9pt, weight: "bold", fill: white)[
            Layer #number — #name
          ]
        ],
        if header-extra != none [
          #text(size: 7pt, fill: white, style: "italic")[#header-extra]
        ],
      )
    ]
    // Three-column body
    #pad(x: 10pt, top: 8pt, bottom: if extra-body != none { 4pt } else { 8pt })[
      #grid(
        columns: (3.1cm, 1fr, 3.1cm),
        gutter: 10pt,
        // Column 1: practitioner question
        [
          #text(size: 7pt, weight: "bold", fill: stroke-col)[Practitioner Question]
          #v(3pt)
          #text(size: ls, style: "italic")[#question]
        ],
        // Column 2: method
        [
          #text(size: 7pt, weight: "bold", fill: stroke-col)[Method]
          #v(3pt)
          #text(size: ls)[#method]
        ],
        // Column 3: scale / outputs
        [
          #text(size: 7pt, weight: "bold", fill: stroke-col)[Scale / Outputs]
          #v(3pt)
          #text(size: ls)[#outputs]
        ],
      )
      #if extra-body != none {
        v(6pt)
        line(length: 100%, stroke: 0.5pt + stroke-col.lighten(50%))
        v(5pt)
        extra-body
      }
    ]
  ]
}

// ── Figure ────────────────────────────────────────────────────────────────────

#figure(
  placement: top,
  kind: image,
  [
    #align(center)[
      #stack(
        dir: ttb,
        spacing: 0pt,

        // ── Layer 1 — Industry Readiness ─────────────────────────────────────
        layer-block(
          number: "1",
          name: "Industry Readiness",
          question: "Should I consider it?",
          method: [Qualitative screening of deployment maturity, vendor support, licensing, community activity, and documentation quality.],
          outputs: [Factual profile per platform.\ Indicators rated:\ Yes / Partial / No.],
          fill: l1-fill,
          stroke-col: l1-stroke,
        ),

        // Connector arrow
        v(-0.5pt),
        align(center)[
          #stack(
            dir: ttb,
            spacing: 0pt,
            block(width: 1.5pt, height: 14pt, fill: arrow-col),
            polygon(fill: arrow-col, stroke: 0pt + arrow-col,
              (-5pt, 0pt), (5pt, 0pt), (0pt, 6pt)),
          )
        ],
        v(-0.5pt),

        // ── Layer 2 — Platform Characteristics ───────────────────────────────
        layer-block(
          number: "2",
          name: "Platform Characteristics",
          question: "What can it do?",
          method: [Structured feature checklist extending the Broccia et al. (2024) taxonomy of agentic platform capabilities.],
          outputs: [Feature matrix per platform.\ Each capability rated:\ Yes / Partial / No.],
          fill: l2-fill,
          stroke-col: l2-stroke,
        ),

        // Connector arrow
        v(-0.5pt),
        align(center)[
          #stack(
            dir: ttb,
            spacing: 0pt,
            block(width: 1.5pt, height: 14pt, fill: arrow-col),
            polygon(fill: arrow-col, stroke: 0pt + arrow-col,
              (-5pt, 0pt), (5pt, 0pt), (0pt, 6pt)),
          )
        ],
        v(-0.5pt),

        // ── Layer 3 — Pipeline Benchmarking (largest — novel contribution) ───
        layer-block(
          number: "3",
          name: "Pipeline Benchmarking",
          question: "How well does it do it?",
          method: [Empirical benchmarking via a 4-stage agentic pipeline run against a fixed story backlog across all 10 platforms. Stages scored with qualitative rubrics and quantitative metrics.],
          outputs: [
            1–5 Likert per dimension: \
            #v(1pt)
            - Effectiveness \
            - Efficiency \
            - Quality \
            - Autonomy \
            #v(3pt)
            Aggregated DESMET score per platform.
          ],
          fill: l3-fill,
          stroke-col: l3-stroke,
          header-extra: "Novel contribution",
          border-weight: 1.8pt,
          extra-body: grid(
            columns: (auto, 1fr, 1fr, 1fr, 1fr),
            gutter: 5pt,
            align: (left + horizon,) + (center + horizon,) * 4,
            [#text(size: 7pt, weight: "bold", fill: l3-stroke)[Pipeline Stages:]],
            rect(fill: l3-stroke.lighten(65%), stroke: 0.6pt + l3-stroke, radius: 3pt,
              inset: (x: 5pt, y: 4pt))[
              #text(size: 6.5pt, weight: "bold")[Stage 1 \ Requirements]
            ],
            rect(fill: l3-stroke.lighten(65%), stroke: 0.6pt + l3-stroke, radius: 3pt,
              inset: (x: 5pt, y: 4pt))[
              #text(size: 6.5pt, weight: "bold")[Stage 2 \ Code Gen.]
            ],
            rect(fill: l3-stroke.lighten(65%), stroke: 0.6pt + l3-stroke, radius: 3pt,
              inset: (x: 5pt, y: 4pt))[
              #text(size: 6.5pt, weight: "bold")[Stage 3 \ Testing]
            ],
            rect(fill: l3-stroke.lighten(65%), stroke: 0.6pt + l3-stroke, radius: 3pt,
              inset: (x: 5pt, y: 4pt))[
              #text(size: 6.5pt, weight: "bold")[Stage 4 \ Build & Deploy]
            ],
          ),
        ),
      )
    ]
  ],
  caption: [
    Three-Layer Evaluation Framework.
    Each layer answers a distinct practitioner question at increasing analytical depth.
    Layers 1 and 2 provide qualitative screening (Yes / Partial / No).
    Layer 3 is the novel empirical contribution — pipeline benchmarking scored on a 1--5 Likert scale across four DESMET dimensions.
  ],
) <fig-three-layer>
