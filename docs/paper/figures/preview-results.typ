// Preview of the result figures at IEEE column width.
//   typst compile docs/paper/figures/preview-results.typ
// reads docs/paper/data/summary.json; to preview another summary, pass
//   --root <dir> --input summary=/<path under root>
#import "results-charts.typ": *

#set page(width: 9.4cm, height: auto, margin: 0.4cm)
#set text(font: "TeX Gyre Termes", size: 10pt)

#let summary = json(sys.inputs.at("summary", default: "../data/summary.json"))

#figure(range-chart(summary, "cost_usd", log: true, fmt: fmt-usd),
  caption: [Cost per execution: median (filled), range and each repeat (hollow).])

#figure(range-chart(summary, "prompt_tokens_per_call", fmt: fmt-count),
  caption: [Prompt tokens per LLM call.])

#figure(stage-share-chart(summary),
  caption: [Share of cost per stage (median per stage, normalised); median total at right.])

#figure(kind: image, criteria-heatmap(summary),
  caption: [Hidden acceptance criteria met / repeats.])
