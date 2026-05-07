"""
Render the module-level dependency diagram for the K2 pipeline.

Run:  python docs/make_module_diagram.py

Outputs docs/modules.png and docs/modules.svg.

Layout: four vertical columns (GUI / driver / analysis core / report
layer), with the surrogate workflow as a labelled side-branch in the
analysis-core column. Arrows are labelled with the data passed.
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


FIG_W, FIG_H = 19.0, 13.0
W, H = 19.0, 13.0

C_GUI = ("#dde6f5", "#3f5a86")
C_DRIVER = ("#fce8c2", "#a87a25")
C_EXTERNAL = ("#eaeaea", "#666666")
C_CORE = ("#dde8d6", "#4f7a3a")
C_CORE_DEEP = ("#bbd2ac", "#34581f")
C_HELPER = ("#eaf1e3", "#5e8a45")
C_SURROGATE = ("#f0d8e2", "#8e3a64")
C_REPORT = ("#e7e1f0", "#583c7a")
C_DATA = ("#fff5d6", "#a08623")


def draw_module(ax, x, y, filename, body="", *, w=3.0, h=1.10,
                palette=C_CORE, header_size=10, body_size=8.5):
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
        ax.text(x, y - 0.05, body,
                ha="center", va="center",
                fontsize=body_size, color="#222",
                family="monospace")
    else:
        ax.text(x, y, filename, ha="center", va="center",
                fontsize=header_size, fontweight="bold",
                family="monospace")


def arrow(ax, x0, y0, x1, y1, *, label=None, label_offset=(0, 0),
          color="#444", linewidth=1.2, connectionstyle="arc3,rad=0",
          label_fontsize=7.5, label_bg="white"):
    a = FancyArrowPatch(
        (x0, y0), (x1, y1),
        arrowstyle="->", mutation_scale=12,
        linewidth=linewidth, color=color,
        connectionstyle=connectionstyle, shrinkA=2, shrinkB=2,
    )
    ax.add_patch(a)
    if label:
        mx = (x0 + x1) / 2 + label_offset[0]
        my = (y0 + y1) / 2 + label_offset[1]
        ax.text(mx, my, label, ha="center", va="center",
                fontsize=label_fontsize, color=color, style="italic",
                bbox=dict(boxstyle="round,pad=0.18",
                          fc=label_bg, ec="none", alpha=0.95))


def column_title(ax, x, y, text, color):
    ax.text(x, y, text, ha="center", va="center",
            fontsize=11, fontweight="bold", color=color)


def main():
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")

    # Title
    ax.text(W / 2, 12.6,
            "K2 Pipeline — Module Interaction Diagram",
            ha="center", va="center", fontsize=14, fontweight="bold")
    ax.text(W / 2, 12.2,
            "Boxes are Python files (with their key classes / functions). "
            "Arrows are labelled with the data passed between modules.",
            ha="center", va="center", fontsize=9, color="#555")

    # Column x-centres
    X_GUI = 2.7
    X_DRV = 6.7
    X_ENG = 11.0
    X_REP = 16.4
    # Column titles
    column_title(ax, X_GUI, 11.6, "GUI layer", C_GUI[1])
    column_title(ax, X_DRV, 11.6, "Driver / external tools", C_DRIVER[1])
    column_title(ax, X_ENG, 11.6, "Analysis core (scripts/src/)", C_CORE[1])
    column_title(ax, X_REP, 11.6, "Report layer", C_REPORT[1])

    # Light vertical separators between columns
    for x_sep in (4.7, 8.85, 14.1):
        ax.plot([x_sep, x_sep], [0.5, 11.3],
                color="#e3e3e3", linewidth=0.8, zorder=0)

    # =======================================================================
    # GUI column (left)
    # =======================================================================
    draw_module(ax, X_GUI, 10.7, "k2_gui.py",
                "K2Application\n(tk.Tk)\nbuilds + shows screens",
                w=3.4, h=1.50, palette=C_GUI, body_size=8)
    draw_module(ax, X_GUI, 8.65, "k2_screens.py",
                "WelcomeScreen\nEntrySelectScreen\nProjectSetupScreen\n"
                "AnalysisParamsScreen\nExecutionScreen\nResultsScreen",
                w=3.4, h=2.20, palette=C_GUI, body_size=7.5)
    draw_module(ax, X_GUI, 6.0, "k2_config.py",
                "K2Config\n  ~/.k2/k2_defaults.json\n  .K2config presets\nK2Project\n  .K2 sessions",
                w=3.4, h=1.85, palette=C_GUI, body_size=7.5)

    arrow(ax, X_GUI, 10.7 - 0.75, X_GUI, 8.65 + 1.10,
          label="hosts screens", color=C_GUI[1])
    arrow(ax, X_GUI, 8.65 - 1.10, X_GUI, 6.0 + 0.92,
          label="reads / writes\nuser settings", color=C_GUI[1])

    # =======================================================================
    # Driver column
    # =======================================================================
    draw_module(ax, X_DRV, 10.5, "gcms_pipeline.py",
                "run_msconvert()\nrun_mzmine()\nrun_library_matching()",
                w=3.4, h=1.40, palette=C_DRIVER, body_size=8)
    draw_module(ax, X_DRV, 8.6, "MSconvert", "vendor → mzML",
                w=2.4, h=0.85, palette=C_EXTERNAL)
    draw_module(ax, X_DRV, 7.4, "MZmine", "mzML → quant CSV + MSP",
                w=3.0, h=0.85, palette=C_EXTERNAL)
    draw_module(ax, X_DRV, 6.0, "MS-DIAL",
                "(alternative entry — user-run)\nArea.txt + MSP",
                w=3.4, h=1.10, palette=C_EXTERNAL, body_size=8)
    draw_module(ax, X_DRV, 4.0, "cli.py",
                "main():\n"
                "  loads IS / surrogate JSON,\n"
                "  builds MatchingEngine,\n"
                "  drives ReportGenerator",
                w=3.4, h=1.50, palette=C_DRIVER, body_size=8)

    # GUI -> driver
    arrow(ax, X_GUI + 1.7, 8.65, X_DRV - 1.7, 10.5,
          label="ExecutionScreen builds\nCLI command (subprocess)",
          color=C_DRIVER[1], label_fontsize=7,
          connectionstyle="arc3,rad=-0.20")
    # gcms_pipeline -> tools
    arrow(ax, X_DRV, 10.5 - 0.70, X_DRV, 8.6 + 0.43,
          label="raw files", color=C_DRIVER[1])
    arrow(ax, X_DRV, 8.6 - 0.43, X_DRV, 7.4 + 0.43,
          label="mzML", color=C_DRIVER[1])
    # gcms_pipeline -> cli (subprocess)
    arrow(ax, X_DRV - 1.6, 10.5 - 0.70, X_DRV - 1.6, 4.0 + 0.75,
          label="subprocess\n--quant --msp --library …",
          color=C_DRIVER[1], label_fontsize=7,
          connectionstyle="arc3,rad=-0.30")
    # MZmine -> cli
    arrow(ax, X_DRV, 7.4 - 0.43, X_DRV - 0.6, 4.0 + 0.75,
          label="quant + MSP",
          color="#888", label_fontsize=7)
    # MS-DIAL -> cli (alternative)
    arrow(ax, X_DRV, 6.0 - 0.55, X_DRV + 0.6, 4.0 + 0.75,
          label="quant + MSP\n(alt path)",
          color="#888", label_fontsize=7)

    # =======================================================================
    # Analysis core column — centerpiece engine + helpers
    # =======================================================================
    # Centerpiece: matching_engine.py
    draw_module(ax, X_ENG, 10.5, "matching_engine.py",
                "MatchingEngine\n"
                "  load_data() / run_matching()\n"
                "MatchCandidate",
                w=4.0, h=1.50, palette=C_CORE_DEEP, body_size=8)

    # cli -> engine
    arrow(ax, X_DRV + 1.7, 4.0, X_ENG - 2.0, 10.5,
          label="instantiates\nMatchingEngine,\nReportGenerator,\n"
                "(optional)\nSurrogateAnalyzer",
          color=C_CORE[1], label_fontsize=7,
          connectionstyle="arc3,rad=-0.40",
          label_offset=(0.5, 0.0))

    # Helper modules around the engine
    draw_module(ax, X_ENG, 8.6, "universal_parser.py",
                "UniversalParser\nFeature\n(handles MZmine + MS-DIAL)",
                w=4.0, h=1.30, palette=C_CORE, body_size=8)
    draw_module(ax, X_ENG, 7.0, "library_parser.py",
                "LibraryParser\nLibraryCompound",
                w=4.0, h=1.05, palette=C_CORE, body_size=8)
    draw_module(ax, X_ENG - 1.10, 5.4, "spectral_math.py",
                "calculate_scores(a, b)\n→ (fwd_dot, rev_dot)",
                w=3.0, h=1.05, palette=C_HELPER, body_size=8)
    draw_module(ax, X_ENG + 1.95, 5.4, "rhrmf.py",
                "is_library_high_res()\ncalculate_rhrmf()\nFormulaExplainer",
                w=3.0, h=1.30, palette=C_HELPER, body_size=8)
    draw_module(ax, X_ENG - 1.10, 3.9, "is_normalizer.py",
                "InternalStandard\nNormalizer\n(pre-BFF)",
                w=3.0, h=1.30, palette=C_HELPER, body_size=8)
    draw_module(ax, X_ENG + 1.95, 3.9, "ri_calibration.py",
                "RICalibrator\n(RT → RI for MZmine)",
                w=3.0, h=1.05, palette=C_HELPER, body_size=8)

    # Engine -> parsers
    arrow(ax, X_ENG, 10.5 - 0.75, X_ENG, 8.6 + 0.65,
          label="parser.parse_files()\n→ Feature[]",
          color=C_CORE[1], label_fontsize=7)
    arrow(ax, X_ENG, 8.6 - 0.65, X_ENG, 7.0 + 0.52,
          label="library.load_library()\n→ LibraryCompound[]",
          color=C_CORE[1], label_fontsize=7)

    # Engine -> spectral_math (left), rhrmf (right)
    arrow(ax, X_ENG - 1.5, 10.5 - 0.75, X_ENG - 1.10, 5.4 + 0.52,
          label="(feat.spectrum,\n lib.spectrum)\nper RI candidate",
          color=C_HELPER[1], label_fontsize=7,
          connectionstyle="arc3,rad=0.10",
          label_offset=(-0.6, 0.4))
    arrow(ax, X_ENG + 1.5, 10.5 - 0.75, X_ENG + 1.95, 5.4 + 0.65,
          label="if low-res library\n→ rhrmf > 75 gate",
          color=C_HELPER[1], label_fontsize=7,
          connectionstyle="arc3,rad=-0.10",
          label_offset=(0.6, 0.4))

    # Engine -> is_normalizer / ri_calibration
    arrow(ax, X_ENG - 1.5, 10.5 - 0.75, X_ENG - 1.10, 3.9 + 0.65,
          label="scales\nFeature.abundances",
          color=C_HELPER[1], label_fontsize=7,
          connectionstyle="arc3,rad=0.30",
          label_offset=(-1.4, -1.0))
    arrow(ax, X_ENG + 1.5, 10.5 - 0.75, X_ENG + 1.95, 3.9 + 0.52,
          label="parser.set_ri_calibrator()",
          color=C_HELPER[1], label_fontsize=7,
          connectionstyle="arc3,rad=-0.30",
          label_offset=(1.4, -1.0))

    # Engine output (data note)
    ax.text(X_ENG, 2.3,
            "results = { feat_id : [ MatchCandidate, … ] }",
            ha="center", va="center", fontsize=8.5, family="monospace",
            color="#333",
            bbox=dict(boxstyle="round,pad=0.20",
                      fc=C_DATA[0], ec=C_DATA[1], lw=0.8))

    # Surrogate workflow side-branch (still in analysis-core column)
    draw_module(ax, X_ENG, 1.1, "surrogate_analyzer.py",
                "SurrogateAnalyzer\n"
                "  match_surrogates()\n"
                "  calculate_recoveries()\n"
                "SurrogateMatch\n(reuses LibraryParser,\n"
                "calculate_scores, rhrmf)",
                w=4.4, h=1.85, palette=C_SURROGATE, body_size=7.5)
    arrow(ax, X_ENG, 2.3 - 0.20, X_ENG, 1.1 + 0.92,
          label="features (post-IS, pre-BFF)\n+ surrogate config",
          color=C_SURROGATE[1], label_fontsize=7)

    # =======================================================================
    # Report layer column (right)
    # =======================================================================
    draw_module(ax, X_REP, 10.5, "reporter.py",
                "ReportGenerator\n"
                "  generate_csv()\n"
                "  generate_pdf()\n"
                "  generate_summary_csvs()",
                w=3.4, h=1.55, palette=C_REPORT, body_size=8)
    draw_module(ax, X_REP, 8.5, "summary_tables.py",
                "build_feature_summary()\nbuild_match_summary()\n"
                "render_summary_pdf_pages()",
                w=3.4, h=1.20, palette=C_REPORT, body_size=8)
    draw_module(ax, X_REP, 6.7, "structure_helper.py",
                "StructureHelper\n  get_structure_image()\n  get_hazard_matrix()",
                w=3.4, h=1.20, palette=C_REPORT, body_size=8)
    draw_module(ax, X_REP, 4.9, "epa_client.py /\nctx_client.py",
                "EPA CompTox API\nPubChem fallback",
                w=3.0, h=1.20, palette=C_REPORT, body_size=8)
    draw_module(ax, X_REP, 1.1, "surrogate_reporter.py",
                "SurrogateReporter\n  generate_csv()\n  generate_pdf_pages()",
                w=3.4, h=1.40, palette=C_SURROGATE, body_size=8)

    # cli -> reporter
    arrow(ax, X_DRV + 1.7, 4.0 + 0.5, X_REP - 1.7, 10.5,
          label="results, features\n→ ReportGenerator",
          color=C_REPORT[1], label_fontsize=7,
          connectionstyle="arc3,rad=-0.30",
          label_offset=(-0.8, 0.5))
    # reporter -> summary_tables
    arrow(ax, X_REP, 10.5 - 0.78, X_REP, 8.5 + 0.60,
          label="features, results",
          color=C_REPORT[1], label_fontsize=7)
    # summary_tables -> structure_helper (no — actually reporter uses both)
    # reporter -> structure_helper
    arrow(ax, X_REP - 1.5, 10.5 - 0.5, X_REP - 1.7, 6.7 + 0.5,
          label="for each match\n(InChIKey, name)",
          color=C_REPORT[1], label_fontsize=7,
          connectionstyle="arc3,rad=0.30",
          label_offset=(-0.8, 0.0))
    # structure_helper -> epa
    arrow(ax, X_REP, 6.7 - 0.60, X_REP, 4.9 + 0.60,
          label="CAS / InChIKey",
          color=C_REPORT[1], label_fontsize=7)

    # surrogate_analyzer -> surrogate_reporter
    arrow(ax, X_ENG + 2.2, 1.1, X_REP - 1.7, 1.1,
          label="recoveries, matches",
          color=C_SURROGATE[1], label_fontsize=7)
    # surrogate_reporter -> reporter (PDF pages)
    arrow(ax, X_REP, 1.1 + 0.70, X_REP, 10.5 - 0.78,
          label="generate_pdf_pages(canvas)\n→ surrogate pages embedded\n"
                "in main PDF",
          color=C_SURROGATE[1], label_fontsize=7,
          connectionstyle="arc3,rad=-0.40",
          label_offset=(1.4, 0.0))

    # Outputs strip
    ax.text(W / 2, 0.20,
            "Outputs on disk:   *_matches_*.csv   ·   *_feature_summary.csv   ·   "
            "*_match_summary.csv   ·   SurrogateRecoveries_*.csv   ·   *_report_*.pdf",
            ha="center", va="center", fontsize=9, style="italic",
            color=C_REPORT[1])

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
