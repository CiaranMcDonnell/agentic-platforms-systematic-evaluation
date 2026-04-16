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
  set par(leading: 0.6em * 1.2, spacing: 1em, first-line-indent: 0cm)

  set heading(numbering: "1.1.1")
  show heading.where(level: 1): it => {
    pagebreak(weak: true)
    v(0.3cm)
    if it.numbering != none {
      text(size: 20pt, weight: "bold")[Chapter #counter(heading).display(): #it.body]
    } else {
      text(size: 20pt, weight: "bold")[#it.body]
    }
    v(0.15cm)
    line(length: 5cm, stroke: 0.5pt)
    v(0.5cm)
  }
  show heading.where(level: 2): it => {
    v(0.4cm)
    text(size: 16pt, weight: "bold")[#counter(heading).display() #it.body]
    v(0.2cm)
  }
  show heading.where(level: 3): it => {
    v(0.3cm)
    text(size: 13pt, weight: "bold")[#counter(heading).display() #it.body]
    v(0.1cm)
  }
  show heading.where(level: 4): it => {
    v(0.2cm)
    text(size: 11pt, weight: "bold")[#counter(heading).display() #it.body]
    v(0.1cm)
  }

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
