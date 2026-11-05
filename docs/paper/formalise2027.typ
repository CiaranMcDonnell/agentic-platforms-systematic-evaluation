// FormaliSE 2027 submission — entry point (compile this file).
// Double-anonymous: authors deliberately empty; do not set document(author:).
#import "@preview/charged-ieee:0.1.4": ieee

#show: ieee.with(
  title: [A Reproducible Harness for Framework-Centric Evaluation of Agentic Platforms on Software Engineering Pipelines],
  abstract: include "sections/00-abstract.typ",
  authors: (),
  index-terms: ("agentic platforms", "LLM agents", "evaluation harness", "DESMET", "software engineering pipelines"),
  bibliography: bibliography("references.bib", style: "ieee"),
)

#include "sections/01-introduction.typ"
#include "sections/02-related.typ"
#include "sections/03-framework.typ"
#include "sections/04-harness.typ"
#include "sections/05-setup.typ"
#include "sections/06-results.typ"
#include "sections/07-threats.typ"
#include "sections/08-conclusion.typ"
#include "sections/09-data-availability.typ"
