#!/usr/bin/env python3
"""
Generate presentation diagrams for K2 GC-MS Pipeline
Creates 12 figures for assertion-evidence style presentation slides
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle, Wedge
import numpy as np
from pathlib import Path

# Set up output directory
OUTPUT_DIR = Path("presentation_figures")
OUTPUT_DIR.mkdir(exist_ok=True)

# Global style settings
plt.rcParams['font.family'] = 'Arial'
plt.rcParams['font.size'] = 11
plt.rcParams['axes.linewidth'] = 1.5

# Color palette
COLOR_PROCESS = '#4472C4'    # Blue for processes
COLOR_DATA = '#70AD47'        # Green for data
COLOR_DECISION = '#FFC000'    # Orange for decisions
COLOR_FILTER = '#ED7D31'      # Orange-red for filters
COLOR_SUCCESS = '#70AD47'     # Green for success
COLOR_FAIL = '#C5504B'        # Red for fail/reject


def create_rounded_box(ax, xy, width, height, text, color, text_color='white', fontsize=10):
    """Helper to create a rounded box with text"""
    box = FancyBboxPatch(xy, width, height, boxstyle="round,pad=0.05",
                         facecolor=color, edgecolor='black', linewidth=2)
    ax.add_patch(box)
    ax.text(xy[0] + width/2, xy[1] + height/2, text,
           ha='center', va='center', color=text_color, fontsize=fontsize,
           weight='bold', wrap=True)
    return box


def create_arrow(ax, start, end, color='black', style='->', linewidth=2):
    """Helper to create an arrow between points"""
    arrow = FancyArrowPatch(start, end, arrowstyle=style,
                           color=color, linewidth=linewidth,
                           mutation_scale=20, zorder=1)
    ax.add_patch(arrow)
    return arrow


# ==============================================================================
# SLIDE 1: System Overview Pipeline
# ==============================================================================
def generate_slide1():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'K2 GC-MS Pipeline: Complete Workflow',
           ha='center', fontsize=16, weight='bold')

    # Entry points (left side)
    create_rounded_box(ax, (0.5, 6), 1.5, 0.6, '.D Files', COLOR_DATA, fontsize=9)
    create_rounded_box(ax, (0.5, 5), 1.5, 0.6, '.mzML', COLOR_DATA, fontsize=9)
    create_rounded_box(ax, (0.5, 4), 1.5, 0.6, 'MZmine\nOutput', COLOR_DATA, fontsize=9)

    # Main pipeline stages
    stages = [
        (2.5, 5.5, 'MSConvert', 'Raw to mzML'),
        (4.5, 5.5, 'MZmine', 'Feature\nDetection'),
        (6.5, 5.5, 'Universal\nParser', 'Format\nDetection'),
        (8.5, 5.5, 'Matching\nEngine', 'Library\nSearch'),
        (10.5, 5.5, 'Reporter', 'CSV/PDF\nGeneration')
    ]

    for i, (x, y, title, desc) in enumerate(stages):
        create_rounded_box(ax, (x, y), 1.5, 0.8, title, COLOR_PROCESS, fontsize=9)
        ax.text(x + 0.75, y - 0.3, desc, ha='center', fontsize=7, style='italic')

        if i > 0:
            create_arrow(ax, (x - 0.1, y + 0.4), (x, y + 0.4))

    # Arrows from entry points
    create_arrow(ax, (2, 6.3), (2.5, 5.9))
    create_arrow(ax, (2, 5.3), (4.5, 5.9))
    create_arrow(ax, (2, 4.3), (6.5, 5.5))

    # Outputs
    create_rounded_box(ax, (9, 3.5), 1.5, 0.5, 'CSV Report', COLOR_SUCCESS, fontsize=9)
    create_rounded_box(ax, (9, 2.8), 1.5, 0.5, 'PDF Report', COLOR_SUCCESS, fontsize=9)

    create_arrow(ax, (11.25, 5.5), (10.5, 4))
    create_arrow(ax, (10.5, 3.75), (10.5, 3.3))

    # Key features boxes
    features = [
        (0.5, 2, 'Level 2\nIdentification'),
        (2.5, 2, 'BFF\nFiltering'),
        (4.5, 2, 'IS\nNormalization'),
        (6.5, 2, 'RI\nCalibration')
    ]

    for x, y, text in features:
        create_rounded_box(ax, (x, y), 1.5, 0.5, text, '#E7E6E6', 'black', fontsize=8)

    ax.text(6, 0.5, 'Automated pipeline with three flexible entry points',
           ha='center', fontsize=10, style='italic')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'slide1_system_overview.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 1: System Overview")


# ==============================================================================
# SLIDE 2: Modular Entry Points
# ==============================================================================
def generate_slide2():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'Three Entry Points for Flexible Workflow',
           ha='center', fontsize=16, weight='bold')

    # Decision diamond
    diamond_x, diamond_y = 6, 6
    diamond = patches.FancyBboxPatch((diamond_x - 0.6, diamond_y - 0.4), 1.2, 0.8,
                                     boxstyle="round,pad=0.1",
                                     facecolor=COLOR_DECISION,
                                     edgecolor='black', linewidth=2)
    ax.add_patch(diamond)
    ax.text(diamond_x, diamond_y, 'Data\nFormat?', ha='center', va='center',
           fontsize=10, weight='bold')

    # Three paths
    paths = [
        # Path 1: Full pipeline
        {
            'start': (diamond_x - 0.6, diamond_y),
            'label_pos': (3, 6.3),
            'label': 'Raw .D files',
            'boxes': [
                (1.5, 4.5, 'MSConvert', COLOR_PROCESS),
                (1.5, 3.5, 'MZmine', COLOR_PROCESS),
                (1.5, 2.5, 'Library\nMatch', COLOR_PROCESS),
                (1.5, 1.5, 'Results', COLOR_SUCCESS)
            ]
        },
        # Path 2: Skip conversion
        {
            'start': (diamond_x, diamond_y - 0.4),
            'label_pos': (6, 5),
            'label': '.mzML files',
            'boxes': [
                (5.25, 3.5, 'MZmine', COLOR_PROCESS),
                (5.25, 2.5, 'Library\nMatch', COLOR_PROCESS),
                (5.25, 1.5, 'Results', COLOR_SUCCESS)
            ]
        },
        # Path 3: Matching only
        {
            'start': (diamond_x + 0.6, diamond_y),
            'label_pos': (9, 6.3),
            'label': 'MZmine\nOutput',
            'boxes': [
                (9, 2.5, 'Library\nMatch', COLOR_PROCESS),
                (9, 1.5, 'Results', COLOR_SUCCESS)
            ]
        }
    ]

    for path in paths:
        # Label
        ax.text(path['label_pos'][0], path['label_pos'][1], path['label'],
               ha='center', fontsize=10, weight='bold',
               bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.7))

        # Boxes
        prev_y = path['start'][1]
        for x, y, text, color in path['boxes']:
            create_rounded_box(ax, (x, y), 1.2, 0.6, text, color, fontsize=9)
            if y < prev_y:
                create_arrow(ax, (x + 0.6, prev_y - 0.1), (x + 0.6, y + 0.6))
            prev_y = y

        # Arrow from diamond
        first_box = path['boxes'][0]
        create_arrow(ax, path['start'], (first_box[0] + 0.6, first_box[1] + 0.6))

    ax.text(6, 0.5, 'Entry point selection enables workflow optimization',
           ha='center', fontsize=10, style='italic')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'slide2_entry_points.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 2: Entry Points")


# ==============================================================================
# SLIDE 3: Universal Parser Architecture
# ==============================================================================
def generate_slide3():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'Universal Parser: Format-Agnostic Architecture',
           ha='center', fontsize=16, weight='bold')

    # Main class
    create_rounded_box(ax, (4.5, 5.5), 3, 1, 'UniversalParser\ndetect_format()',
                      COLOR_PROCESS, fontsize=12)

    # Format detection
    create_rounded_box(ax, (4.5, 4), 3, 0.5, 'detect_format(quant, msp)',
                      '#B4C7E7', 'black', fontsize=10)
    create_arrow(ax, (6, 5.5), (6, 4.5))

    # Two branches
    # MS-DIAL branch
    create_rounded_box(ax, (1, 2.5), 2.5, 0.8, 'MS-DIAL Parser', '#9DC3E6', 'black', fontsize=10)
    ax.text(2.25, 1.8, 'Parse "Alignment"\nCheck "RETENTIONTIME"',
           ha='center', fontsize=8)

    # MZmine branch
    create_rounded_box(ax, (8.5, 2.5), 2.5, 0.8, 'MZmine Parser', '#9DC3E6', 'black', fontsize=10)
    ax.text(9.75, 1.8, 'Parse "row ID"\nApply RI calibration',
           ha='center', fontsize=8)

    # Arrows to branches
    create_arrow(ax, (5, 4), (2.5, 3.3))
    create_arrow(ax, (7, 4), (9.5, 3.3))

    # Common output
    create_rounded_box(ax, (4.5, 0.5), 3, 0.7, 'Feature Objects\n(unified format)',
                      COLOR_SUCCESS, fontsize=11)

    create_arrow(ax, (2.25, 2.5), (5, 1.2))
    create_arrow(ax, (9.75, 2.5), (7, 1.2))

    # Add code snippet
    code_text = 'if "RETENTIONTIME" in msp:\n    format = "msdial"\nelse:\n    format = "mzmine"'
    ax.text(10.5, 5.5, code_text, fontsize=8, family='monospace',
           verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='#F0F0F0', alpha=0.9))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'slide3_universal_parser.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 3: Universal Parser")


# ==============================================================================
# SLIDE 4: Feature Data Model
# ==============================================================================
def generate_slide4():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'Feature Object: Comprehensive Data Container',
           ha='center', fontsize=16, weight='bold')

    # Main Feature class box
    main_box = Rectangle((3, 2), 6, 4.5, facecolor='#D9E1F2', edgecolor='black', linewidth=2)
    ax.add_patch(main_box)

    # Class name
    ax.text(6, 6.2, 'Feature', ha='center', fontsize=14, weight='bold')
    ax.plot([3, 9], [6, 6], 'k-', linewidth=2)

    # Attributes section
    attributes = [
        'Identifiers:',
        '  • id: int',
        '  • rt: float (retention time)',
        '  • ri: float (retention index)',
        '  • mz: float (base m/z)',
        '',
        'Spectral Data:',
        '  • spectrum: [(mz, intensity), ...]',
        '',
        'Quantitative Data:',
        '  • abundances: {sample_name: area}',
        '  • normalization_factors: {sample: factor}',
        '',
        'Quality Metrics:',
        '  • bff_threshold: float',
        '  • passed_bff: bool',
        '  • is_normalized: bool'
    ]

    y_pos = 5.7
    for attr in attributes:
        ax.text(3.2, y_pos, attr, fontsize=9, family='monospace', verticalalignment='top')
        y_pos -= 0.25

    # Methods section
    ax.plot([3, 9], [2.5, 2.5], 'k-', linewidth=2)
    ax.text(6, 2.3, 'calculate_bff(blank_cols, sample_cols)',
           ha='center', fontsize=9, family='monospace')

    # Example instantiation
    example = 'feat = Feature(id=42, rt=5.23, ri=1180, mz=128.0)\nfeat.spectrum = [(128, 999), (127, 450), ...]'
    ax.text(1, 1, example, fontsize=8, family='monospace',
           bbox=dict(boxstyle='round', facecolor='#FFF4CC', alpha=0.9))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'slide4_feature_model.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 4: Feature Model")


# ==============================================================================
# SLIDE 5: Blank Feature Filtering (BFF)
# ==============================================================================
def generate_slide5():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'Blank Feature Filtering: Statistical Background Removal',
           ha='center', fontsize=16, weight='bold')

    # Formula box
    formula_text = r'Threshold = 5 × (μ$_{blank}$ + 3σ$_{blank}$)'
    ax.text(6, 6.8, formula_text, ha='center', fontsize=14, weight='bold',
           bbox=dict(boxstyle='round', facecolor='#FFE699', edgecolor='black', linewidth=2))

    # Create box plot style visualization
    np.random.seed(42)
    blank_data = np.random.lognormal(3, 0.5, 30)
    sample_pass_data = np.random.lognormal(5.5, 0.4, 30)
    sample_fail_data = np.random.lognormal(3.5, 0.4, 30)

    # Create subplot for distribution
    ax_dist = fig.add_axes([0.15, 0.15, 0.7, 0.55])

    # Box plots
    bp = ax_dist.boxplot([blank_data, sample_fail_data, sample_pass_data],
                          positions=[1, 2, 3], widths=0.5,
                          labels=['Blanks', 'Sample\n(Fail)', 'Sample\n(Pass)'],
                          patch_artist=True)

    # Color the boxes
    bp['boxes'][0].set_facecolor('#C5D9F1')
    bp['boxes'][1].set_facecolor(COLOR_FAIL)
    bp['boxes'][2].set_facecolor(COLOR_SUCCESS)

    # Calculate and plot threshold
    mean_blank = np.mean(blank_data)
    std_blank = np.std(blank_data, ddof=1)
    threshold = 5 * (mean_blank + 3 * std_blank)

    ax_dist.axhline(y=threshold, color='red', linestyle='--', linewidth=2, label='BFF Threshold')

    # Annotations
    ax_dist.text(1, mean_blank, f'μ={mean_blank:.0f}', ha='center', va='bottom', fontsize=10)
    ax_dist.text(3.5, threshold, f'Threshold={threshold:.0f}', va='center', fontsize=11, weight='bold')

    ax_dist.set_ylabel('Peak Area (abundance)', fontsize=12)
    ax_dist.set_title('Distribution of Peak Areas Across Sample Types', fontsize=12)
    ax_dist.legend(loc='upper left', fontsize=10)
    ax_dist.grid(axis='y', alpha=0.3)

    # Decision logic
    ax.text(10.5, 3.5, 'Decision:\nIF max(sample) > threshold\n  THEN pass\nELSE\n  THEN reject',
           fontsize=10, family='monospace',
           bbox=dict(boxstyle='round', facecolor='#E7E6E6', edgecolor='black', linewidth=1.5))

    plt.savefig(OUTPUT_DIR / 'slide5_bff_filtering.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 5: BFF Filtering")


# ==============================================================================
# SLIDE 6: Internal Standard Normalization
# ==============================================================================
def generate_slide6():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'Internal Standard Normalization: Three Detection Methods',
           ha='center', fontsize=16, weight='bold')

    # Three parallel methods
    methods = [
        {
            'x': 1,
            'title': 'Method 1:\nManual Entry',
            'color': '#8EA9DB',
            'steps': ['User provides\nIS peak areas', 'Direct input\nvia table/CSV']
        },
        {
            'x': 4.5,
            'title': 'Method 2:\nAuto m/z + RI/RT',
            'color': '#70AD47',
            'steps': ['Search by\ntarget m/z', 'Match within\nRI/RT tolerance']
        },
        {
            'x': 8,
            'title': 'Method 3:\nAuto MSP Match',
            'color': '#FFC000',
            'steps': ['Load IS\nspectrum', 'Find best\nspectral match']
        }
    ]

    for method in methods:
        # Method header
        create_rounded_box(ax, (method['x'], 6), 2, 0.6, method['title'],
                          method['color'], fontsize=10)

        # Steps
        for i, step in enumerate(method['steps']):
            y = 5 - i * 1
            create_rounded_box(ax, (method['x'], y), 2, 0.6, step,
                              '#E7E6E6', 'black', fontsize=9)
            if i > 0:
                create_arrow(ax, (method['x'] + 1, 5 - (i-1)*1),
                           (method['x'] + 1, y + 0.6))

    # Convergence
    create_rounded_box(ax, (4, 2.5), 4, 0.7,
                      'Calculate Normalization Factors',
                      COLOR_PROCESS, fontsize=11)

    # Arrows to convergence
    create_arrow(ax, (2, 4), (5, 3.2))
    create_arrow(ax, (5.5, 4), (6, 3.2))
    create_arrow(ax, (9, 4), (7, 3.2))

    # Final step
    create_rounded_box(ax, (4, 1.5), 4, 0.7,
                      'Apply to All Features',
                      COLOR_SUCCESS, fontsize=11)
    create_arrow(ax, (6, 2.5), (6, 2.2))

    # Formula
    formula = 'Factor = median(IS_areas) / IS_area_sample\nNormalized_abundance = raw_abundance × Factor'
    ax.text(6, 0.5, formula, ha='center', fontsize=9, family='monospace',
           bbox=dict(boxstyle='round', facecolor='#FFE699', alpha=0.9))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'slide6_is_normalization.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 6: IS Normalization")


# ==============================================================================
# SLIDE 7: Library Matching Engine Funnel
# ==============================================================================
def generate_slide7():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'Hierarchical Filtering for Library Matching',
           ha='center', fontsize=16, weight='bold')

    # Funnel stages with numbers
    stages = [
        (6, 6.5, 5, 0.6, 'Features Passing BFF', 'N = 5,432', COLOR_DATA),
        (6, 5.5, 4, 0.6, 'RI Window Filter (±50)', 'N = 2,156', COLOR_FILTER),
        (6, 4.5, 3, 0.6, 'Spectral Similarity\n(Dot Product > 0.70)', 'N = 843', COLOR_FILTER),
        (6, 3.5, 2, 0.6, 'RI Error < 25', 'N = 412', COLOR_FILTER),
        (6, 2.5, 1.5, 0.6, 'RHRMF Formula Match', 'N = 287', COLOR_SUCCESS)
    ]

    for i, (x, y, width, height, label, count, color) in enumerate(stages):
        # Trapezoid/rectangle for funnel effect
        x_left = x - width/2
        x_right = x + width/2

        rect = Rectangle((x_left, y), width, height,
                        facecolor=color, edgecolor='black', linewidth=2, alpha=0.7)
        ax.add_patch(rect)

        ax.text(x, y + height/2, label, ha='center', va='center',
               fontsize=11, weight='bold', color='white')

        ax.text(x + width/2 + 0.5, y + height/2, count,
               ha='left', va='center', fontsize=10, weight='bold')

        # Arrow to next stage
        if i < len(stages) - 1:
            next_y = stages[i+1][1]
            create_arrow(ax, (x, y), (x, next_y + stages[i+1][3]), linewidth=3)

    # Binary search illustration
    ax.text(1, 5.5, 'Binary Search\non Sorted RI', ha='center', fontsize=9,
           bbox=dict(boxstyle='round', facecolor='#E7E6E6'))
    create_arrow(ax, (2, 5.5), (3.5, 5.8), linewidth=1.5)

    # Efficiency note
    ax.text(6, 1.5, '95% reduction through hierarchical filtering',
           ha='center', fontsize=10, style='italic', weight='bold')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'slide7_matching_funnel.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 7: Matching Funnel")


# ==============================================================================
# SLIDE 8: Spectral Similarity Scoring
# ==============================================================================
def generate_slide8():
    fig, ax = plt.subplots(figsize=(12, 8))

    # Title
    fig.suptitle('Spectral Similarity: Dot Product Scoring', fontsize=16, weight='bold')

    # Create mirror spectrum plot
    ax_spectrum = fig.add_axes([0.1, 0.35, 0.8, 0.5])

    # Query spectrum (top, pointing down)
    query_mz = np.array([43, 58, 71, 86, 101, 128, 142])
    query_int = np.array([450, 120, 680, 999, 340, 560, 180])
    query_int_norm = query_int / 999.0

    # Library spectrum (bottom, pointing up)
    lib_mz = np.array([43, 58, 71, 86, 101, 128, 142, 157])
    lib_int = np.array([420, 150, 700, 999, 310, 590, 200, 90])
    lib_int_norm = lib_int / 999.0

    # Plot query (negative for mirror effect)
    ax_spectrum.bar(query_mz, query_int_norm, width=2, color='#4472C4',
                   alpha=0.8, label='Query Spectrum')

    # Plot library (positive)
    ax_spectrum.bar(lib_mz, -lib_int_norm, width=2, color='#ED7D31',
                   alpha=0.8, label='Library Spectrum')

    # Highlight matching peaks
    matching_mz = set(query_mz) & set(lib_mz)
    for mz in matching_mz:
        ax_spectrum.axvline(x=mz, color='green', linestyle=':', linewidth=2, alpha=0.5)

    ax_spectrum.set_xlabel('m/z', fontsize=12)
    ax_spectrum.set_ylabel('Normalized Intensity', fontsize=12)
    ax_spectrum.axhline(y=0, color='black', linewidth=1)
    ax_spectrum.legend(loc='upper right', fontsize=10)
    ax_spectrum.set_ylim(-1.1, 1.1)
    ax_spectrum.grid(axis='x', alpha=0.3)

    # Formula box
    formula_text = (
        'Dot Product = cos θ = (A · B) / (|A| × |B|)\n\n'
        'A · B = Σ(intensity_query × intensity_library)\n'
        '|A| = √(Σ intensity_query²)\n'
        '|B| = √(Σ intensity_library²)\n\n'
        'Range: [0, 1]  •  Threshold: > 0.70'
    )

    ax_formula = fig.add_axes([0.15, 0.05, 0.7, 0.25])
    ax_formula.axis('off')
    ax_formula.text(0.5, 0.5, formula_text, ha='center', va='center', fontsize=10,
                   family='monospace',
                   bbox=dict(boxstyle='round', facecolor='#FFE699',
                            edgecolor='black', linewidth=2))

    plt.savefig(OUTPUT_DIR / 'slide8_spectral_scoring.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 8: Spectral Scoring")


# ==============================================================================
# SLIDE 9: Retention Index Calibration
# ==============================================================================
def generate_slide9():
    fig, ax = plt.subplots(figsize=(12, 8))

    # Title
    fig.suptitle('Retention Index Calibration: n-Alkane Standards',
                fontsize=16, weight='bold')

    # Create calibration plot
    ax_cal = fig.add_axes([0.15, 0.3, 0.7, 0.55])

    # n-Alkane calibration data (realistic)
    carbon_numbers = np.array([9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])
    retention_times = np.array([4.2, 5.1, 6.3, 7.8, 9.5, 11.4, 13.5, 15.8, 18.3, 21.0, 23.8, 26.8])

    # Fit polynomial (cubic for realistic kovats)
    coeffs = np.polyfit(retention_times, carbon_numbers * 100, 3)
    poly = np.poly1d(coeffs)

    # Plot calibration points
    ax_cal.scatter(retention_times, carbon_numbers * 100, s=150,
                  color=COLOR_SUCCESS, edgecolor='black', linewidth=2,
                  label='n-Alkane Standards', zorder=3)

    # Plot fitted curve
    rt_smooth = np.linspace(retention_times.min(), retention_times.max(), 200)
    ri_smooth = poly(rt_smooth)
    ax_cal.plot(rt_smooth, ri_smooth, 'b-', linewidth=2, label='Calibration Curve')

    # Example unknown compound
    unknown_rt = 14.2
    unknown_ri = poly(unknown_rt)
    ax_cal.scatter([unknown_rt], [unknown_ri], s=200, marker='*',
                  color='red', edgecolor='black', linewidth=2,
                  label='Unknown Compound', zorder=4)

    # Annotation for unknown
    ax_cal.annotate(f'RT={unknown_rt:.1f} min\nRI={unknown_ri:.0f}',
                   xy=(unknown_rt, unknown_ri), xytext=(unknown_rt+2, unknown_ri+100),
                   arrowprops=dict(arrowstyle='->', lw=2, color='red'),
                   fontsize=11, weight='bold',
                   bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))

    ax_cal.set_xlabel('Retention Time (minutes)', fontsize=12)
    ax_cal.set_ylabel('Retention Index (Kovats)', fontsize=12)
    ax_cal.legend(loc='upper left', fontsize=10)
    ax_cal.grid(True, alpha=0.3)
    ax_cal.set_title('Cubic Polynomial Interpolation', fontsize=11, style='italic')

    # Equation box
    equation_text = (
        'RI = f(RT) using cubic interpolation\n'
        'RI(n-alkane) = carbon_number × 100\n\n'
        'Enables instrument-independent matching'
    )
    ax_eq = fig.add_axes([0.15, 0.05, 0.7, 0.18])
    ax_eq.axis('off')
    ax_eq.text(0.5, 0.5, equation_text, ha='center', va='center', fontsize=10,
              bbox=dict(boxstyle='round', facecolor='#E7E6E6',
                       edgecolor='black', linewidth=1.5))

    plt.savefig(OUTPUT_DIR / 'slide9_ri_calibration.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 9: RI Calibration")


# ==============================================================================
# SLIDE 10: Level 2 Identification Logic
# ==============================================================================
def generate_slide10():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'Level 2 Identification: Multi-Criteria Decision Logic',
           ha='center', fontsize=16, weight='bold')

    # Logic gates (AND gates)
    gates = [
        (2, 5.5, 'Spectral Score\n> 0.70', COLOR_PROCESS),
        (6, 5.5, 'RI Error\n< 25 units', COLOR_PROCESS),
        (10, 5.5, 'RHRMF\nFormula Match', COLOR_PROCESS)
    ]

    for x, y, label, color in gates:
        create_rounded_box(ax, (x - 0.75, y), 1.5, 0.8, label, color, fontsize=10)

        # Pass/Fail indicators
        ax.text(x, y - 0.5, '✓ PASS', ha='center', fontsize=9,
               color=COLOR_SUCCESS, weight='bold')
        ax.text(x, y - 0.8, '✗ FAIL', ha='center', fontsize=9,
               color=COLOR_FAIL, weight='bold')

    # AND logic
    create_rounded_box(ax, (5, 3.5), 2, 0.6, 'AND', COLOR_DECISION, fontsize=12)

    # Arrows from gates to AND
    create_arrow(ax, (2, 5.5), (5.5, 4.1))
    create_arrow(ax, (6, 5.5), (6, 4.1))
    create_arrow(ax, (10, 5.5), (6.5, 4.1))

    # Decision diamond
    diamond = patches.FancyBboxPatch((5.3, 2.2), 1.4, 0.8,
                                     boxstyle="round,pad=0.1",
                                     facecolor=COLOR_DECISION,
                                     edgecolor='black', linewidth=2)
    ax.add_patch(diamond)
    ax.text(6, 2.6, 'All Pass?', ha='center', va='center',
           fontsize=11, weight='bold')

    create_arrow(ax, (6, 3.5), (6, 3))

    # Outcomes
    create_rounded_box(ax, (3, 1), 2, 0.6, 'Level 2 ID\nConfident',
                      COLOR_SUCCESS, fontsize=11)
    create_rounded_box(ax, (7.5, 1), 2, 0.6, 'No Match\nReject',
                      COLOR_FAIL, fontsize=11)

    # Decision arrows
    create_arrow(ax, (5.5, 2.4), (4.5, 1.6))
    create_arrow(ax, (6.5, 2.4), (8, 1.6))

    ax.text(4.8, 2, 'YES', fontsize=9, weight='bold', color=COLOR_SUCCESS)
    ax.text(7.2, 2, 'NO', fontsize=9, weight='bold', color=COLOR_FAIL)

    # Reference
    ax.text(6, 0.3, 'Following Koelmel et al. 2022 Level 2 criteria',
           ha='center', fontsize=9, style='italic')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'slide10_level2_logic.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 10: Level 2 Logic")


# ==============================================================================
# SLIDE 11: Surrogate Standard Recovery
# ==============================================================================
def generate_slide11():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'Surrogate Standard Recovery: QC Workflow',
           ha='center', fontsize=16, weight='bold')

    # Workflow stages
    # Stage 1: Spike
    create_rounded_box(ax, (0.5, 6), 2, 0.6, 'Spike Labeled\nSurrogates',
                      COLOR_DATA, fontsize=10)

    # Stage 2: Extract
    create_rounded_box(ax, (3, 6), 2, 0.6, 'Sample\nExtraction',
                      COLOR_PROCESS, fontsize=10)
    create_arrow(ax, (2.5, 6.3), (3, 6.3))

    # Stage 3: Analysis
    create_rounded_box(ax, (5.5, 6), 2, 0.6, 'GC-MS\nAnalysis',
                      COLOR_PROCESS, fontsize=10)
    create_arrow(ax, (5, 6.3), (5.5, 6.3))

    # Two parallel paths
    # Reference samples
    create_rounded_box(ax, (1.5, 4.5), 2, 0.6, 'Reference\nSamples',
                      '#B4C7E7', 'black', fontsize=10)
    ax.text(2.5, 3.8, 'Known spike\nconcentration', ha='center', fontsize=8)

    # Test samples
    create_rounded_box(ax, (8, 4.5), 2, 0.6, 'Test\nSamples',
                      '#B4C7E7', 'black', fontsize=10)
    ax.text(9, 3.8, 'Unknown\nrecovery', ha='center', fontsize=8)

    # Arrows down from analysis
    create_arrow(ax, (5.5, 6), (3, 5.1))
    create_arrow(ax, (7.5, 6), (8.5, 5.1))

    # Calculate recovery
    create_rounded_box(ax, (4, 2.5), 4, 0.7,
                      'Calculate Recovery %',
                      COLOR_PROCESS, fontsize=11)

    create_arrow(ax, (2.5, 4.5), (5, 3.2))
    create_arrow(ax, (9, 4.5), (7, 3.2))

    # Formula
    formula = '% Recovery = (Sample_norm / Spike_ratio) / \n             (Reference_norm / Ref_spike_ratio) × 100'
    ax.text(6, 1.5, formula, ha='center', fontsize=9, family='monospace',
           bbox=dict(boxstyle='round', facecolor='#FFE699', alpha=0.9))

    # QC zones
    zones = [
        (1, 0.3, '70-130%', COLOR_SUCCESS, 'Acceptable'),
        (4, 0.3, '50-70%\n130-150%', COLOR_DECISION, 'Warning'),
        (7.5, 0.3, '<50%\n>150%', COLOR_FAIL, 'Fail')
    ]

    for x, y, range_text, color, label in zones:
        create_rounded_box(ax, (x, y), 1.8, 0.5, range_text, color, fontsize=9)
        ax.text(x + 0.9, y - 0.3, label, ha='center', fontsize=8, weight='bold')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'slide11_surrogate_recovery.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 11: Surrogate Recovery")


# ==============================================================================
# SLIDE 12: Multi-Format Report Generation
# ==============================================================================
def generate_slide12():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'Automated Report Generation: CSV and PDF Outputs',
           ha='center', fontsize=16, weight='bold')

    # Split screen layout
    # Left side - CSV
    csv_box = Rectangle((0.5, 1.5), 5, 5, facecolor='white',
                        edgecolor='black', linewidth=2)
    ax.add_patch(csv_box)
    ax.text(3, 6.2, 'CSV Report', ha='center', fontsize=13, weight='bold')

    # CSV content mockup
    csv_content = [
        'Feature_ID,Compound,Formula,Score',
        '42,Naphthalene,C10H8,0.95',
        '87,Benzene,C6H6,0.88',
        '...,Sample_1,Sample_2,Sample_3',
        '...,12500,14200,11800',
        '...,8900,9100,8700',
        '',
        'Columns:',
        '• Identification results',
        '• Scores (spectral, RI)',
        '• Sample abundances',
        '• IS normalization factors',
        '• Metadata (CAS, InChIKey)'
    ]

    y_pos = 5.8
    for line in csv_content:
        if line.startswith('Columns:'):
            ax.text(0.7, y_pos, line, fontsize=9, weight='bold')
        else:
            ax.text(0.7, y_pos, line, fontsize=8, family='monospace')
        y_pos -= 0.3

    # Right side - PDF
    pdf_box = Rectangle((6.5, 1.5), 5, 5, facecolor='white',
                        edgecolor='black', linewidth=2)
    ax.add_patch(pdf_box)
    ax.text(9, 6.2, 'PDF Report', ha='center', fontsize=13, weight='bold')

    # PDF content mockup
    pdf_elements = [
        (7, 5.5, 1.8, 0.8, 'Mirror\nSpectra', '#B4C7E7'),
        (9.2, 5.5, 1.8, 0.8, 'Chemical\nStructures', '#C5E0B4'),
        (7, 4.3, 1.8, 0.8, 'Match\nScores', '#F4B084'),
        (9.2, 4.3, 1.8, 0.8, 'RI\nValidation', '#FFD966'),
        (7, 3.1, 3.8, 0.8, 'GHS Hazard Matrix', '#F8CBAD')
    ]

    for x, y, w, h, label, color in pdf_elements:
        create_rounded_box(ax, (x, y), w, h, label, color, 'black', fontsize=9)

    # EPA CompTox integration
    create_rounded_box(ax, (8, 2), 2, 0.5, 'EPA CompTox\nAPI',
                      '#C5504B', fontsize=9)
    ax.text(9, 1.5, 'Toxicity data', ha='center', fontsize=8, style='italic')

    # Bottom note
    ax.text(6, 0.5, 'Dual format enables statistical analysis (CSV) and visualization (PDF)',
           ha='center', fontsize=10, style='italic')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'slide12_report_generation.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("[OK] Generated Slide 12: Report Generation")


# ==============================================================================
# Main execution
# ==============================================================================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("Generating K2 Presentation Diagrams")
    print("="*60 + "\n")

    generate_slide1()
    generate_slide2()
    generate_slide3()
    generate_slide4()
    generate_slide5()
    generate_slide6()
    generate_slide7()
    generate_slide8()
    generate_slide9()
    generate_slide10()
    generate_slide11()
    generate_slide12()

    print("\n" + "="*60)
    print(f"[SUCCESS] All 12 diagrams generated successfully!")
    print(f"[OUTPUT] Saved to: {OUTPUT_DIR.absolute()}")
    print("="*60 + "\n")
