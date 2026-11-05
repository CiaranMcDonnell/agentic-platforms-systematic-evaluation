// Result figures drawn from docs/paper/data/summary.json (written by
// extract_reported_runs.py).  Every chart has the same row structure: one
// group per platform, one row per model, so the figures read side by side.
//
//   #import "../figures/results-charts.typ": *
//   #let summary = json("../data/summary.json")
//   #figure(range-chart(summary, "cost_usd", log: true, fmt: fmt-usd), caption: [...])
//
// Models are told apart by colour *and* marker shape (greyscale print);
// pipeline stages are ordered, so they use one blue ramp, light to dark.

#let platforms = (
  ("openai_agents_sdk", "OpenAI Agents SDK"),
  ("google_adk", "Google ADK"),
  ("langgraph", "LangGraph"),
  ("crewai", "CrewAI"),
  ("microsoft_agent_framework", "MS Agent Framework"),
)
#let stages = (
  ("requirements", "Requirements"),
  ("codegen", "Code generation"),
  ("testing", "Testing"),
  ("deploy", "Deploy"),
)
#let model-colors = (rgb("#2a78d6"), rgb("#eb6834"), rgb("#1baf7a"))
#let stage-colors = (rgb("#86b6ef"), rgb("#3987e5"), rgb("#1c5cab"), rgb("#0d366b"))
#let ink = luma(15%)
#let ink-muted = luma(40%)
#let grid-color = luma(88%)
#let text-size = 6.5pt

#let label-width = 2.35cm
#let row-height = 6.5pt
#let group-gap = 4pt

// ---------------------------------------------------------------- helpers

// Model labels in run order (as pinned), and their display names
// ("sonnet-5.5/US-001" -> "sonnet-5.5").
#let models-of(summary) = {
  let out = ()
  for c in summary.cells {
    if c.label not in out { out.push(c.label) }
  }
  out
}
#let model-name(label) = label.split("/").at(0)

#let cell-of(summary, label, platform) = {
  let found = summary.cells.filter(c => c.label == label and c.platform_id == platform)
  if found.len() == 0 { none } else { found.at(0) }
}

// Marker centred on (x, y) inside a `place`d canvas.
#let marker(i, x, y, r: 2.2pt, filled: true) = {
  let c = model-colors.at(i)
  let fill = if filled { c } else { white }
  let stroke = 0.6pt + c
  let shape = if i == 0 {
    circle(radius: r, fill: fill, stroke: stroke)
  } else if i == 1 {
    rect(width: 1.8 * r, height: 1.8 * r, fill: fill, stroke: stroke)
  } else {
    polygon(fill: fill, stroke: stroke, (r * 1.2, 0pt), (r * 2.4, r * 1.2), (r * 1.2, r * 2.4), (0pt, r * 1.2))
  }
  let half = if i == 1 { 0.9 * r } else if i == 2 { 1.2 * r } else { r }
  place(top + left, dx: x - half, dy: y - half, shape)
}

#let legend(models) = {
  set text(size: text-size, fill: ink)
  align(center, stack(dir: ltr, spacing: 8pt, ..models.enumerate().map(((i, m)) => box(
    stack(dir: ltr, spacing: 3pt, box(width: 5pt, height: 5pt, marker(i, 2.5pt, 2.5pt)), model-name(m)),
  ))))
}

#let fmt-usd(v) = {
  if v >= 1 { "$" + str(calc.round(v, digits: 1)) }
  else if v >= 0.1 { "$" + str(calc.round(v, digits: 2)) }
  else if v >= 0.01 { "$" + str(calc.round(v, digits: 3)) }
  else { "$" + str(calc.round(v, digits: 4)) }
}
#let fmt-count(v) = {
  if v >= 1e6 { str(calc.round(v / 1e6, digits: 1)) + "M" }
  else if v >= 1e3 { str(calc.round(v / 1e3, digits: 0)) + "k" }
  else { str(calc.round(v, digits: 0)) }
}

// Axis ticks covering [lo, hi]: decades (with 2 and 5 when the span is short)
// on a log axis, 1/2/5 steps on a linear one starting at zero.
#let ticks-for(lo, hi, log) = {
  if log {
    let a = calc.floor(calc.log(lo, base: 10))
    let b = calc.ceil(calc.log(hi, base: 10))
    let mults = if b - a <= 2 { (1, 2, 5) } else { (1,) }
    let out = ()
    for k in range(a, b + 1) {
      for m in mults {
        let t = m * calc.pow(10.0, k)
        if t >= calc.pow(10.0, a) and t <= calc.pow(10.0, b) { out.push(t) }
      }
    }
    out
  } else {
    let raw = hi / 4
    let mag = calc.pow(10.0, calc.floor(calc.log(raw, base: 10)))
    let step = if raw / mag <= 1 { mag } else if raw / mag <= 2 { 2 * mag } else if raw / mag <= 5 { 5 * mag } else { 10 * mag }
    range(0, calc.ceil(hi / step) + 1).map(k => k * step)
  }
}

