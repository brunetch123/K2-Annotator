"""
Render the K2 Annotator architecture diagram.

Run:  python docs/make_architecture_diagram.py

Outputs docs/architecture.png and docs/architecture.svg.

The diagram is laid out in three horizontal lanes:
  - Top lane: external preprocessing (vendor file -> mzML -> MZmine, or MS-DIAL)
  - Middle lane: the K2 internal suspect-screening workflow
  - Bottom lane: the parallel surrogate-recovery workflow
With outputs collected on the right.
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
FIG_W, FIG_H = 17.0, 10.5

# Lane y-centers
Y_EXTERNAL = 8.6
Y_PIPELINE = 5.6
Y_SURROGATE = 2.4
Y_OUTPUTS = 5.6

# Box sizes
BOX_W = 2.2
BOX_H = 0.95
SMALL_W = 1.55
TOOL_H = 0.55  # for the "MSconvert" / "MZmine" tool labels along an arrow

# Colors (muted, print-friendly)
C_EXTERNAL = "#d6e9f5"
C_EXTERNAL_EDGE = "#3b6e8f"
C_TOOL = "#fce8c2"
C_TOOL_EDGE = "#a87a25"
C_PIPELINE = "#dde8d6"
C_PIPELINE_EDGE = "#4f7a3a"
C_SURROGATE = "#f0d8e2"
C_SURROGATE_EDGE = "#8e3a64"
C_OUTPUT = "#e7e1f0"
C_OUTPUT_EDGE = "#583c7a"
C_DECISION = "#fdf3c4"
C_DECISION_EDGE = "#a08623"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def draw_box(ax, x, y, label, *, w=BOX_W, h=BOX_H,
             face=C_PIPELINE, edge=C_PIPELINE_EDGE, fontsize=9, bold=False):
    """Draw a labeled rounded box centered at (x, y)."""
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.04,rounding_size=0.12",
        linewidth=1.4, edgecolor=edge, facecolor=face,
    )
    ax.add_patch(patch)
    weight = "bold" if bold else "normal"
    ax.text(x, y, label, ha="center", va="center",
            fontsize=fontsize, fontweight=weight, wrap=True)


def draw_arrow(ax, x0, y0, x1, y1, *, label=None, label_offset=(0, 0.18),
               style="->", color="#444", linewidth=1.4,
               connectionstyle="arc3,rad=0"):
    """Draw an arrow between two points; optional label at the midpoint."""
    arrow = FancyArrowPatch(
        (x0, y0), (x1, y1),
        arrowstyle=style, mutation_scale=14,
        linewidth=linewidth, color=color,
        connectionstyle=connectionstyle,
        shrinkA=2, shrinkB=2,
    )
    ax.add_patch(arrow)
    if label is not None:
        mx, my = (x0 + x1) / 2 + label_offset[0], (y0 + y1) / 2 + label_offset[1]
        ax.text(mx, my, label, ha="center", va="center",
                fontsize=8, color=color,
                bbox=dict(boxstyle="round,pad=0.18",
                          fc="white", ec="none", alpha=0.9))


def draw_lane_label(ax, y, text, color):
    """Left-edge lane label."""
    ax.text(0.08, y, text, ha="left", va="center",
            fontsize=10, fontweight="bold", color=color)


# ---------------------------------------------------------------------------
# Build the diagram
# ---------------------------------------------------------------------------
def main():
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.set_xlim(0, 17)
    ax.set_ylim(0, 10.5)
    ax.set_aspect("equal")
    ax.axis("off")

    # Title
    ax.text(8.5, 10.1, "K2 Annotator — Architecture",
            ha="center", va="center", fontsize=14, fontweight="bold")
    ax.text(8.5, 9.7,
            "External preprocessing (top) feeds K2 Annotator (middle); "
            "surrogate recovery runs in parallel (bottom).",
            ha="center", va="center", fontsize=9, color="#555")

    # ----- LANE 1: external preprocessing -----
    draw_lane_label(ax, Y_EXTERNAL + 0.7, "External Preprocessing", C_EXTERNAL_EDGE)

    # Vendor raw -> MSconvert -> mzML -> MZmine -> quant + MSP
    draw_box(ax, 1.7, Y_EXTERNAL,
             "Vendor raw data\n(.d / .raw / .wiff)",
             face=C_EXTERNAL, edge=C_EXTERNAL_EDGE)
    draw_box(ax, 5.2, Y_EXTERNAL, "mzML files",
             face=C_EXTERNAL, edge=C_EXTERNAL_EDGE)
    draw_box(ax, 8.7, Y_EXTERNAL,
             "MZmine outputs\n(quant CSV + MSP)",
             face=C_EXTERNAL, edge=C_EXTERNAL_EDGE)

    # Tool labels along the arrows (MSconvert, MZmine)
    draw_arrow(ax, 1.7 + BOX_W / 2, Y_EXTERNAL, 5.2 - BOX_W / 2, Y_EXTERNAL,
               label="MSconvert", color=C_TOOL_EDGE)
    draw_arrow(ax, 5.2 + BOX_W / 2, Y_EXTERNAL, 8.7 - BOX_W / 2, Y_EXTERNAL,
               label="MZmine", color=C_TOOL_EDGE)

    # Alternative MS-DIAL entry point (joins downstream)
    draw_box(ax, 8.7, Y_EXTERNAL - 1.4,
             "MS-DIAL outputs\n(Area.txt + MSP)",
             face=C_EXTERNAL, edge=C_EXTERNAL_EDGE, fontsize=8.5)
    ax.text(5.2, Y_EXTERNAL - 1.4, "(alternative entry point)",
            ha="center", va="center", fontsize=9,
            color="#666", style="italic")

    # ----- LANE 2: K2 internal pipeline -----
    draw_lane_label(ax, Y_PIPELINE + 0.85, "K2 Annotator", C_PIPELINE_EDGE)

    # Universal parser
    draw_box(ax, 1.6, Y_PIPELINE,
             "Universal Parser\n(auto-detect format)",
             face=C_PIPELINE, edge=C_PIPELINE_EDGE, bold=True)

    # Optional IS normalization (decision-style box)
    draw_box(ax, 4.1, Y_PIPELINE,
             "IS Normalization\n(optional, max/IS factor)",
             face=C_DECISION, edge=C_DECISION_EDGE)

    # BFF
    draw_box(ax, 6.6, Y_PIPELINE,
             "Blank Feature Filtering\n(standard or adjusted)",
             face=C_PIPELINE, edge=C_PIPELINE_EDGE)

    # Library matching
    draw_box(ax, 9.1, Y_PIPELINE,
             "Level 2 Library Match\n(RI ± dot products)",
             face=C_PIPELINE, edge=C_PIPELINE_EDGE)

    # RHRMF
    draw_box(ax, 11.6, Y_PIPELINE,
             "RHRMF check\n(low-res library entries)",
             face=C_PIPELINE, edge=C_PIPELINE_EDGE)

    # Hazards
    draw_box(ax, 14.0, Y_PIPELINE,
             "Hazard Screening\n(EPA CompTox)",
             face=C_PIPELINE, edge=C_PIPELINE_EDGE)

    # Pipeline arrows
    pipeline_xs = [1.6, 4.1, 6.6, 9.1, 11.6, 14.0]
    for x_a, x_b in zip(pipeline_xs[:-1], pipeline_xs[1:]):
        draw_arrow(ax, x_a + BOX_W / 2, Y_PIPELINE,
                   x_b - BOX_W / 2, Y_PIPELINE)

    # MZmine -> Parser
    draw_arrow(ax, 8.7, Y_EXTERNAL - BOX_H / 2,
               1.6, Y_PIPELINE + BOX_H / 2,
               connectionstyle="arc3,rad=-0.18")
    # MS-DIAL -> Parser
    draw_arrow(ax, 8.7 - BOX_W / 2, Y_EXTERNAL - 1.4,
               1.6, Y_PIPELINE + BOX_H / 2,
               connectionstyle="arc3,rad=-0.30",
               color="#888")

    # ----- LANE 3: surrogate recovery -----
    draw_lane_label(ax, Y_SURROGATE + 0.85,
                    "Surrogate Recovery (parallel)", C_SURROGATE_EDGE)

    draw_box(ax, 4.1, Y_SURROGATE,
             "Surrogate library\n(user CSV/MSP)",
             face=C_SURROGATE, edge=C_SURROGATE_EDGE)
    draw_box(ax, 6.6, Y_SURROGATE,
             "Surrogate match\n(skip BFF; best per cmpd)",
             face=C_SURROGATE, edge=C_SURROGATE_EDGE)
    draw_box(ax, 9.1, Y_SURROGATE,
             "% Recovery\n(vs reference samples)",
             face=C_SURROGATE, edge=C_SURROGATE_EDGE)

    # Surrogate flow arrows
    draw_arrow(ax, 4.1 + BOX_W / 2, Y_SURROGATE,
               6.6 - BOX_W / 2, Y_SURROGATE,
               color=C_SURROGATE_EDGE)
    draw_arrow(ax, 6.6 + BOX_W / 2, Y_SURROGATE,
               9.1 - BOX_W / 2, Y_SURROGATE,
               color=C_SURROGATE_EDGE)

    # Parser feature list -> surrogate match (after IS norm if enabled)
    draw_arrow(ax, 4.1, Y_PIPELINE - BOX_H / 2,
               6.6, Y_SURROGATE + BOX_H / 2,
               connectionstyle="arc3,rad=0.18",
               color=C_SURROGATE_EDGE,
               label="features\n(post-IS, pre-BFF)",
               label_offset=(-1.0, 0.05))

    # ----- LANE 4: outputs (collected on the right side) -----
    out_x = 14.5
    out_ys = [Y_PIPELINE - 2.0, Y_PIPELINE - 2.95, Y_PIPELINE - 3.9]
    out_labels = [
        "Match CSV\n+ feature & match summary CSVs",
        "Surrogate recovery CSV",
        "PDF report\n(summary + per-match pages)",
    ]
    # Place the Outputs lane label above the output boxes, on the right
    ax.text(out_x, out_ys[0] + 0.85, "Outputs",
            ha="center", va="center",
            fontsize=10, fontweight="bold", color=C_OUTPUT_EDGE)
    for y, lbl in zip(out_ys, out_labels):
        draw_box(ax, out_x, y, lbl,
                 face=C_OUTPUT, edge=C_OUTPUT_EDGE,
                 w=2.6, h=0.8, fontsize=8.5)

    # Hazard step -> Match CSV / PDF
    draw_arrow(ax, 14.0, Y_PIPELINE - BOX_H / 2,
               out_x - 1.3, out_ys[0],
               connectionstyle="arc3,rad=-0.10",
               color=C_OUTPUT_EDGE)
    draw_arrow(ax, 14.0, Y_PIPELINE - BOX_H / 2,
               out_x - 1.3, out_ys[2],
               connectionstyle="arc3,rad=-0.32",
               color=C_OUTPUT_EDGE)
    # Surrogate % Recovery -> Surrogate CSV and PDF (surrogate pages)
    draw_arrow(ax, 9.1 + BOX_W / 2, Y_SURROGATE,
               out_x - 1.3, out_ys[1],
               connectionstyle="arc3,rad=-0.20",
               color=C_OUTPUT_EDGE)
    draw_arrow(ax, 9.1 + BOX_W / 2, Y_SURROGATE,
               out_x - 1.3, out_ys[2] - 0.18,
               connectionstyle="arc3,rad=0.18",
               color=C_OUTPUT_EDGE)

    # Lane separator lines (subtle)
    for y_sep in (7.4, 4.1):
        ax.plot([0.05, 16.95], [y_sep, y_sep],
                color="#dddddd", linewidth=0.8, zorder=0)

    # Legend strip at the bottom — fixed-stride spacing so all five items
    # fit horizontally inside the figure.
    legend_y = 0.55
    legend_items = [
        ("External tool / file", C_EXTERNAL, C_EXTERNAL_EDGE),
        ("Optional step", C_DECISION, C_DECISION_EDGE),
        ("K2 pipeline step", C_PIPELINE, C_PIPELINE_EDGE),
        ("Surrogate workflow", C_SURROGATE, C_SURROGATE_EDGE),
        ("Output file", C_OUTPUT, C_OUTPUT_EDGE),
    ]
    n = len(legend_items)
    stride = 15.5 / n  # leaves 0.75 unit margin each side
    x0 = 0.75
    for i, (label, fc, ec) in enumerate(legend_items):
        x = x0 + i * stride
        sw = FancyBboxPatch(
            (x, legend_y - 0.18), 0.45, 0.36,
            boxstyle="round,pad=0.02,rounding_size=0.07",
            facecolor=fc, edgecolor=ec, linewidth=1.2,
        )
        ax.add_patch(sw)
        ax.text(x + 0.55, legend_y, label, ha="left", va="center", fontsize=9)

    here = Path(__file__).resolve().parent
    out_png = here / "architecture.png"
    out_svg = here / "architecture.svg"
    fig.tight_layout()
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_svg, bbox_inches="tight", facecolor="white")
    print(f"Wrote {out_png}")
    print(f"Wrote {out_svg}")


if __name__ == "__main__":
    main()
