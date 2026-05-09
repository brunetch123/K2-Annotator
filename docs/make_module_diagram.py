"""
Render the module-level dependency diagram for K2 Annotator.

Run:  python docs/make_module_diagram.py

Outputs docs/modules.png and docs/modules.svg.

Design:
  - Boxes are Python files in the repo (with their key
    classes/functions).
  - Parallelograms are *data objects* that flow between the modules.
  - Arrow routing is strictly orthogonal (only horizontal and vertical
    segments) and runs in dedicated channels so lines do not cross
    boxes or each other.
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon


# Canvas
W, H = 24.0, 17.0

# Color palette per role: (face, edge)
C_GUI = ("#dde6f5", "#3f5a86")
C_DRIVER = ("#fce8c2", "#a87a25")
C_EXTERNAL = ("#eaeaea", "#666666")
C_CORE = ("#dde8d6", "#4f7a3a")
C_CORE_DEEP = ("#bbd2ac", "#34581f")
C_HELPER = ("#eaf1e3", "#5e8a45")
C_SURROGATE = ("#f0d8e2", "#8e3a64")
C_REPORT = ("#e7e1f0", "#583c7a")
C_DATA = ("#fff5d6", "#a08623")  # parallelogram for data objects


# ---------------------------------------------------------------------------
# Drawing primitives
# ---------------------------------------------------------------------------
def draw_module(ax, x, y, filename, body="", *,
                w=3.0, h=1.20, palette=C_CORE,
                header_size=10, body_size=8.5):
    """A module box: file name in monospace bold + class/function list."""
    fc, ec = palette
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.04,rounding_size=0.10",
        linewidth=1.4, edgecolor=ec, facecolor=fc,
    )
    ax.add_patch(patch)
    if body:
        ax.text(x, y + h / 2 - 0.22, filename,
                ha="center", va="center",
                fontsize=header_size, fontweight="bold",
                family="monospace")
        ax.text(x, y - 0.08, body,
                ha="center", va="center",
                fontsize=body_size, color="#222",
                family="monospace")
    else:
        ax.text(x, y, filename, ha="center", va="center",
                fontsize=header_size, fontweight="bold",
                family="monospace")


def draw_data(ax, x, y, label, *, w=2.6, h=0.7,
              palette=C_DATA, fontsize=8.2):
    """Data parallelogram: shows the object passed between modules."""
    fc, ec = palette
    shear = 0.22 * h
    poly = Polygon(
        [
            (x - w / 2 + shear, y - h / 2),
            (x + w / 2 + shear, y - h / 2),
            (x + w / 2 - shear, y + h / 2),
            (x - w / 2 - shear, y + h / 2),
        ],
        closed=True, facecolor=fc, edgecolor=ec, linewidth=1.0,
    )
    ax.add_patch(poly)
    ax.text(x, y, label, ha="center", va="center",
            fontsize=fontsize, family="monospace", color="#222")


def ortho_segment(ax, points, color="#444", linewidth=1.3, arrow=True):
    """Draw a polyline with right-angle segments. Arrowhead on the
    final segment if `arrow` is True. `points` is a list of (x, y).
    """
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        is_last = (i == len(points) - 2)
        if is_last and arrow:
            ax.add_patch(FancyArrowPatch(
                (x0, y0), (x1, y1),
                arrowstyle="->", mutation_scale=12,
                linewidth=linewidth, color=color,
                shrinkA=0, shrinkB=2,
            ))
        else:
            ax.plot([x0, x1], [y0, y1], color=color,
                    linewidth=linewidth, solid_capstyle="round",
                    zorder=1)


def lane_label(ax, x, y, text, color):
    ax.text(x, y, text, ha="left", va="center",
            fontsize=11, fontweight="bold", color=color)


# ---------------------------------------------------------------------------
# Diagram
# ---------------------------------------------------------------------------
def main():
    fig, ax = plt.subplots(figsize=(W, H))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")

    # Title
    ax.text(W / 2, 16.55,
            "K2 Annotator — Module Interaction Diagram",
            ha="center", va="center", fontsize=14, fontweight="bold")
    ax.text(W / 2, 16.15,
            "Boxes are Python files (with their key classes / functions). "
            "Parallelograms are data objects passed between modules.",
            ha="center", va="center", fontsize=9, color="#555")

    # ---- Y-coordinates per row (top → bottom) -----------------------
    Y_GUI = 14.8
    Y_DRV = 12.4
    Y_EXT = 12.4         # external tools share Y with driver lane
    Y_CLI = 9.8
    Y_ENGINE = 7.4
    Y_PARSERS = 7.4
    Y_HELPERS = 5.0
    Y_RESULTS = 3.2
    Y_SURR = 3.2
    Y_REPORT = 1.3

    # ---- X-coordinates: column lanes -------------------------------
    # Vertical "channels" between columns are at x = 5.7, 11.4, 17.1.
    # We route vertical arrows along these channels so they don't run
    # through boxes.
    CH_LEFT = 4.6
    CH_MID = 11.4
    CH_RIGHT = 17.4

    # =================================================================
    # GUI row
    # =================================================================
    lane_label(ax, 0.2, Y_GUI + 0.85, "GUI layer", C_GUI[1])
    draw_module(ax, 2.6, Y_GUI, "k2_gui.py",
                "K2Application(tk.Tk)\nbuilds + shows screens",
                w=3.4, h=1.30, palette=C_GUI, body_size=8)
    draw_module(ax, 8.0, Y_GUI, "k2_screens.py",
                "WelcomeScreen, EntrySelectScreen,\n"
                "ProjectSetupScreen, AnalysisParams,\n"
                "ExecutionScreen, ResultsScreen",
                w=4.4, h=1.30, palette=C_GUI, body_size=8)
    draw_module(ax, 13.4, Y_GUI, "k2_config.py",
                "K2Config (~/.k2/k2_defaults.json,\n  .K2config presets)\n"
                "K2Project (.K2 sessions)",
                w=4.4, h=1.30, palette=C_GUI, body_size=8)

    # GUI internal arrows (horizontal, no overlap)
    ortho_segment(ax, [(2.6 + 1.7, Y_GUI), (8.0 - 2.2, Y_GUI)],
                  color=C_GUI[1])
    draw_data(ax, (2.6 + 1.7 + 8.0 - 2.2) / 2, Y_GUI + 0.55,
              "screen registry", w=2.0, h=0.55, fontsize=7.5)
    ortho_segment(ax, [(8.0 + 2.2, Y_GUI), (13.4 - 2.2, Y_GUI)],
                  color=C_GUI[1])
    draw_data(ax, (8.0 + 2.2 + 13.4 - 2.2) / 2, Y_GUI + 0.55,
              "config + project state", w=2.5, h=0.55, fontsize=7.5)

    # =================================================================
    # Driver / external tools row
    # =================================================================
    lane_label(ax, 0.2, Y_DRV + 0.85, "Driver / external tools",
               C_DRIVER[1])
    draw_module(ax, 2.6, Y_DRV, "gcms_pipeline.py",
                "run_msconvert()\nrun_mzmine()\nrun_library_matching()",
                w=3.4, h=1.30, palette=C_DRIVER, body_size=8)
    draw_module(ax, 7.6, Y_DRV, "MSconvert", "vendor → mzML",
                w=2.4, h=0.85, palette=C_EXTERNAL)
    draw_module(ax, 11.6, Y_DRV, "MZmine", "mzML → quant CSV + MSP",
                w=3.0, h=0.85, palette=C_EXTERNAL)
    draw_module(ax, 16.0, Y_DRV, "MS-DIAL",
                "(alternative; user-run)\nArea.txt + MSP",
                w=2.8, h=1.00, palette=C_EXTERNAL, body_size=8)

    # GUI -> driver: route vertical from k2_screens (8, Y_GUI - 0.65)
    # down to (2.6, Y_DRV + 0.65). Use channel CH_LEFT to avoid the
    # k2_screens box.
    ortho_segment(ax, [
        (8.0, Y_GUI - 0.65),
        (8.0, 13.6),
        (2.6, 13.6),
        (2.6, Y_DRV + 0.65),
    ], color=C_DRIVER[1])
    draw_data(ax, 5.0, 13.6, "CLI command (subprocess)",
              w=3.4, h=0.55, fontsize=7.8)

    # gcms_pipeline -> MSconvert (with raw files data)
    mid_x = (2.6 + 1.7 + 7.6 - 1.2) / 2
    ortho_segment(ax, [(2.6 + 1.7, Y_DRV), (7.6 - 1.2, Y_DRV)],
                  color=C_DRIVER[1])
    draw_data(ax, mid_x, Y_DRV + 0.62,
              "raw files\n(.d / .raw / .wiff)",
              w=2.4, h=0.70, fontsize=7.5)

    # MSconvert -> MZmine
    ortho_segment(ax, [(7.6 + 1.2, Y_DRV), (11.6 - 1.5, Y_DRV)],
                  color=C_DRIVER[1])
    draw_data(ax, (7.6 + 1.2 + 11.6 - 1.5) / 2, Y_DRV + 0.62,
              "mzML files",
              w=1.8, h=0.55, fontsize=7.8)

    # =================================================================
    # CLI bridge
    # =================================================================
    draw_module(ax, 11.6, Y_CLI, "cli.py",
                "main():\n  loads IS / surrogate JSON,\n"
                "  builds MatchingEngine,\n  drives ReportGenerator",
                w=3.8, h=1.40, palette=C_DRIVER, body_size=8)

    # gcms_pipeline -> cli (via subprocess) — runs down channel CH_LEFT
    ortho_segment(ax, [
        (2.6 - 0.20, Y_DRV - 0.65),
        (2.6 - 0.20, 11.0),
        (11.6 - 1.9, 11.0),
        (11.6 - 1.9, Y_CLI + 0.70),
    ], color=C_DRIVER[1])
    draw_data(ax, 7.0, 11.0, "subprocess args:\n--quant --msp --library …",
              w=4.0, h=0.70, fontsize=7.5)

    # MZmine -> cli (drop down)
    ortho_segment(ax, [
        (11.6, Y_DRV - 0.43),
        (11.6, Y_CLI + 0.70),
    ], color="#888")
    draw_data(ax, 11.6, (Y_DRV - 0.43 + Y_CLI + 0.70) / 2,
              "quant CSV + MSP",
              w=2.4, h=0.55, fontsize=7.8)

    # MS-DIAL -> cli (alternative — diagonal-ish via mid right channel)
    ortho_segment(ax, [
        (16.0, Y_DRV - 0.50),
        (16.0, Y_CLI),
        (11.6 + 1.9, Y_CLI),
    ], color="#888")
    draw_data(ax, 16.0, (Y_DRV - 0.50 + Y_CLI) / 2 + 0.10,
              "Area.txt + MSP\n(alt path)",
              w=2.4, h=0.60, fontsize=7.5)

    # =================================================================
    # Analysis core
    # =================================================================
    lane_label(ax, 0.2, Y_ENGINE + 1.05, "Analysis core (scripts/src/)",
               C_CORE[1])

    # Engine row layout (y = Y_ENGINE = 7.4):
    #   universal_parser(3.5)  library_parser(7.0)  matching_engine(12)
    #   spectral_math(17.0)  rhrmf(20.5)
    # Helper row (y = Y_HELPERS = 5.0):
    #   ri_calibration(3.5)  is_normalizer(7.0)
    # Each box gets a 3.0-unit-wide footprint with at least 0.5 unit
    # of gap between columns, so arrow channels never run through a
    # box.

    # Centerpiece engine
    draw_module(ax, 12.0, Y_ENGINE, "matching_engine.py",
                "MatchingEngine\n  load_data() / run_matching()\n"
                "MatchCandidate",
                w=4.0, h=1.45, palette=C_CORE_DEEP, body_size=8)
    # cli -> engine
    ortho_segment(ax, [
        (11.6, Y_CLI - 0.70),
        (11.6, Y_ENGINE + 0.73),
    ], color=C_CORE[1])
    draw_data(ax, 11.6, (Y_CLI - 0.70 + Y_ENGINE + 0.73) / 2,
              "config dicts\n(IS, surrogate, samples)",
              w=3.0, h=0.70, fontsize=7.5)

    # Parsers (left)
    draw_module(ax, 3.5, Y_PARSERS, "universal_parser.py",
                "UniversalParser\nFeature\n(MZmine / MS-DIAL)",
                w=3.0, h=1.30, palette=C_CORE, body_size=8)
    draw_module(ax, 7.0, Y_PARSERS, "library_parser.py",
                "LibraryParser\nLibraryCompound",
                w=3.0, h=1.05, palette=C_CORE, body_size=8)

    # Helpers (right of the engine)
    draw_module(ax, 17.0, Y_PARSERS, "spectral_math.py",
                "calculate_scores(a, b)\n→ (fwd_dot, rev_dot)",
                w=3.0, h=1.05, palette=C_HELPER, body_size=8)
    draw_module(ax, 20.5, Y_PARSERS, "rhrmf.py",
                "is_library_high_res()\ncalculate_rhrmf()\n"
                "FormulaExplainer",
                w=3.0, h=1.30, palette=C_HELPER, body_size=8)

    # Pre-processing helpers (below)
    draw_module(ax, 3.5, Y_HELPERS, "ri_calibration.py",
                "RICalibrator\n(RT → RI for MZmine)",
                w=3.0, h=1.05, palette=C_HELPER, body_size=8)
    draw_module(ax, 7.0, Y_HELPERS, "is_normalizer.py",
                "InternalStandard\nNormalizer\n(pre-BFF)",
                w=3.0, h=1.30, palette=C_HELPER, body_size=8)

    # ---- Engine ↔ universal_parser ----
    # Forward (parser → engine, with Feature[] data) at y = Y_ENGINE +
    # 0.20; return arrow not needed (parser is an owned attribute).
    ortho_segment(ax, [(3.5 + 1.5, Y_ENGINE + 0.20),
                       (12.0 - 2.0, Y_ENGINE + 0.20)],
                  color=C_CORE[1])
    draw_data(ax, (3.5 + 1.5 + 12.0 - 2.0) / 2, Y_ENGINE + 0.65,
              "Feature[]  (parsed peaks)",
              w=3.6, h=0.55, fontsize=7.5)

    # ---- Engine ↔ library_parser ----
    # Use a parallel channel at y = Y_ENGINE - 0.20.
    ortho_segment(ax, [(7.0 + 1.5, Y_ENGINE - 0.20),
                       (12.0 - 2.0, Y_ENGINE - 0.20)],
                  color=C_CORE[1])
    draw_data(ax, (7.0 + 1.5 + 12.0 - 2.0) / 2, Y_ENGINE - 0.65,
              "LibraryCompound[]",
              w=3.0, h=0.55, fontsize=7.5)

    # ---- Engine ↔ spectral_math ----
    # Outbound at y = Y_ENGINE + 0.20, inbound at Y_ENGINE - 0.20.
    ortho_segment(ax, [(12.0 + 2.0, Y_ENGINE + 0.20),
                       (17.0 - 1.5, Y_ENGINE + 0.20)],
                  color=C_HELPER[1])
    draw_data(ax, (12.0 + 2.0 + 17.0 - 1.5) / 2, Y_ENGINE + 0.65,
              "(feat.spectrum, lib.spectrum)",
              w=3.6, h=0.55, fontsize=7.5)
    ortho_segment(ax, [(17.0 - 1.5, Y_ENGINE - 0.20),
                       (12.0 + 2.0, Y_ENGINE - 0.20)],
                  color=C_HELPER[1])
    draw_data(ax, (12.0 + 2.0 + 17.0 - 1.5) / 2, Y_ENGINE - 0.65,
              "(fwd_dot, rev_dot)",
              w=2.8, h=0.55, fontsize=7.5)

    # ---- Engine ↔ rhrmf (only when low-res library) ----
    ortho_segment(ax, [(17.0 + 1.5, Y_ENGINE + 0.20),
                       (20.5 - 1.5, Y_ENGINE + 0.20)],
                  color=C_HELPER[1])
    draw_data(ax, (17.0 + 1.5 + 20.5 - 1.5) / 2, Y_ENGINE + 0.65,
              "(if low-res library entry)",
              w=2.8, h=0.55, fontsize=7.5)
    ortho_segment(ax, [(20.5 - 1.5, Y_ENGINE - 0.20),
                       (17.0 + 1.5, Y_ENGINE - 0.20)],
                  color=C_HELPER[1])
    draw_data(ax, (17.0 + 1.5 + 20.5 - 1.5) / 2, Y_ENGINE - 0.65,
              "rhrmf_score",
              w=2.0, h=0.55, fontsize=7.5)

    # ---- universal_parser ↔ ri_calibration ----
    # parser.set_ri_calibrator(file) — vertical channel at x=3.5
    ortho_segment(ax, [(3.5, Y_PARSERS - 0.65),
                       (3.5, Y_HELPERS + 0.52)],
                  color=C_HELPER[1])
    draw_data(ax, 3.5, (Y_PARSERS - 0.65 + Y_HELPERS + 0.52) / 2,
              "set_ri_calibrator(file)",
              w=3.0, h=0.55, fontsize=7.5)

    # ---- Engine ↔ is_normalizer ----
    # Vertical channel at x=7.0 → matching_engine bottom edge.
    ortho_segment(ax, [
        (12.0 - 0.6, Y_ENGINE - 0.73),
        (12.0 - 0.6, Y_HELPERS - 0.10),
        (7.0 + 1.5, Y_HELPERS - 0.10),
    ], color=C_HELPER[1])
    draw_data(ax, (7.0 + 1.5 + 12.0 - 0.6) / 2, Y_HELPERS - 0.55,
              "Feature.abundances\n(scaled in place)",
              w=3.4, h=0.65, fontsize=7.5)

    # =================================================================
    # Engine output: results (data parallelogram)
    # =================================================================
    ortho_segment(ax, [(12.0, Y_ENGINE - 0.73),
                       (12.0, Y_RESULTS + 0.40)],
                  color=C_CORE[1])
    draw_data(ax, 12.0, Y_RESULTS,
              "results = { feat_id : [ MatchCandidate, … ] }",
              w=6.0, h=0.75, fontsize=8.5)

    # =================================================================
    # Surrogate workflow (parallel branch)
    # =================================================================
    lane_label(ax, 0.2, Y_SURR + 0.95, "Surrogate workflow",
               C_SURROGATE[1])
    draw_module(ax, 19.6, Y_SURR, "surrogate_analyzer.py",
                "SurrogateAnalyzer\n  match_surrogates()\n"
                "  calculate_recoveries()\n"
                "(reuses LibraryParser,\ncalculate_scores, rhrmf)",
                w=4.4, h=1.65, palette=C_SURROGATE, body_size=7.5)

    # Engine -> surrogate analyzer (horizontal at Y_RESULTS, then up
    # to surrogate)
    ortho_segment(ax, [
        (12.0 + 3.2, Y_RESULTS),
        (19.6 - 2.2, Y_RESULTS),
    ], color=C_SURROGATE[1])
    draw_data(ax, (12.0 + 3.2 + 19.6 - 2.2) / 2, Y_RESULTS + 0.55,
              "features (post-IS, pre-BFF)\n+ surrogate config",
              w=4.6, h=0.70, fontsize=7.5)

    # =================================================================
    # Report layer
    # =================================================================
    lane_label(ax, 0.2, Y_REPORT + 0.85, "Report layer", C_REPORT[1])
    draw_module(ax, 2.6, Y_REPORT, "reporter.py",
                "ReportGenerator\n  generate_csv()\n  generate_pdf()\n"
                "  generate_summary_csvs()",
                w=3.4, h=1.50, palette=C_REPORT, body_size=8)
    draw_module(ax, 6.6, Y_REPORT, "summary_tables.py",
                "build_feature_summary()\nbuild_match_summary()\n"
                "render_summary_pdf_pages()",
                w=3.4, h=1.30, palette=C_REPORT, body_size=8)
    draw_module(ax, 10.6, Y_REPORT, "structure_helper.py",
                "StructureHelper\n  get_structure_image()\n"
                "  get_hazard_matrix()",
                w=3.4, h=1.30, palette=C_REPORT, body_size=8)
    draw_module(ax, 14.4, Y_REPORT,
                "epa_client.py /\nctx_client.py",
                "EPA CompTox API\nPubChem fallback",
                w=3.0, h=1.30, palette=C_REPORT, body_size=8)
    draw_module(ax, 19.6, Y_REPORT, "surrogate_reporter.py",
                "SurrogateReporter\n  generate_csv()\n"
                "  generate_pdf_pages(canvas)",
                w=3.4, h=1.30, palette=C_SURROGATE, body_size=8)

    # cli -> reporter (subprocess data flow)
    ortho_segment(ax, [
        (11.6 - 1.9, Y_CLI),
        (1.0, Y_CLI),
        (1.0, Y_REPORT),
        (2.6 - 1.7, Y_REPORT),
    ], color=C_REPORT[1])
    draw_data(ax, 1.0, (Y_CLI + Y_REPORT) / 2 - 0.5,
              "results, features",
              w=2.4, h=0.55, fontsize=7.8)

    # reporter -> summary_tables
    ortho_segment(ax, [(2.6 + 1.7, Y_REPORT),
                       (6.6 - 1.7, Y_REPORT)],
                  color=C_REPORT[1])
    draw_data(ax, (2.6 + 1.7 + 6.6 - 1.7) / 2, Y_REPORT + 0.62,
              "features, results",
              w=2.4, h=0.55, fontsize=7.5)

    # reporter -> structure_helper (per match)
    ortho_segment(ax, [(2.6 + 1.7, Y_REPORT - 0.55),
                       (10.6 - 1.7, Y_REPORT - 0.55)],
                  color=C_REPORT[1])
    draw_data(ax, (2.6 + 1.7 + 10.6 - 1.7) / 2, Y_REPORT - 1.05,
              "InChIKey, CAS\n(per match)",
              w=2.6, h=0.65, fontsize=7.5)

    # structure_helper -> epa_client
    ortho_segment(ax, [(10.6 + 1.7, Y_REPORT),
                       (14.4 - 1.5, Y_REPORT)],
                  color=C_REPORT[1])
    draw_data(ax, (10.6 + 1.7 + 14.4 - 1.5) / 2, Y_REPORT + 0.62,
              "REST API call",
              w=2.0, h=0.55, fontsize=7.5)

    # surrogate_analyzer -> surrogate_reporter
    ortho_segment(ax, [(19.6, Y_SURR - 0.85),
                       (19.6, Y_REPORT + 0.65)],
                  color=C_SURROGATE[1])
    draw_data(ax, 19.6, (Y_SURR - 0.85 + Y_REPORT + 0.65) / 2,
              "matches dict,\nrecoveries dict",
              w=2.6, h=0.70, fontsize=7.5)

    # surrogate_reporter -> reporter (PDF pages embedded)
    # Route along the bottom: down 0.55 to a clear lane, left to
    # reporter, then up to reporter.
    ortho_segment(ax, [
        (19.6 - 1.7, Y_REPORT),
        (16.4, Y_REPORT),
        (16.4, Y_REPORT - 1.10),
        (2.6, Y_REPORT - 1.10),
        (2.6, Y_REPORT - 0.75),
    ], color=C_SURROGATE[1])
    draw_data(ax, 9.5, Y_REPORT - 1.10,
              "generate_pdf_pages(canvas) → surrogate pages embedded in main PDF",
              w=10.0, h=0.55, fontsize=7.8)

    # Final outputs strip
    ax.text(W / 2, 0.20,
            "Outputs on disk:   *_matches_*.csv   ·   "
            "*_feature_summary.csv   ·   *_match_summary.csv   ·   "
            "SurrogateRecoveries_*.csv   ·   *_report_*.pdf",
            ha="center", va="center", fontsize=9.5, style="italic",
            color=C_REPORT[1])

    # Subtle horizontal lane separators
    for y_sep in (13.85, 11.10, 8.95, 6.05, 4.30, 2.30):
        ax.plot([0.05, W - 0.05], [y_sep, y_sep],
                color="#ececec", linewidth=0.7, zorder=0)

    here = Path(__file__).resolve().parent
    out_png = here / "modules.png"
    out_svg = here / "modules.svg"
    fig.tight_layout()
    fig.savefig(out_png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(out_svg, bbox_inches="tight", facecolor="white")
    print(f"Wrote {out_png}")
    print(f"Wrote {out_svg}")


if __name__ == "__main__":
    main()