// ---------------------------------------------------------------- range chart

// Median (filled marker), range over repeats (line) and each repeat (small
// hollow dots) for one statistic, per platform x model.  `metric` is a key
// of a cell ("cost_usd", "tokens_total", "prompt_tokens_per_call", ...);
// `stage` reads the per-stage statistic instead.
#let range-chart(summary, metric, stage: none, log: false, fmt: fmt-count, width: 8.6cm, unit: none) = {
  let models = models-of(summary)
  let stat-of(cell) = if cell == none { none } else if stage == none { cell.at(metric) } else { cell.stages.at(stage).at(metric) }

  let all = ()
  for (pid, _) in platforms {
    for m in models {
      let s = stat-of(cell-of(summary, m, pid))
      if s != none { all += s.values.filter(v => v != none and (not log or v > 0)) }
    }
  }
  if all.len() == 0 { return text(size: text-size)[no data] }
  let ticks = ticks-for(calc.min(..all), calc.max(..all), log)
  let lo = ticks.first()
  let hi = ticks.last()
  let plot-w = width - label-width
  let xpos(v) = if log {
    plot-w * (calc.log(v, base: 10) - calc.log(lo, base: 10)) / (calc.log(hi, base: 10) - calc.log(lo, base: 10))
  } else {
    plot-w * (v - lo) / (hi - lo)
  }

  let group-h = models.len() * row-height
  let plot-h = platforms.len() * group-h + (platforms.len() - 1) * group-gap
  set text(size: text-size, fill: ink)

  let canvas = box(width: plot-w, height: plot-h, {
    for t in ticks {
      place(top + left, line(start: (xpos(t), 0pt), end: (xpos(t), plot-h), stroke: 0.4pt + grid-color))
    }
    for (g, (pid, _)) in platforms.enumerate() {
      let y0 = g * (group-h + group-gap)
      for (i, m) in models.enumerate() {
        let y = y0 + (i + 0.5) * row-height
        let s = stat-of(cell-of(summary, m, pid))
        if s == none or s.median == none {
          place(top + left, dx: 1pt, dy: y - 3pt, text(fill: ink-muted, size: 5.5pt)[n/a])
          continue
        }
        place(top + left, line(start: (xpos(s.min), y), end: (xpos(s.max), y), stroke: 0.8pt + model-colors.at(i)))
        for v in s.values.filter(v => v != none) {
          marker(i, xpos(v), y, r: 1.1pt, filled: false)
        }
        marker(i, xpos(s.median), y)
        if s.n < s.values.len() {
          // Some repeats unknown: say how many values the statistic covers.
          place(top + left, dx: xpos(s.max) + 3pt, dy: y - 3pt, text(fill: ink-muted, size: 5.5pt)[n=#s.n])
        }
      }
    }
  })

  let labels = box(width: label-width, height: plot-h, {
    for (g, (_, name)) in platforms.enumerate() {
      let y0 = g * (group-h + group-gap)
      place(top + left, dy: y0, box(height: group-h, width: label-width - 4pt, align(right + horizon, name)))
    }
  })

  let axis = box(width: plot-w, height: 8pt, {
    place(top + left, line(start: (0pt, 0pt), end: (plot-w, 0pt), stroke: 0.5pt + ink-muted))
    for t in ticks {
      place(top + left, dx: xpos(t) - 15pt, dy: 1.5pt, box(width: 30pt, align(center, text(fill: ink-muted, fmt(t)))))
    }
  })

  block(width: width, {
    legend(models)
    v(3pt)
    grid(columns: (label-width, plot-w), row-gutter: 0pt, labels, canvas, [], axis)
    if unit != none { align(right, text(fill: ink-muted, unit)) }
  })
}

// ---------------------------------------------------------------- stage shares

// Share of each execution's cost (or tokens) spent in each stage: the
// median per stage, normalised to 100%, with the median total at the end.
#let stage-share-chart(summary, metric: "cost_usd", fmt: fmt-usd, width: 8.6cm) = {
  let models = models-of(summary)
  let total-w = 1.1cm
  let plot-w = width - label-width - 1.1cm - total-w
  let bar-h = row-height - 1.6pt
  set text(size: text-size, fill: ink)

  let rows = ()
  for (pid, name) in platforms {
    for (i, m) in models.enumerate() {
      let cell = cell-of(summary, m, pid)
      let parts = if cell == none { () } else {
        stages.map(((sid, _)) => cell.stages.at(sid).at(metric).median)
      }
      let known = parts.filter(p => p != none)
      let sum = known.fold(0, (a, b) => a + b)
      let bar = if sum == 0 or known.len() < parts.len() {
        text(fill: ink-muted, size: 5.5pt)[n/a]
      } else {
        box(width: plot-w, height: bar-h, {
          let x = 0pt
          for (k, p) in parts.enumerate() {
            let w = plot-w * p / sum
            // 0.5pt surface gap between segments.
            place(top + left, dx: x, rect(width: calc.max(w - 0.5pt, 0pt), height: bar-h, fill: stage-colors.at(k), stroke: none))
            x += w
          }
        })
      }
      let total = if cell == none or cell.at(metric).median == none { [] } else { fmt(cell.at(metric).median) }
      rows.push((
        if i == 0 { name } else { [] },
        box(width: 5pt, height: 5pt, marker(i, 2.5pt, 2.5pt, r: 1.8pt)),
        bar,
        pad(left: 2.5pt, text(fill: ink-muted, total)),
      ))
    }
  }

  let stage-legend = align(center, stack(dir: ltr, spacing: 7pt, ..stages.enumerate().map(((k, (_, sname))) => box(
    stack(dir: ltr, spacing: 2.5pt, box(width: 6pt, height: 5pt, fill: stage-colors.at(k)), sname),
  ))))

  block(width: width, {
    stage-legend
    v(1pt)
    legend(models)
    v(3pt)
    grid(
      columns: (label-width - 0.2cm, 0.5cm, plot-w, total-w + 0.8cm),
      column-gutter: 0pt,
      row-gutter: (..range(rows.len() - 1).map(r => if calc.rem(r + 1, models.len()) == 0 { group-gap + 1.6pt } else { 1.6pt })),
      align: (right + horizon, center + horizon, left + horizon, left + horizon),
      ..rows.flatten(),
    )
  })
}

