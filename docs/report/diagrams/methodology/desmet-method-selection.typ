// DESMET Method Selection Diagram — injected into report via #include
// Decision flow showing how DESMET guides evaluation method selection
// and how this study arrived at "Benchmarking + Qualitative Screening"
// Portrait A4 — designed to fit within standard report margins (Chapter 3)

// ── Colours ─────────────────────────────────────────────────────────────────────

// Non-selected methods
#let grey-fill   = rgb("#f5f5f5")
#let grey-stroke = rgb("#9e9e9e")
#let grey-text   = rgb("#757575")

// Selected methods — green
#let sel-fill   = rgb("#e8f5e9")
#let sel-stroke = rgb("#2e7d32")
#let sel-text   = rgb("#1b5e20")

// Column header colours
#let quant-fill = rgb("#e3f2fd")
#let quant-hdr  = rgb("#1565c0")
#let qual-fill  = rgb("#f3e5f5")
#let qual-hdr   = rgb("#6a1b9a")
#let hyb-fill   = rgb("#fff3e0")
#let hyb-hdr    = rgb("#e65100")

// Criteria / decision
#let crit-fill   = rgb("#fafafa")
#let crit-stroke = rgb("#546e7a")
#let crit-hdr    = rgb("#37474f")

// Arrow
#let arr-col = luma(90)

// ── Sizing ──────────────────────────────────────────────────────────────────────

#let col-w   = 3.9cm
#let full-w  = 13.0cm
#let item-sz = 7.5pt
#let note-sz = 6.5pt
#let crit-sz = 7.5pt
#let hdr-sz  = 7.5pt

// ── Helper: method item box ─────────────────────────────────────────────────────

#let method-box(name: "", selected: false) = {
  let f  = if selected { sel-fill } else { grey-fill }
  let s  = if selected { sel-stroke } else { grey-stroke }
  let sw = if selected { 1.8pt } else { 0.7pt }
  let tc = if selected { sel-text } else { grey-text }
  let fw = if selected { "bold" } else { "regular" }

  rect(
    width: 100%, fill: f, stroke: sw + s, radius: 4pt,
    inset: (x: 7pt, y: 5pt),
  )[#text(size: item-sz, weight: fw, fill: tc)[#name]]
}

// ── Helper: method column (header + items) ──────────────────────────────────────

#let method-col(title: "", hdr-fill: quant-hdr, body-fill: quant-fill, methods: ()) = {
  rect(
    width: col-w, fill: body-fill,
    stroke: 0.6pt + hdr-fill.lighten(20%),
    radius: 6pt, inset: 0pt,
  )[
    #block(
      width: 100%, fill: hdr-fill,
      radius: (top-left: 5pt, top-right: 5pt, bottom-left: 0pt, bottom-right: 0pt),
      inset: (x: 8pt, y: 5pt),
    )[
      #align(center)[#text(size: hdr-sz, weight: "bold", fill: white)[#title]]
    ]
    #pad(x: 6pt, top: 6pt, bottom: 8pt)[
      #stack(dir: ttb, spacing: 4pt, ..methods)
    ]
  ]
}

// ── Helper: criteria item ───────────────────────────────────────────────────────

#let crit-item(body: "", elim: false, favour: false) = {
  let icon   = if elim { "✕" } else if favour { "✓" } else { "→" }
  let ic-col = if elim { rgb("#c62828") } else if favour { sel-stroke } else { crit-hdr }

  grid(
    columns: (12pt, 1fr), gutter: 4pt,
    align: (center + top, left + top),
    text(size: crit-sz, weight: "bold", fill: ic-col)[#icon],
    text(size: crit-sz, fill: ic-col)[#body],
  )
}

// ── Helper: down arrow (clean curve primitive) ──────────────────────────────────

#let down-arrow(col: arr-col, h: 14pt) = {
  let sw = 1pt
  let aw = 4.5pt
  let ah = 5.5pt
  align(center, v(2pt) + curve(
    fill: col,
    stroke: 0.3pt + col,
    curve.move((-sw, 0pt)),
    curve.line((-sw, h)),
    curve.line((-aw, h)),
    curve.line((0pt, h + ah)),
    curve.line((aw, h)),
    curve.line((sw, h)),
    curve.line((sw, 0pt)),
    curve.close(),
  ) + v(2pt))
}

