// Platform Isolation Architecture — injected into report via #include
// Shows how the harness dispatches to containerized and in-process runners

#import "@preview/fletcher:0.5.7" as fletcher: diagram, node, edge

// ── Colours ──────────────────────────────────────────────────────────────────

#let harness-fill   = rgb("#e3f2fd")   // light blue  — harness / shared
#let harness-stroke = rgb("#1565c0")
#let sdk-fill       = rgb("#fff3e0")   // light orange — per-platform (matches pipeline)
#let sdk-stroke     = rgb("#e65100")
#let visual-fill    = rgb("#e8f5e9")   // light green  — visual / workflow
#let visual-stroke  = rgb("#2e7d32")
#let fallback-fill  = rgb("#f5f5f5")   // grey         — fallback
#let fallback-stroke = rgb("#757575")
#let docker-fill    = rgb("#e1f5fe")
#let docker-stroke  = rgb("#0277bd")

// ── Sizing ───────────────────────────────────────────────────────────────────

#let ns = 7pt       // node text size
#let ss = 6.5pt     // small text size

// ── Figure ───────────────────────────────────────────────────────────────────

#figure(
  placement: top,
  kind: image,
  [
    #align(center)[
      #diagram(
        spacing: (1.6cm, 1.1cm),
        node-stroke: 0.8pt,

        // ── Row 0 — Host harness ──────────────────────────────────────────

        node((2, 0),
          align(center)[
            #text(size: 8pt, weight: "bold")[DESMET Harness]
            #v(2pt)
            #text(size: ss)[Management Console + Evaluation Runner]
          ],
          shape: rect, corner-radius: 5pt, width: 4.4cm,
          fill: harness-fill, stroke: 1pt + harness-stroke, inset: 8pt),

        // ── Row 1 — Three execution modes ─────────────────────────────────

        node((0.5, 1),
          align(center)[
            #text(size: ns, weight: "bold")[Container Runner]
            #v(2pt)
            #text(size: ss, fill: sdk-stroke)[Docker SDK API]
          ],
          shape: rect, corner-radius: 5pt, width: 3cm,
          fill: sdk-fill, stroke: 0.8pt + sdk-stroke, inset: 7pt),

        node((2, 1),
          align(center)[
            #text(size: ns, weight: "bold")[In-Process]
            #v(2pt)
            #text(size: ss, fill: fallback-stroke)[Fallback (no image)]
          ],
          shape: rect, corner-radius: 5pt, width: 2.6cm,
          fill: fallback-fill, stroke: (dash: "dashed", paint: fallback-stroke, thickness: 0.8pt), inset: 7pt),

        node((3.5, 1),
          align(center)[
            #text(size: ns, weight: "bold")[Docker Compose]
            #v(2pt)
            #text(size: ss, fill: visual-stroke)[infrastructure/]
          ],
          shape: rect, corner-radius: 5pt, width: 3cm,
          fill: visual-fill, stroke: 0.8pt + visual-stroke, inset: 7pt),

        // ── Row 2 — Generic container instances ──────────────────────────

        // SDK containers — each platform gets its own isolated container
        node((-0.15, 2.2),
          align(center)[
            #text(size: ss)[▢ Platform A]
            #v(1pt)
            #text(size: 5.5pt, fill: luma(100))[SDK + isolated deps]
          ],
          shape: rect, corner-radius: 3pt, width: 2.1cm,
          fill: white, stroke: 0.6pt + sdk-stroke, inset: 5pt),

        node((0.7, 2.2),
          align(center)[
            #text(size: ss)[▢ Platform B]
            #v(1pt)
            #text(size: 5.5pt, fill: luma(100))[SDK + isolated deps]
          ],
          shape: rect, corner-radius: 3pt, width: 2.1cm,
          fill: white, stroke: 0.6pt + sdk-stroke, inset: 5pt),

        node((1.55, 2.2),
          align(center)[
            #text(size: ss, fill: luma(120))[#sym.dots.c]
          ],
          shape: rect, corner-radius: 3pt, width: 1cm,
          fill: white, stroke: (dash: "dotted", paint: sdk-stroke, thickness: 0.6pt), inset: 5pt),

        // Visual platform services — shared Compose stack
        node((3.05, 2.2),
          align(center)[
            #text(size: ss)[▢ Service A]
          ],
          shape: rect, corner-radius: 3pt, width: 1.8cm,
          fill: white, stroke: 0.6pt + visual-stroke, inset: 5pt),

        node((3.85, 2.2),
          align(center)[
            #text(size: ss)[▢ Service B]
          ],
          shape: rect, corner-radius: 3pt, width: 1.8cm,
          fill: white, stroke: 0.6pt + visual-stroke, inset: 5pt),

        node((4.55, 2.2),
          align(center)[
            #text(size: ss, fill: luma(120))[#sym.dots.c]
          ],
          shape: rect, corner-radius: 3pt, width: 1cm,
          fill: white, stroke: (dash: "dotted", paint: visual-stroke, thickness: 0.6pt), inset: 5pt),

        // ── Edges ─────────────────────────────────────────────────────────

        // Harness to three modes
        edge((2, 0), (0.5, 1), "->", stroke: 0.7pt + harness-stroke),
        edge((2, 0), (2, 1), "->", stroke: (dash: "dashed", paint: fallback-stroke, thickness: 0.7pt)),
        edge((2, 0), (3.5, 1), "->", stroke: 0.7pt + harness-stroke),

        // Container runner to SDK containers
        edge((0.5, 1), (-0.15, 2.2), "->", stroke: 0.5pt + sdk-stroke),
        edge((0.5, 1), (0.7, 2.2), "->", stroke: 0.5pt + sdk-stroke),
        edge((0.5, 1), (1.55, 2.2), "->", stroke: 0.5pt + sdk-stroke),

        // Docker Compose to visual services
        edge((3.5, 1), (3.05, 2.2), "->", stroke: 0.5pt + visual-stroke),
        edge((3.5, 1), (3.85, 2.2), "->", stroke: 0.5pt + visual-stroke),
        edge((3.5, 1), (4.55, 2.2), "->", stroke: 0.5pt + visual-stroke),
      )
    ]

    #v(0.3cm)
    #line(length: 100%, stroke: 0.4pt + luma(180))
    #v(0.15cm)

    // Legend
    #grid(
      columns: (1fr, 1fr, 1fr, 1fr),
      gutter: 0.6cm,
      align: (left + horizon,) * 4,
      [#text(size: 7.5pt, weight: "bold")[Legend:]],
      [
        #box(width: 0.5cm, height: 0.3cm, fill: harness-fill, stroke: 0.6pt + harness-stroke, radius: 3pt)
        #text(size: 6.5pt)[ Host / Harness]
      ],
      [
        #box(width: 0.5cm, height: 0.3cm, fill: sdk-fill, stroke: 0.6pt + sdk-stroke, radius: 3pt)
        #text(size: 6.5pt)[ SDK Container]
      ],
      [
        #box(width: 0.5cm, height: 0.3cm, fill: visual-fill, stroke: 0.6pt + visual-stroke, radius: 3pt)
        #text(size: 6.5pt)[ Visual / Workflow]
      ],
    )
  ],
  caption: [
    Platform isolation architecture.
    The evaluation runner dispatches each SDK platform to its own Docker container with isolated dependencies, avoiding version conflicts between frameworks.
    Visual platforms run via Docker Compose.
    If no container image exists, the runner falls back to in-process execution (dashed).
  ],
) <fig-platform-isolation>