// ---------------------------------------------------------------- criteria heatmap

// Hidden acceptance criteria met, per platform x model x criterion: each
// cell shows passes / repeats, shaded by the pass rate on the blue ramp.
// It is built from a table: wrap it in figure(kind: image, ...) so it is
// numbered as a figure.
#let criteria-heatmap(summary, width: 8.6cm) = {
  let models = models-of(summary)
  let criteria = ()
  for c in summary.cells {
    for k in c.correctness.per_criterion.keys() {
      if k not in criteria { criteria.push(k) }
    }
  }
  criteria = criteria.sorted()
  let ramp = (rgb("#f1f1ee"), rgb("#cde2fb"), rgb("#86b6ef"), rgb("#3987e5"), rgb("#1c5cab"))
  let shade(rate) = ramp.at(calc.min(calc.floor(rate * (ramp.len() - 1) + 0.5), ramp.len() - 1))
  set text(size: text-size, fill: ink)

  let short(k) = k.split("-").last()
  let header = ([],) + models.enumerate().map(((i, m)) => table.cell(colspan: criteria.len(), align: center,
    stack(dir: ltr, spacing: 3pt, box(width: 5pt, height: 5pt, marker(i, 2.5pt, 2.5pt, r: 1.8pt)), model-name(m))))
  let sub = ([],) + models.map(_ => criteria.map(k => text(fill: ink-muted, "AC" + short(k)))).flatten()
  let body = ()
  for (pid, name) in platforms {
    body.push(align(right, pad(right: 2pt, name)))
    for m in models {
      let cell = cell-of(summary, m, pid)
      for k in criteria {
        if cell == none or k not in cell.correctness.per_criterion {
          body.push(table.cell(fill: white, text(fill: ink-muted)[--]))
        } else {
          let n = cell.correctness.executions
          let met = cell.correctness.per_criterion.at(k)
          let rate = if n == 0 { 0 } else { met / n }
          body.push(table.cell(fill: shade(rate), text(fill: if rate >= 0.7 { white } else { ink }, [#met/#n])))
        }
      }
    }
  }
  block(width: width, table(
    columns: (label-width,) + (1fr,) * (models.len() * criteria.len()),
    align: center + horizon,
    inset: (x: 1pt, y: 2.2pt),
    stroke: (x, y) => if x > 0 and calc.rem(x - 1, criteria.len()) == 0 { (left: 1.5pt + white) } else { (left: 0.4pt + white, top: 0.4pt + white) },
    table.header(..header, ..sub),
    ..body,
  ))
}
