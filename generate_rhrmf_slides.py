#!/usr/bin/env python3
"""
Generate RHRMF presentation slides for ECE seminar
Creates 5 figures explaining the Reverse High Resolution Mass Filter algorithm
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle
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
COLOR_SUCCESS = '#70AD47'     # Green for success
COLOR_FAIL = '#C5504B'        # Red for fail/reject
COLOR_HIGHLIGHT = '#9966FF'   # Purple for highlights

def create_rounded_box(ax, xy, width, height, text, color, text_color='white', fontsize=10, linewidth=2):
    """Helper to create a rounded box with text"""
    box = FancyBboxPatch(xy, width, height, boxstyle="round,pad=0.05",
                         facecolor=color, edgecolor='black', linewidth=linewidth)
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
# SLIDE 1: RHRMF Purpose and Overview
# ==============================================================================
def generate_slide1():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title assertion
    ax.text(6, 7.3, 'RHRMF validates that experimental peaks can be explained by',
           ha='center', fontsize=15, weight='bold')
    ax.text(6, 6.9, 'fragment combinations from the candidate compound formula',
           ha='center', fontsize=15, weight='bold')

    # Problem box
    create_rounded_box(ax, (0.5, 5.2), 5, 1.2,
                      'THE PROBLEM:\nLow-resolution unit mass libraries may match\nto incorrect compounds with similar spectra',
                      COLOR_FAIL, fontsize=11)

    # Solution box
    create_rounded_box(ax, (6.5, 5.2), 5, 1.2,
                      'THE SOLUTION:\nUse high-resolution experimental data to verify\nthat peaks match the molecular formula',
                      COLOR_SUCCESS, fontsize=11)

    # Example scenario
    ax.text(6, 4.3, 'Example Scenario:', ha='center', fontsize=13, weight='bold', style='italic')

    # Two compound boxes
    create_rounded_box(ax, (1, 2.8), 4.5, 0.8,
                      'Compound A: C6H12O6\n(Glucose, MW=180.06)',
                      COLOR_DATA, fontsize=10)

    create_rounded_box(ax, (6.5, 2.8), 4.5, 0.8,
                      'Compound B: C9H8O4\n(Aspirin, MW=180.04)',
                      COLOR_DATA, fontsize=10)

    ax.text(6, 2.1, 'Both have unit mass = 180 Da, but different formulas!',
           ha='center', fontsize=11, style='italic')

    # RHRMF role
    create_rounded_box(ax, (2, 0.8), 8, 0.9,
                      'RHRMF checks if experimental peak masses at 0.015 Da precision\ncan be formed from the candidate formula elements',
                      COLOR_HIGHLIGHT, fontsize=11)

    # Save
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'rhrmf_slide1_purpose.png', dpi=300, bbox_inches='tight')
    print("Generated: rhrmf_slide1_purpose.png")
    plt.close()

# ==============================================================================
# SLIDE 2: Algorithm Workflow
# ==============================================================================
def generate_slide2():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'RHRMF Algorithm Workflow',
           ha='center', fontsize=16, weight='bold')
    ax.text(6, 7.1, 'Iterates through matched peaks to calculate an explanation score',
           ha='center', fontsize=12, style='italic')

    # Input box
    create_rounded_box(ax, (0.5, 6), 2.5, 0.7,
                      'INPUT:\nExperimental Spectrum\n+ Library Formula',
                      COLOR_DATA, fontsize=10)

    # Step 1: Parse formula
    create_rounded_box(ax, (4, 6), 2, 0.7,
                      'Step 1:\nParse Formula\nC6H12O6',
                      COLOR_PROCESS, fontsize=10)
    create_arrow(ax, (3, 6.35), (4, 6.35))
    ax.text(5, 5.4, '{C:6, H:12, O:6}', ha='center', fontsize=9,
           bbox=dict(boxstyle='round', facecolor='wheat'))

    # Step 2: Bin library spectrum
    create_rounded_box(ax, (7, 6), 2, 0.7,
                      'Step 2:\nBin Library Peaks\nto Unit Mass',
                      COLOR_PROCESS, fontsize=10)
    create_arrow(ax, (6, 6.35), (7, 6.35))
    ax.text(8, 5.4, '{60, 73, 89, 117}', ha='center', fontsize=9,
           bbox=dict(boxstyle='round', facecolor='wheat'))

    # Step 3: Loop through experimental peaks
    create_rounded_box(ax, (10, 6), 1.5, 0.7,
                      'Step 3:\nFor each\nexp peak...',
                      COLOR_PROCESS, fontsize=9)
    create_arrow(ax, (9, 6.35), (10, 6.35))

    # Decision diamond
    diamond_x, diamond_y = 2.5, 3.5
    diamond = patches.FancyBboxPatch((diamond_x, diamond_y), 1.5, 1,
                                    boxstyle="round,pad=0.1",
                                    facecolor=COLOR_DECISION,
                                    edgecolor='black', linewidth=2)
    ax.add_patch(diamond)
    ax.text(diamond_x + 0.75, diamond_y + 0.5,
           'Unit mass\nin library\nbins?',
           ha='center', va='center', fontsize=10, weight='bold')

    # Arrow from step 3 to decision
    create_arrow(ax, (10.75, 6), (3.25, 4.5), style='->', linewidth=2)

    # NO path
    ax.text(1.5, 3.9, 'NO', ha='center', fontsize=10, weight='bold', color=COLOR_FAIL)
    create_arrow(ax, (2.5, 4), (1.5, 4), color=COLOR_FAIL)
    create_rounded_box(ax, (0.3, 3.5), 1, 0.5, 'Skip peak', COLOR_FAIL, fontsize=9)

    # YES path
    ax.text(4.8, 3.9, 'YES', ha='center', fontsize=10, weight='bold', color=COLOR_SUCCESS)
    create_arrow(ax, (4, 4), (5, 4), color=COLOR_SUCCESS)

    # Sub-decision: Can explain?
    create_rounded_box(ax, (5.5, 3.5), 2.5, 1,
                      'Can peak mass\nbe explained by\nformula elements?\n(±0.015 Da)',
                      COLOR_DECISION, fontsize=9)

    # Explained counter
    ax.text(9, 4.3, 'YES → explained_peaks++', ha='center', fontsize=10,
           bbox=dict(boxstyle='round', facecolor=COLOR_SUCCESS, alpha=0.7))
    create_arrow(ax, (8, 4), (9, 4.2), color=COLOR_SUCCESS)

    ax.text(9, 3.7, 'NO → (no increment)', ha='center', fontsize=10,
           bbox=dict(boxstyle='round', facecolor=COLOR_FAIL, alpha=0.7))
    create_arrow(ax, (8, 3.8), (9, 3.8), color=COLOR_FAIL)

    # Always increment matched
    ax.text(5.5, 2.5, 'matched_peaks++ (always)', ha='center', fontsize=10,
           bbox=dict(boxstyle='round', facecolor='lightblue'))

    # Final calculation
    create_rounded_box(ax, (3, 0.8), 6, 0.9,
                      'RHRMF Score = (explained_peaks / matched_peaks) × 100',
                      COLOR_HIGHLIGHT, fontsize=12)

    # Threshold
    ax.text(6, 0.2, 'Threshold: RHRMF > 75% for Level 2 identification',
           ha='center', fontsize=11, style='italic', weight='bold')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'rhrmf_slide2_workflow.png', dpi=300, bbox_inches='tight')
    print("Generated: rhrmf_slide2_workflow.png")
    plt.close()

# ==============================================================================
# SLIDE 3: Formula Parsing & Peak Explanation Algorithm
# ==============================================================================
def generate_slide3():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.5, 'Peak Explanation: Recursive Combinatorial Solver',
           ha='center', fontsize=16, weight='bold')
    ax.text(6, 7.1, 'Determines if a target mass can be formed from formula elements',
           ha='center', fontsize=12, style='italic')

    # Example formula
    ax.text(2, 6.5, 'Given Formula: C6H12O6', fontsize=13, weight='bold',
           bbox=dict(boxstyle='round', facecolor=COLOR_DATA, alpha=0.7))

    ax.text(2, 6.0, 'Parsed: {C:6, H:12, O:6}', fontsize=11,
           bbox=dict(boxstyle='round', facecolor='wheat'))

    # Atom masses table
    ax.text(8, 6.5, 'Exact Atomic Masses:', fontsize=13, weight='bold')
    table_data = [
        ['Element', 'Mass (Da)'],
        ['C', '12.00000'],
        ['H', '1.00783'],
        ['O', '15.99491']
    ]

    table_y = 6.1
    for i, row in enumerate(table_data):
        color = 'lightgray' if i == 0 else 'white'
        for j, cell in enumerate(row):
            rect = Rectangle((7.5 + j*1.2, table_y - i*0.35), 1.15, 0.32,
                           facecolor=color, edgecolor='black', linewidth=1)
            ax.add_patch(rect)
            weight = 'bold' if i == 0 else 'normal'
            ax.text(7.5 + j*1.2 + 0.575, table_y - i*0.35 + 0.16, cell,
                   ha='center', va='center', fontsize=10, weight=weight)

    # Example target peak
    ax.text(6, 4.5, 'Example: Can we explain peak at m/z = 73.0284 Da?',
           ha='center', fontsize=13, weight='bold', style='italic',
           bbox=dict(boxstyle='round', facecolor=COLOR_DECISION))

    # Algorithm description
    algo_text = """Recursive Algorithm (memoized):

