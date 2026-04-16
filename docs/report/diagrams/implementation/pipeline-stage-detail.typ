// Pipeline Stage Detail — injected into report via #include
// Portrait-friendly tables showing per-stage metrics and dimension formulas

#let dim-fill = rgb("#fff8e1")

#figure(
  placement: top,
  kind: table,
  table(
    columns: (2.5cm, 1fr, 1fr),
    align: (left, left, left),
    stroke: 0.5pt + luma(180),
    inset: 7pt,

    table.cell(fill: luma(230))[#text(weight: "bold", size: 8pt)[Stage]],
    table.cell(fill: luma(230))[#text(weight: "bold", size: 8pt)[Stage-Specific Metrics]],
    table.cell(fill: luma(230))[#text(weight: "bold", size: 8pt)[Key Outputs]],

    [#text(weight: "bold", size: 7.5pt)[1 — Requirements \ & Design]],
    [#text(size: 7pt)[
      - Requirement completeness (%) \
      - Requirement quality (rubric 0–3) \
      - Traceability (rubric 0–3) \
      - Design completeness (rubric 0–3) \
      - Design correctness (rubric 0–3) \
      - Parseable UML (binary)
    ]],
    [#text(size: 7pt)[
      - Structured requirements \
      - Acceptance criteria \
      - UML class diagrams (Mermaid) \
      - UML sequence diagrams
    ]],

    [#text(weight: "bold", size: 7.5pt)[2 — Code \ Generation]],
    [#text(size: 7pt)[
      - Functional correctness (binary) \
      - Completeness (%) \
      - Code quality (rubric 0–3) \
      - Adherence to design (rubric 0–3)
    ]],
    [#text(size: 7pt)[
      - Source code files \
      - Execution logs \
      - Agent traces
    ]],

    [#text(weight: "bold", size: 7.5pt)[3 — Test \ Generation]],
    [#text(size: 7pt)[
      - Test pass rate (%) \
      - Test coverage (%) \
      - Test quality (rubric 0–3)
    ]],
    [#text(size: 7pt)[
      - Test suites \
      - Coverage reports \
      - Test execution logs
    ]],

    [#text(weight: "bold", size: 7.5pt)[4 — Build & \ Deploy]],
    [#text(size: 7pt)[
      - Build success (binary) \
      - Deploy success (binary) \
      - Configuration effort (rubric 0–3)
    ]],
    [#text(size: 7pt)[
      - Build artifacts \
      - Container images \
      - Health check evidence
    ]],
  ),
  caption: [Pipeline Stage Detail — per-stage metrics and key outputs. All stages also record token usage (input/output/total), API cost (USD), wall-clock time (s), and human interventions (count).],
) <fig-stage-detail>

#v(0.3cm)

#figure(
  placement: top,
  kind: table,
  table(
    columns: (0.5cm, 2.2cm, 1fr, 1fr),
    align: (center, left, left, left),
    stroke: 0.5pt + luma(180),
    inset: 7pt,

    table.cell(fill: dim-fill)[#text(weight: "bold", size: 7.5pt)[\#]],
    table.cell(fill: dim-fill)[#text(weight: "bold", size: 7.5pt)[Dimension]],
    table.cell(fill: dim-fill)[#text(weight: "bold", size: 7.5pt)[What Is Measured]],
    table.cell(fill: dim-fill)[#text(weight: "bold", size: 7.5pt)[Aggregation Formula]],

    [1], [#text(weight: "bold", size: 7.5pt)[Effectiveness]],
    [#text(size: 7pt)[Capability tier, correctness, completeness across all stages]],
    [#text(size: 6.5pt)[$(S_"supported" / S_"total") times 0.4 + overline(C_"correct") times 0.3 + overline(C_"complete") times 0.3$, scaled to 1–5]],

    [2], [#text(weight: "bold", size: 7.5pt)[Efficiency]],
    [#text(size: 7pt)[Token usage, wall-clock time, API cost]],
    [#text(size: 6.5pt)[Rank-normalised across platforms: lowest resource consumption = 5]],

    [3], [#text(weight: "bold", size: 7.5pt)[Quality]],
    [#text(size: 7pt)[All qualitative rubric scores (0–3) across stages]],
    [#text(size: 6.5pt)[$overline(R_"all") times 5 / 3$]],

    [4], [#text(weight: "bold", size: 7.5pt)[Autonomy]],
    [#text(size: 7pt)[Human interventions across all stages]],
    [#text(size: 6.5pt)[$5 - min(4, overline(I_"per-stage"))$]],
  ),
  caption: [Cross-cutting evaluation dimensions with aggregation formulas (Layer 3 benchmarking, 1–5 Likert scale).],
) <fig-dimension-formulas>