// ── Helper: converging funnel arrows ────────────────────────────────────────────
// Draws three lines converging from column bottoms to a single point below.

#let converging-arrows(total-w: full-w, h: 20pt, col: arr-col) = {
  let mid = total-w / 2
  let left-x = total-w * 0.167   // centre of left column
  let right-x = total-w * 0.833  // centre of right column
  let aw = 4.5pt
  let ah = 5.5pt

  align(center)[
    #box(width: total-w, height: h + ah + 2pt)[
      // Left diagonal line
      #place(top + left, dx: left-x, dy: 0pt)[
        #line(
          start: (0pt, 0pt),
          end: (mid - left-x, h),
          stroke: 1pt + col,
        )
      ]
      // Centre vertical line
      #place(top + left, dx: mid, dy: 0pt)[
        #line(
          start: (0pt, 0pt),
          end: (0pt, h),
          stroke: 1pt + col,
        )
      ]
      // Right diagonal line
      #place(top + left, dx: right-x, dy: 0pt)[
        #line(
          start: (0pt, 0pt),
          end: (mid - right-x, h),
          stroke: 1pt + col,
        )
      ]
      // Arrowhead at merge point
      #place(top + left, dx: mid - aw, dy: h)[
        #polygon(
          fill: col, stroke: none,
          (0pt, 0pt), (aw * 2, 0pt), (aw, ah),
        )
      ]
    ]
  ]
}

// ── Figure body ─────────────────────────────────────────────────────────────────