1. Try all combinations of elements up to their max count
2. Use greedy search: start with element combinations that maximize mass
3. Check if sum matches target ± tolerance (0.015 Da)
4. Prune branches that exceed target mass (optimization)
5. Cache results to avoid redundant calculations
    """

    ax.text(0.5, 3.5, algo_text, fontsize=10, family='monospace',
           bbox=dict(boxstyle='round', facecolor='lightcyan', alpha=0.8),
           verticalalignment='top')

    # Visualization of search
    ax.text(8, 3.8, 'Combinatorial Search:', fontsize=12, weight='bold')

    # Show some combinations
    combinations = [
        ('C3H5O', '53.039', 'Too low'),
        ('C4H9', '57.070', 'Too low'),
        ('C3H5O2', '73.029', 'MATCH!'),
        ('C4H9O', '73.065', 'Close but no'),
        ('C5H13', '73.102', 'Too high')
    ]

    y_pos = 3.3
    for combo, mass, result in combinations:
        is_match = 'MATCH' in result
        color = COLOR_SUCCESS if is_match else 'lightgray'
        text_color = 'black'
        weight = 'bold' if is_match else 'normal'

        ax.text(7.5, y_pos, f'{combo}', fontsize=9, weight=weight)
        ax.text(9.2, y_pos, f'{mass}', fontsize=9, weight=weight)
        ax.text(10.5, y_pos, f'{result}', fontsize=9, weight=weight,
               bbox=dict(boxstyle='round', facecolor=color, alpha=0.6))
        y_pos -= 0.35

    # Result box
    create_rounded_box(ax, (2, 0.5), 8, 0.8,
                      'Peak 73.0284 is EXPLAINED by formula C6H12O6 -> explained_peaks++',
                      COLOR_SUCCESS, fontsize=12)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'rhrmf_slide3_algorithm.png', dpi=300, bbox_inches='tight')
    print("Generated: rhrmf_slide3_algorithm.png")
    plt.close()

# ==============================================================================
# SLIDE 4: Example - Compound PASSES RHRMF
# ==============================================================================
def generate_slide4():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.6, 'Example 1: Compound PASSES RHRMF (Score = 100%)',
           ha='center', fontsize=16, weight='bold', color=COLOR_SUCCESS)

    # Compound info
    create_rounded_box(ax, (0.5, 6.5), 5, 0.8,
                      'Candidate: Glucose\nFormula: C6H12O6\nMW: 180.063 Da',
                      COLOR_DATA, fontsize=11)

    create_rounded_box(ax, (6.5, 6.5), 5, 0.8,
                      'Level 2 Criteria Already Met:\nSpectral Score: 850\nRI Error: 0.8%',
                      COLOR_SUCCESS, fontsize=10)

    # Spectrum visualization
    ax.text(1.5, 6, 'Experimental Spectrum (High-Res):', fontsize=12, weight='bold')

    # Table header
    headers = ['m/z (exp)', 'Intensity', 'Unit\nMass', 'In Lib?', 'Explained?', 'Formula']
    col_widths = [1.2, 1.0, 0.8, 0.8, 1.0, 1.5]
    x_start = 0.3
    y_table = 5.5

    # Draw header
    x_pos = x_start
    for i, (header, width) in enumerate(zip(headers, col_widths)):
        rect = Rectangle((x_pos, y_table), width, 0.4,
                       facecolor='lightgray', edgecolor='black', linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x_pos + width/2, y_table + 0.2, header,
               ha='center', va='center', fontsize=9, weight='bold')
        x_pos += width

    # Data rows - GOOD MATCH
    data_rows = [
        ['60.0211', '320', '60', 'Y', 'Y', 'C2H4O2'],
        ['73.0284', '850', '73', 'Y', 'Y', 'C3H5O2'],
        ['89.0239', '410', '89', 'Y', 'Y', 'C3H5O3'],
        ['117.0552', '290', '117', 'Y', 'Y', 'C5H9O3'],
        ['145.0501', '150', '145', 'Y', 'Y', 'C6H9O4']
    ]

    y_row = y_table - 0.4
    for row_idx, row in enumerate(data_rows):
        x_pos = x_start
        for col_idx, (cell, width) in enumerate(zip(row, col_widths)):
            bg_color = 'white' if row_idx % 2 == 0 else '#f0f0f0'
            if col_idx in [3, 4] and cell == 'Y':  # In lib and explained columns
                bg_color = '#d4edda'  # Light green

            rect = Rectangle((x_pos, y_row), width, 0.4,
                           facecolor=bg_color, edgecolor='black', linewidth=0.8)
            ax.add_patch(rect)

            fontsize = 9 if col_idx < 5 else 8
            ax.text(x_pos + width/2, y_row + 0.2, cell,
                   ha='center', va='center', fontsize=fontsize)
            x_pos += width
        y_row -= 0.4

    # Calculation box
    ax.text(8, 3.5, 'RHRMF Calculation:', fontsize=13, weight='bold')
    calc_text = """matched_peaks = 5
