// Harness Architecture Diagram — injected into report via #include
// Component diagram: evaluation harness system, portrait A4

// ── Colours ───────────────────────────────────────────────────────────────────

#let h-fill   = rgb("#e3f2fd")   // Blue — harness infrastructure
#let h-stroke = rgb("#1565c0")
#let a-fill   = rgb("#fff3e0")   // Orange — platform adapters
#let a-stroke = rgb("#e65100")
#let o-fill   = rgb("#f3e5f5")   // Purple — outputs / storage / UI
#let o-stroke = rgb("#6a1b9a")
#let m-fill   = rgb("#fff8e1")   // Gold — metrics / dimensions
#let m-stroke = rgb("#f57f17")
#let x-fill   = rgb("#e8f5e9")   // Green — cross-cutting concerns
#let x-stroke = rgb("#2e7d32")
#let arr-col  = luma(80)

// ── Sizing constants ─────────────────────────────────────────────────────────

#let bw  = 13.0cm   // full-width block
#let bs  = 7pt      // body text size
#let ss  = 6pt      // small text size
#let xs  = 5.5pt    // extra-small text

// ── Clean arrow primitive ────────────────────────────────────────────────────

#let down-arrow(h: 7pt) = {
  let sw = 1pt
  let aw = 3.5pt
  let ah = 4.5pt
  align(center, v(1.5pt) + curve(
    fill: arr-col,
    stroke: 0.3pt + arr-col,
    curve.move((-sw, 0pt)),
    curve.line((-sw, h)),
    curve.line((-aw, h)),
    curve.line((0pt, h + ah)),
    curve.line((aw, h)),
    curve.line((sw, h)),
    curve.line((sw, 0pt)),
    curve.close(),
  ) + v(1.5pt))
}

#let right-arrow = pad(x: 2pt, y: 0pt)[
  #text(size: 10pt, fill: a-stroke, weight: "bold")[#sym.arrow.r]
]

// ── Component box helper ─────────────────────────────────────────────────────

#let comp-box(
  label: "",
  detail: none,
  bg: h-fill,
  accent: h-stroke,
  w: bw,
) = rect(
  width: w,
  fill: bg,
  stroke: 0.8pt + accent,
  radius: 3pt,
  inset: 0pt,
)[
  #block(
    width: 100%,
    fill: accent,
    radius: (top-left: 2pt, top-right: 2pt),
    inset: (x: 6pt, y: 3pt),
  )[#text(size: bs, weight: "bold", fill: white)[#label]]
  #if detail != none {
    pad(x: 6pt, y: 3pt)[#detail]
  }
]

// ── Figure body ──────────────────────────────────────────────────────────────

