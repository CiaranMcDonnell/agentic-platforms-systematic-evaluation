"""
Chart export helpers for the DESMET dashboard.
Exports Plotly figures as PNG or SVG for the Typst report.
Requires the kaleido package.
"""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from .data import FIGURES_DIR

# A4 widths at 300 DPI
PRESETS = {
    "full_width": {"width": 1890, "height": 1181},   # ~160mm at 300 DPI
    "half_width": {"width": 886, "height": 591},      # ~75mm at 300 DPI
    "default": {"width": 800, "height": 500},
}


def export_figure(
    fig: go.Figure,
    name: str,
    fmt: str = "svg",
    preset: str = "default",
    width: int | None = None,
    height: int | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Export a Plotly figure to disk.

    Parameters
    ----------
    fig : The Plotly figure to export.
    name : Filename stem (e.g. "radar_all_platforms").
    fmt : "png" or "svg".
    preset : Size preset: "full_width", "half_width", or "default".
    width, height : Override preset dimensions (pixels).
    output_dir : Where to save. Defaults to docs/report/figures/.

    Returns
    -------
    Path to the saved file.
    """
    out = output_dir or FIGURES_DIR
    out.mkdir(parents=True, exist_ok=True)

    dims = PRESETS.get(preset, PRESETS["default"])
    w = width or dims["width"]
    h = height or dims["height"]

    path = out / f"{name}.{fmt}"
    fig.write_image(
        str(path),
        format=fmt,
        width=w,
        height=h,
        scale=2 if fmt == "png" else 1,
    )
    return path
