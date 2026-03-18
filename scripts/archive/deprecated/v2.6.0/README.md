# Deprecated Modules - v2.6.0

**Date:** January 23, 2026
**Reason:** Removed in v2.7.0 to simplify K2 and focus on core identification functionality

## Deprecated Files

### stats_engine.py (~250 lines)
**Purpose:** Statistical analysis module for group comparisons
- Performed PCA (Principal Component Analysis)
- Calculated volcano plots (log2 fold change vs p-value)
- Generated t-tests and ANOVA for group comparisons
- Calculated group means, std deviations, fold changes

**Why Removed:**
- Added significant complexity requiring scikit-learn and scipy dependencies
- Users preferred to export data and perform statistics in their own tools
- Core K2 mission is identification, not statistical analysis
- Maintenance burden for features rarely used

### visualizer.py (~450 lines)
**Purpose:** Visualization module for statistical plots
- Created volcano plots
- Generated PCA score plots
- Generated hierarchical clustering heatmaps
- Rendered statistical visualizations with matplotlib

**Why Removed:**
- Tightly coupled with stats_engine.py
- Not needed after statistics removal
- Mirror plots for spectral matching still available (handled in reporter.py)

### gcms_pipeline_guide.docx
**Purpose:** Original user guide document
- Legacy Microsoft Word documentation

**Why Removed:**
- Superseded by K2_USER_GUIDE.md (markdown format)
- Markdown is easier to maintain and version control

### run_pipeline.bat
**Purpose:** CLI launcher script
- Launched gcms_pipeline.py command-line interface

**Why Removed:**
- K2 GUI is now the primary interface
- CLI still accessible via `python scripts/gcms_pipeline.py`

### IdentificationSummary.png & Spectral Details.png
**Purpose:** Screenshots for old documentation

**Why Removed:**
- No longer referenced in any documentation
- Outdated UI screenshots

## Migration Path

If you need statistical analysis:
1. Export the Level 2 matches CSV file
2. Open in R, Python (pandas/scipy), or Prism
3. Perform your preferred statistical tests
4. Generate publication-quality figures with your tool of choice

## Restore Instructions

If you absolutely need these modules back:
1. Copy these files back to `scripts/src/`
2. Reinstall dependencies: `pip install scikit-learn scipy`
3. Restore the Global Statistics tab in `k2_screens.py` (see v2.6.0_stable archive)
4. Re-add imports in `cli.py` and `k2_screens.py`

**Note:** We strongly recommend using dedicated statistical software instead.