(all experimental peaks
 are in library bins)

explained_peaks = 5
(all can be formed from
 C6H12O6 elements)

RHRMF = (5/5) x 100
      = 100%
"""
    ax.text(8, 3.2, calc_text, fontsize=10, family='monospace',
           bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7),
           verticalalignment='top')

    # Result
    create_rounded_box(ax, (1, 0.5), 10, 0.9,
                      'RHRMF = 100% > 75% threshold -> PASS\nAll experimental peaks are chemically consistent with glucose formula',
                      COLOR_SUCCESS, fontsize=12)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'rhrmf_slide4_pass_example.png', dpi=300, bbox_inches='tight')
    print("Generated: rhrmf_slide4_pass_example.png")
    plt.close()

# ==============================================================================
# SLIDE 5: Example - Compound FAILS RHRMF
# ==============================================================================
def generate_slide5():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Title
    ax.text(6, 7.6, 'Example 2: Compound FAILS RHRMF (Score = 40%)',
           ha='center', fontsize=16, weight='bold', color=COLOR_FAIL)

    # Compound info
    create_rounded_box(ax, (0.5, 6.5), 5, 0.8,
                      'Candidate: Aspirin (WRONG)\nFormula: C9H8O4\nMW: 180.042 Da',
                      COLOR_FAIL, fontsize=11)

    create_rounded_box(ax, (6.5, 6.5), 5, 0.8,
                      'Level 2 Criteria Met (so far):\nSpectral Score: 780\nRI Error: 1.2%',
                      COLOR_DECISION, fontsize=10)

    # Spectrum visualization
    ax.text(1.5, 6, 'Experimental Spectrum (same as before):', fontsize=12, weight='bold')

    # Table header (same structure)
    headers = ['m/z (exp)', 'Intensity', 'Unit\nMass', 'In Lib?', 'Explained?', 'Why Not?']
    col_widths = [1.2, 1.0, 0.8, 0.8, 1.0, 1.8]
    x_start = 0.3
    y_table = 5.5

    # Draw header
    x_pos = x_start
    for i, (header, width) in enumerate(zip(headers, col_widths)):
        rect = Rectangle((x_pos, y_table), width, 0.4,
                       facecolor='lightgray', edgecolor='black', linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x_pos + width/2, y_table + 0.2, header,
               ha='center', va='center', fontsize=9, weight='bold')
        x_pos += width

    # Data rows - BAD MATCH (aspirin doesn't have enough H or right composition)
    data_rows = [
        ['60.0211', '320', '60', 'Y', 'N', 'Need C2H4O2: not enough H'],
        ['73.0284', '850', '73', 'Y', 'N', 'Need C3H5O2: not enough H'],
        ['89.0239', '410', '89', 'Y', 'Y', 'C3H5O3 (possible)'],
        ['117.0552', '290', '117', 'Y', 'N', 'Need C5H9O3: not enough H'],
        ['145.0501', '150', '145', 'Y', 'Y', 'C6H9O4 (possible)']
    ]

    y_row = y_table - 0.4
    for row_idx, row in enumerate(data_rows):
        x_pos = x_start
        for col_idx, (cell, width) in enumerate(zip(row, col_widths)):
            bg_color = 'white' if row_idx % 2 == 0 else '#f0f0f0'

            # Color code the "Explained?" column
            if col_idx == 4:
                if cell == 'Y':
                    bg_color = '#d4edda'  # Light green
                else:
                    bg_color = '#f8d7da'  # Light red

            rect = Rectangle((x_pos, y_row), width, 0.4,
                           facecolor=bg_color, edgecolor='black', linewidth=0.8)
            ax.add_patch(rect)

            fontsize = 8 if col_idx == 5 else 9
            ax.text(x_pos + width/2, y_row + 0.2, cell,
                   ha='center', va='center', fontsize=fontsize)
            x_pos += width
        y_row -= 0.4

    # Calculation box
    ax.text(8, 3.5, 'RHRMF Calculation:', fontsize=13, weight='bold')
    calc_text = """matched_peaks = 5
