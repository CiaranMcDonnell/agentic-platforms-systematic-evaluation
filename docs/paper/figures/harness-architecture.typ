// Harness architecture — adapted from the thesis diagram for a two-column
// IEEE page: spans both columns (scope: "parent"), width reduced, console
// and CLI merged into one strip, dashboard box dropped.

#let h-fill   = rgb("#DCE7F1")
#let h-stroke = rgb("#2C5282")
#let a-fill   = rgb("#F5E1C8")
#let a-stroke = rgb("#B8691F")
#let o-fill   = rgb("#E4DAEA")
#let o-stroke = rgb("#6B4B8A")
#let m-fill   = rgb("#F5EBC8")
#let m-stroke = rgb("#A8851F")
#let x-fill   = rgb("#D4E4D0")
#let x-stroke = rgb("#4A7A3F")
#let arr-col  = luma(80)

#let bw = 17cm
#let bs = 7pt
#let ss = 6.5pt
#let xs = 6pt

#let down-arrow(h: 6pt) = {
  let sw = 1pt
  let aw = 3.5pt
  let ah = 4pt
  align(center, v(1pt) + curve(
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
  ) + v(1pt))
}

#let right-arrow = pad(x: 2pt)[#text(size: 10pt, fill: a-stroke, weight: "bold")[#sym.arrow.r]]

#let side-arrow(label) = align(center)[
  #text(size: xs, fill: arr-col, style: "italic")[#label]
  #v(-2pt)
  #text(size: 13pt, fill: arr-col)[#sym.arrow.r]
]

#let comp-box(label: "", detail: none, bg: h-fill, accent: h-stroke, w: bw) = rect(
  width: w, fill: bg, stroke: 0.8pt + accent, radius: 3pt, inset: 0pt,
)[
  #block(width: 100%, fill: accent, radius: (top-left: 2pt, top-right: 2pt), inset: (x: 6pt, y: 3pt))[
    #text(size: bs, weight: "bold", fill: white)[#label]
  ]
  #if detail != none { pad(x: 6pt, y: 3pt)[#detail] }
]

#let stage-box(name, n) = rect(fill: white, stroke: 0.6pt + a-stroke, radius: 2pt, inset: (x: 3pt, y: 4pt))[
  #align(center)[#text(size: ss, weight: "bold")[#raw(name)] #v(1pt) #text(size: xs, fill: a-stroke)[Stage #n]]
]

#figure(
  scope: "parent",
  placement: top,
  kind: image,
  [
    #set text(hyphenate: false)
    #align(center)[
      #stack(
        dir: ttb,
        spacing: 0pt,

        rect(width: bw, fill: o-fill, stroke: 0.8pt + o-stroke, radius: 3pt, inset: (x: 8pt, y: 4pt))[
          #text(size: bs, weight: "bold")[CLI / management console]
          #text(size: ss, fill: luma(60))[ --- run launch, live logs, rubric scoring with trace evidence, cross-platform comparison]
        ],

        down-arrow(),

        grid(
          columns: (1fr, 1.6cm, 1fr), gutter: 0pt, align: horizon,
          comp-box(
            label: "Runner",
            detail: text(size: ss)[Orchestrates platforms × scenarios; resolves adapters via the registry, invokes the four stages in sequence, collects typed `StageResult` objects, audits the workspace after each stage.],
            w: 100%,
          ),
          side-arrow("ensures running"),
          comp-box(
            label: "Infrastructure",
            detail: [
              #text(size: ss)[Docker Compose profiles, health checks and service status for containerised platforms and tracing.]
              #v(1pt)
              #text(size: xs, fill: h-stroke)[Flowise · LangFlow · Dify · n8n · Langfuse]
            ],
            w: 100%,
          ),
        ),

        down-arrow(),

        grid(
          columns: (1fr, 1.6cm, 1fr), gutter: 0pt, align: horizon,
          comp-box(
            label: "Scenario loader",
            detail: text(size: ss)[Reads YAML scenario definitions, validates fields, resolves prompt templates and Gherkin acceptance criteria, builds the `StageContext`.],
            w: 100%,
          ),
          side-arrow("StageContext"),
          comp-box(
            label: "BasePlatformAdapter → ToolAgentAdapter / VisualAgentAdapter",
            detail: text(size: ss)[Four-method stage interface. `ToolAgentAdapter` supplies the shared stage template (prompts, tools, trace, retry, result); each platform implements one `_run_agent` method.],
            bg: a-fill, accent: a-stroke, w: 100%,
          ),
        ),

        align(center)[#v(2pt) #text(size: xs, fill: arr-col, style: "italic")[invokes the four-stage interface]],
        down-arrow(h: 4pt),

        rect(width: bw, fill: a-fill, stroke: 0.8pt + a-stroke, radius: 3pt, inset: 0pt)[
          #block(width: 100%, fill: a-stroke, radius: (top-left: 2pt, top-right: 2pt), inset: (x: 6pt, y: 3pt))[
            #text(size: bs, weight: "bold", fill: white)[Per-platform pipeline stages (planner → executor → reviewer inside each)]
          ]
          #pad(x: 6pt, y: 5pt)[
            #grid(
              columns: (1fr, auto, 1fr, auto, 1fr, auto, 1fr), gutter: 0pt, align: center + horizon,
              stage-box("generate_requirements()", 1), right-arrow,
              stage-box("generate_code()", 2), right-arrow,
              stage-box("generate_tests()", 3), right-arrow,
              stage-box("build_and_deploy()", 4),
            )
          ]
        ],

        down-arrow(),

        rect(width: bw, fill: luma(250), stroke: 0.5pt + luma(160), radius: 2pt, inset: (x: 8pt, y: 3pt))[
          #text(size: ss, weight: "bold")[StageResult]
          #text(size: ss, fill: luma(60))[ --- typed output carrying an `AgentTrace` (tokens, timing, tool calls, LLM spans)]
        ],

        down-arrow(),

        grid(
          columns: (1fr, 0.2cm, 1fr, 0.2cm, 1fr), gutter: 0pt, align: top,
          comp-box(
            label: "Metrics collector",
            detail: text(size: ss)[Framework metrics from the trace (rtc, tool-failure rate, latency, overhead); auto-derived rubric seeds; four cross-cutting 1--5 scores; variance across repeats.],
            bg: m-fill, accent: m-stroke, w: 100%,
          ),
          [],
          comp-box(
            label: "Result store (DuckDB)",
            detail: text(size: ss)[`runs` and `executions` tables; per-stage JSON and traces on disk; SQL-queryable and exportable.],
            bg: o-fill, accent: o-stroke, w: 100%,
          ),
          [],
          comp-box(
            label: "Observability",
            detail: text(size: ss)[Structured logs; Langfuse spans for every LLM call and tool call; LangSmith run trees where the platform emits them.],
            bg: x-fill, accent: x-stroke, w: 100%,
          ),
        ),
      )
    ]
  ],
  caption: [Harness architecture (logical view). Shared components are blue; the adapter layer and stages that each platform implements are orange.],
) <fig-arch>