#figure(
  placement: top,
  kind: image,
  [
    #align(center)[
      #stack(
        dir: ttb,
        spacing: 0pt,

        // ── 1. CLI (thin strip) ─────────────────────────────────────────────
        rect(width: bw, fill: h-fill, stroke: 0.8pt + h-stroke, radius: 3pt, inset: (x: 8pt, y: 4pt))[
          #text(size: bs, weight: "bold")[desmet CLI]
          #text(size: ss, fill: luma(80))[ — entry point; launches WebUI management console via Uvicorn (port 8042)]
        ],

        down-arrow(),

        // ── 2. WebUI ────────────────────────────────────────────────────────
        comp-box(
          label: "WebUI  (FastAPI — desmet.webui.api)",
          detail: text(size: ss)[
            Management console and API backend. REST endpoints for platform management, benchmark execution, and results visualisation. WebSocket for live logs.
          ],
          bg: o-fill, accent: o-stroke,
        ),

        down-arrow(),

        // ── 3. Side-by-side: Runner | Infrastructure ────────────────────────
        grid(
          columns: (1fr, 0.2cm, 1fr),
          gutter: 0pt, align: top,

          comp-box(
            label: "Runner  (harness/runner.py)",
            detail: text(size: ss)[
              Orchestrates evaluation across platforms and stories. Instantiates adapters via Registry, invokes stages sequentially, collects typed StageResult objects.
            ],
            w: 100%,
          ),

          [],

          comp-box(
            label: "Infrastructure  (infra.py)",
            detail: [
              #text(size: ss)[Docker Compose orchestration for containerised platforms. Manages service profiles, health checks, status.]
              #v(1pt)
              #text(size: xs, fill: h-stroke)[Flowise · LangFlow · Dify · n8n · Langfuse]
            ],
            w: 100%,
          ),
        ),

        down-arrow(),

        // ── 4. Side-by-side: Story Loader | BasePlatformAdapter ─────────────
        grid(
          columns: (1fr, 0.2cm, 1fr),
          gutter: 0pt,
          align: top,

          comp-box(
            label: "Story Loader  (stage1)",
            detail: [
              #text(size: ss)[Reads YAML story definitions. Validates fields, resolves prompts and Gherkin, constructs StageContext.]
              #v(1pt)
              #text(size: xs, fill: h-stroke)[basic / intermediate / advanced]
            ],
            w: 100%,
          ),

          [],

          comp-box(
            label: "BasePlatformAdapter  (ABC)",
            detail: text(size: ss)[
              Abstract base class defining the 4-method stage interface all platform adapters must implement. Extended by VisualPlatformAdapter for HTTP API platforms. Adapters are resolved at runtime via the adapter Registry.
            ],
            w: 100%,
          ),
        ),

        down-arrow(),

        // ── 5. Pipeline Stages ───────────────────────────────────────────────
        rect(width: bw, fill: a-fill, stroke: 0.8pt + a-stroke, radius: 3pt, inset: 0pt)[
          #block(width: 100%, fill: a-stroke, radius: (top-left: 2pt, top-right: 2pt), inset: (x: 6pt, y: 3pt))[
            #text(size: bs, weight: "bold", fill: white)[Per-Platform Pipeline Stages]
          ]
          #pad(x: 6pt, y: 5pt)[
            #grid(
              columns: (1fr, auto, 1fr, auto, 1fr, auto, 1fr),
              gutter: 0pt, align: center + horizon,
              rect(fill: white, stroke: 0.6pt + a-stroke, radius: 2pt, inset: (x: 3pt, y: 4pt))[
                #align(center)[#text(size: ss, weight: "bold")[generate_requirements()] #v(1pt) #text(size: xs, fill: a-stroke)[Stage 1]]
              ],
              right-arrow,
              rect(fill: white, stroke: 0.6pt + a-stroke, radius: 2pt, inset: (x: 3pt, y: 4pt))[
                #align(center)[#text(size: ss, weight: "bold")[generate_code()] #v(1pt) #text(size: xs, fill: a-stroke)[Stage 2]]
              ],
              right-arrow,
              rect(fill: white, stroke: 0.6pt + a-stroke, radius: 2pt, inset: (x: 3pt, y: 4pt))[
                #align(center)[#text(size: ss, weight: "bold")[generate_tests()] #v(1pt) #text(size: xs, fill: a-stroke)[Stage 3]]
              ],
              right-arrow,
              rect(fill: white, stroke: 0.6pt + a-stroke, radius: 2pt, inset: (x: 3pt, y: 4pt))[
                #align(center)[#text(size: ss, weight: "bold")[build_and_deploy()] #v(1pt) #text(size: xs, fill: a-stroke)[Stage 4]]
              ],
            )
          ]
        ],

        down-arrow(),

        // ── 6. StageResult (thin bar) ────────────────────────────────────────
        rect(width: bw, fill: luma(250), stroke: 0.5pt + luma(160), radius: 2pt, inset: (x: 8pt, y: 3pt))[
          #text(size: ss, weight: "bold")[StageResult]
          #text(size: ss, fill: luma(80))[ — typed output with AgentTrace (tokens, time, tool calls)]
          #h(4pt)
          #text(size: xs, fill: luma(100))[RequirementsResult #sym.bar.v CodeResult #sym.bar.v TestResult #sym.bar.v DeployResult]
        ],

        down-arrow(),

        // ── 7. Three-column: Metrics | Results | Dashboard ───────────────────
        grid(
          columns: (1fr, 0.2cm, 1fr, 0.2cm, 1fr),
          gutter: 0pt, align: top,

          comp-box(
            label: "Metrics Collector",
            detail: [
              #text(size: ss)[Dimension scores (1–5 Likert):]
              #v(1pt)
              #grid(
                columns: (auto, auto), gutter: (3pt, 1pt),
                ..("Pipeline Comp.", "Efficiency", "Orchestration", "Autonomy").map(d =>
                  [#rect(width: 4pt, height: 4pt, fill: m-stroke, radius: 1pt, stroke: none)[] #text(size: xs, weight: "bold")[#d]]
                )
              )
            ],
            bg: m-fill, accent: m-stroke, w: 100%,
          ),

          [],

          comp-box(
            label: "Results Storage",
            detail: [
              #text(size: xs, style: "italic", fill: o-stroke)[results/{platform}/{story_id}/]
              #v(1pt)
              #text(size: ss)[Stage outputs, traces, token logs, rubric evidence.]
            ],
            bg: o-fill, accent: o-stroke, w: 100%,
          ),

          [],

          comp-box(
            label: "Dashboard Data",
            detail: [
              #text(size: ss)[Chart generation consumed by WebUI. Platform summaries, Plotly visualisations.]
            ],
            bg: o-fill, accent: o-stroke, w: 100%,
          ),
        ),

        v(4pt),

        // ── 8. Cross-cutting (compact strip) ────────────────────────────────
        rect(width: bw, fill: x-fill, stroke: 0.7pt + x-stroke, radius: 3pt, inset: (x: 8pt, y: 4pt))[
          #grid(
            columns: (auto, 1fr, 0.3cm, auto, 1fr),
            gutter: 0pt, align: left + top,
            text(size: ss, weight: "bold", fill: x-stroke)[LLM Config ],
            text(size: xs)[Centralised model, temperature, provider (OpenAI, Anthropic, Google, OpenRouter).],
            [],
            text(size: ss, weight: "bold", fill: x-stroke)[Observability ],
            text(size: xs)[Structured logging (structlog) + optional Langfuse tracing for LLM calls and pipeline spans.],
          )
        ],

      ) // end stack
    ] // end align center

    #v(0.15cm)
    #line(length: 100%, stroke: 0.4pt + luma(180))
    #v(0.08cm)

    // ── Legend (single row) ────────────────────────────────────────────────
    #align(center)[
      #text(size: ss, weight: "bold")[Legend: ]
      #box(width: 0.4cm, height: 0.22cm, fill: h-fill, stroke: 0.5pt + h-stroke, radius: 2pt)
      #text(size: xs)[ Harness]
      #h(0.12cm)
      #box(width: 0.4cm, height: 0.22cm, fill: a-fill, stroke: 0.5pt + a-stroke, radius: 2pt)
      #text(size: xs)[ Adapter / Stage]
      #h(0.12cm)
      #box(width: 0.4cm, height: 0.22cm, fill: o-fill, stroke: 0.5pt + o-stroke, radius: 2pt)
      #text(size: xs)[ UI / Storage]
      #h(0.12cm)
      #box(width: 0.4cm, height: 0.22cm, fill: m-fill, stroke: 0.5pt + m-stroke, radius: 2pt)
      #text(size: xs)[ Metrics]
      #h(0.12cm)
      #box(width: 0.4cm, height: 0.22cm, fill: x-fill, stroke: 0.5pt + x-stroke, radius: 2pt)
      #text(size: xs)[ Cross-Cutting]
    ]
  ],
  caption: [
    Evaluation Harness Architecture. The _desmet_ CLI launches a FastAPI-based WebUI that serves as the management console. The WebUI delegates benchmark execution to the Runner, which dispatches user stories through platform-specific adapters. Each adapter executes four pipeline stages, producing typed StageResult objects. The Metrics Collector computes dimension scores; Results Storage persists JSON artifacts; the Dashboard data layer provides chart generation consumed by the WebUI. Cross-cutting concerns — centralised LLM configuration and structured observability — span all components.
  ],
) <fig-harness-arch>