(all experimental peaks
 are in library bins)

explained_peaks = 2
(only 2 peaks can be
 formed from C9H8O4)

RHRMF = (2/5) x 100
      = 40%
"""
    ax.text(8, 3.2, calc_text, fontsize=10, family='monospace',
           bbox=dict(boxstyle='round', facecolor='#f8d7da', alpha=0.7),
           verticalalignment='top')

    # Key insight box
    create_rounded_box(ax, (0.5, 1.8), 6, 0.7,
                      'KEY INSIGHT:\nAspirin (C9H8O4) has only 8 H atoms\nCannot form fragments requiring 9-12 H!',
                      COLOR_DECISION, fontsize=10)

    # Result
    create_rounded_box(ax, (1, 0.5), 10, 0.9,
                      'RHRMF = 40% < 75% threshold -> FAIL (Reject Match)\nExperimental spectrum is NOT consistent with aspirin formula',
                      COLOR_FAIL, fontsize=12)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'rhrmf_slide5_fail_example.png', dpi=300, bbox_inches='tight')
    print("Generated: rhrmf_slide5_fail_example.png")
    plt.close()

# ==============================================================================
# Main execution
# ==============================================================================
if __name__ == '__main__':
    print("Generating RHRMF presentation slides...")
    print("=" * 60)

    generate_slide1()
    generate_slide2()
    generate_slide3()
    generate_slide4()
    generate_slide5()

    print("=" * 60)
    print("All 5 RHRMF slides generated successfully!")
    print(f"Location: {OUTPUT_DIR.absolute()}")
    print("\nFiles created:")
    print("  1. rhrmf_slide1_purpose.png      - RHRMF purpose and problem statement")
    print("  2. rhrmf_slide2_workflow.png     - Algorithm workflow diagram")
    print("  3. rhrmf_slide3_algorithm.png    - Formula parsing and peak explanation")
    print("  4. rhrmf_slide4_pass_example.png - Example: Glucose (PASSES)")
    print("  5. rhrmf_slide5_fail_example.png - Example: Aspirin (FAILS)")
