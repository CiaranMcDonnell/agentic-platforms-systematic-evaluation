// =============================================================================
// UCD CS FYP Report — Shared Template
// Systematic Evaluation of Agentic Platforms
// =============================================================================

// ---------------------------------------------------------------------------
// Package imports
// ---------------------------------------------------------------------------

#import "@preview/codly:1.3.0": *
#import "@preview/booktabs:0.0.4": *

// ---------------------------------------------------------------------------
// Project details
// ---------------------------------------------------------------------------

#let student-name = "Ciaran McDonnell"
#let student-id = "21320201"
#let project-title = "Systematic Evaluation of Agentic Platforms"
#let supervisor-name = "Alessio Ferrari"

// ---------------------------------------------------------------------------
// Colored verdict cells for result tables (Yes / Partial / No, etc.)
// ---------------------------------------------------------------------------

#let yes-cell = table.cell(fill: rgb("#A5D6A7"))[Yes]
#let no-cell = table.cell(fill: rgb("#EF9A9A"))[No]
#let partial-cell = table.cell(fill: rgb("#FFE0B2"))[Partial]
#let cost-only-cell = table.cell(fill: rgb("#FFE0B2"))[Cost only]

// Pipeline / adapter status verdicts
#let supported-cell = table.cell(fill: rgb("#A5D6A7"))[Supported]
#let not-supported-cell = table.cell(fill: rgb("#EF9A9A"))[Not Supported]
#let implemented-cell = table.cell(fill: rgb("#A5D6A7"))[Implemented]
#let completed-cell = table.cell(fill: rgb("#A5D6A7"))[Completed]
#let failed-cell = table.cell(fill: rgb("#EF9A9A"))[Failed]

// Numeric score coloring (used for 0--5 dimension aggregates): wrap a value
// and it picks green / orange / red based on standard thresholds.
#let score-cell(value, good: 4.0, mid: 3.0) = {
  let v = float(value)
  let fill = if v >= good { rgb("#A5D6A7") }
    else if v >= mid { rgb("#FFE0B2") }
    else { rgb("#EF9A9A") }
  table.cell(fill: fill)[#value]
}

// ---------------------------------------------------------------------------
// Document template — apply with #show: template
// ---------------------------------------------------------------------------

#let template(body) = {
  set document(
    title: project-title,
    author: student-name,
  )

  set page(
    paper: "a4",
    margin: (left: 3cm, right: 2.5cm, top: 2.5cm, bottom: 2cm),
    header: [],
    footer: context {
      let num = page.numbering
      if num != none {
        set align(center)
        set text(size: 9pt)
        [Page #counter(page).display(num)]
      }
    },
  )

  set text(font: "Arial", size: 11pt)
  // Discourage single-line widows/orphans across page breaks.
  set text(costs: (hyphenation: 100%, runt: 100%, widow: 250%, orphan: 250%))
  set par(
    leading: 0.65em,
    spacing: 0.8em,
    first-line-indent: (amount: 1.5em, all: true),
    justify: true,
  )

  set figure(placement: auto)

  // Disable hyphenation and justification in all headings to avoid breaks like
  // "Plat-\nforms" and to avoid huge inter-word gaps when a heading wraps.
  show heading: set text(hyphenate: false)
  show heading: set par(justify: false, first-line-indent: 0em)
  // Figure and table captions should also be left-ragged (not justified) so the
  // trailing short line doesn't stretch.
  show figure.caption: set par(first-line-indent: 0em)

  set heading(numbering: "1.1.1")
  show heading.where(level: 1): it => {
    if it.numbering != none {
      pagebreak(weak: true)
    }
    v(0.2cm)
    if it.numbering != none {
      text(size: 20pt, weight: "bold")[Chapter #counter(heading).display(): #it.body]
    } else {
      text(size: 20pt, weight: "bold")[#it.body]
    }
    v(0.1cm)
    line(length: 5cm, stroke: 0.5pt)
    v(0.35cm)
  }
  show heading.where(level: 2): it => {
    v(0.3cm)
    text(size: 16pt, weight: "bold")[#counter(heading).display() #it.body]
    v(0.1cm)
  }
  show heading.where(level: 3): it => {
    v(0.2cm)
    text(size: 13pt, weight: "bold")[#counter(heading).display() #it.body]
    v(0.05cm)
  }
  show heading.where(level: 4): it => {
    v(0.15cm)
    text(size: 11pt, weight: "bold")[#counter(heading).display() #it.body]
    v(0.05cm)
  }

  // Left-align and justify figure/table captions (Typst centers them by default,
  // which produces ragged multi-line captions).
  show figure.caption: set align(left)
  show figure.caption: set par(justify: true)

  // Disable justification inside table cells — narrow cells with justified text
  // create large inter-word gaps ("rivers"). Ragged-right reads better.
  show table.cell: set par(justify: false)

  // Allow long tables to split across pages instead of being hoisted whole.
  show figure.where(kind: table): set block(breakable: true)

  // Hyperlink styling
  show link: set text(fill: blue)

  // Booktabs table styling (clean academic tables, no vertical rules)
  show: booktabs-default-table-style

  // Codly code block styling
  show: codly-init.with()
  codly(
    languages: (
      python: (name: "Python", color: rgb("#3572A5")),
      yaml: (name: "YAML", color: rgb("#CB171E")),
      bash: (name: "Bash", color: rgb("#4EAA25")),
    ),
  )

  body
}