#figure(
  placement: top,
  kind: image,
  [
    #align(center)[
      #block(width: full-w)[

        // ── Title header ────────────────────────────────────────────────────
        #rect(
          width: 100%, fill: crit-hdr, stroke: none, radius: 6pt,
          inset: (x: 12pt, y: 8pt),
        )[
          #align(center)[
            #text(size: 10pt, weight: "bold", fill: white)[
              DESMET Evaluation Methods
            ]
            #v(1pt)
            #text(size: note-sz, fill: white.lighten(30%))[
              Nine methods across three categories — guiding selection for this study
            ]
          ]
        ]

        #v(10pt)

        // ── Three columns of methods ────────────────────────────────────────
        #grid(
          columns: (1fr, 0.4cm, 1fr, 0.4cm, 1fr),
          gutter: 0pt,
          align: top,

          method-col(
            title: "Quantitative",
            hdr-fill: quant-hdr, body-fill: quant-fill,
            methods: (
              method-box(name: "Formal Experiment"),
              method-box(name: "Case Study"),
              method-box(name: "Survey"),
            ),
          ),
          [],
          method-col(
            title: "Qualitative",
            hdr-fill: qual-hdr, body-fill: qual-fill,
            methods: (
              method-box(name: "Screening", selected: true),
              method-box(name: "Experiment"),
              method-box(name: "Case Study"),
              method-box(name: "Survey"),
            ),
          ),
          [],
          method-col(
            title: "Hybrid",
            hdr-fill: hyb-hdr, body-fill: hyb-fill,
            methods: (
              method-box(name: "Effects Analysis"),
              method-box(name: "Benchmarking", selected: true),
            ),
          ),
        )

        // ── Converging funnel arrows ────────────────────────────────────────
        #converging-arrows()

        // ── Decision criteria box ───────────────────────────────────────────
        #rect(
          width: 100%, fill: crit-fill,
          stroke: 1pt + crit-stroke, radius: 6pt, inset: 0pt,
        )[
          #block(
            width: 100%, fill: crit-hdr,
            radius: (top-left: 5pt, top-right: 5pt, bottom-left: 0pt, bottom-right: 0pt),
            inset: (x: 10pt, y: 5pt),
          )[
            #align(center)[
              #text(size: 8pt, weight: "bold", fill: white)[
                Selection Criteria Applied in This Study
              ]
            ]
          ]
          #pad(x: 14pt, top: 10pt, bottom: 12pt)[
            #grid(
              columns: (1fr, 1fr), gutter: (8pt, 8pt),
              crit-item(
                body: [Benefits not easily quantifiable → eliminates pure quantitative methods],
                elim: true,
              ),
              crit-item(
                body: [No access to large user population → eliminates survey-based methods],
                elim: true,
              ),
              crit-item(
                body: [Platforms architecturally heterogeneous → favours qualitative feature screening],
                favour: true,
              ),
              crit-item(
                body: [Standardised SE tasks available → enables objective benchmarking],
                favour: true,
              ),
            )
          ]
        ]

        #v(2pt)

        // ── Arrow: criteria → result (green) ────────────────────────────────
        #down-arrow(col: sel-stroke, h: 16pt)

        #v(2pt)

        // ── Selected result box ─────────────────────────────────────────────
        #rect(
          width: 100%, fill: sel-fill,
          stroke: 2pt + sel-stroke, radius: 6pt,
          inset: (x: 14pt, y: 12pt),
        )[
          #align(center)[
            #text(size: note-sz, weight: "bold", fill: sel-stroke, style: "italic")[
              Study Approach
            ]
            #v(4pt)
            #text(size: 9.5pt, weight: "bold", fill: sel-text)[
              Qualitative Screening  +  Benchmarking (Hybrid)
            ]
            #v(5pt)
            #text(size: note-sz, fill: luma(60))[
              Layer 1–2: feature-based screening of industry readiness and platform characteristics \
              Layer 3: empirical pipeline benchmarking across four SE workflow stages
            ]
          ]
        ]

        // ── Legend ──────────────────────────────────────────────────────────
        #v(10pt)
        #line(length: 100%, stroke: 0.4pt + luma(190))
        #v(6pt)

        #grid(
          columns: (auto, 1fr, 1fr, 1fr),
          gutter: 6pt,
          align: (left + horizon,) * 4,
          text(size: note-sz, weight: "bold")[Legend:],
          [
            #box(width: 0.55cm, height: 0.32cm, fill: sel-fill, stroke: 1.8pt + sel-stroke, radius: 3pt)
            #h(3pt)
            #text(size: note-sz)[Selected method]
          ],
          [
            #box(width: 0.55cm, height: 0.32cm, fill: grey-fill, stroke: 0.7pt + grey-stroke, radius: 3pt)
            #h(3pt)
            #text(size: note-sz)[Not selected]
          ],
          [
            #text(size: note-sz, weight: "bold", fill: rgb("#c62828"))[✕]
            #h(2pt)
            #text(size: note-sz)[Eliminates \ ]
            #text(size: note-sz, weight: "bold", fill: sel-stroke)[✓]
            #h(2pt)
            #text(size: note-sz)[Favours]
          ],
        )

      ] // end block
    ] // end align center
  ],
  caption: [
    DESMET evaluation method selection for this study. The nine DESMET methods span
    three categories: Quantitative, Qualitative, and Hybrid. Four decision criteria
    narrow the field: the expected benefits of agentic tools resist precise
    quantification, eliminating purely quantitative methods; the absence of a large
    accessible user population rules out survey-based approaches; the architectural
    heterogeneity of the ten platforms favours qualitative feature screening; and
    the availability of standardised software engineering tasks enables objective
    benchmarking. The resulting approach combines Qualitative Screening (Layers 1–2)
    with Hybrid Benchmarking (Layer 3).
  ],
) <fig-desmet-selection>
