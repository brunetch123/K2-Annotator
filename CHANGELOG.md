# Changelog

All notable changes to **K2 Annotator** (formerly K2 Analyzer / K2 GC-MS Suspect Screening Pipeline) will be documented in this file.

## [3.0.8] - 2026-05-09

### Changed
- **Renamed software to K2 Annotator** ahead of public release. Internal command-line and Python-package layouts are unchanged; only the user-facing brand name, the splash logo, and documentation references are updated.
- **New splash logo** (`K2Logo.png`) replaces the previous wordmark on the welcome screen and in the README. The window icon (`K2Icon.png`) is unchanged.
- GUI window title, About dialog, and User Guide popup now read "K2 Annotator". README, CHANGELOG, launcher batch file, and architecture / module diagrams updated to match.
- Older `K2Logo2.png` is retained as a fallback in `WelcomeScreen` so the splash screen still renders on machines that have an older asset bundle.

### Backward Compatibility
- File extensions (`.K2`, `.K2config`) are unchanged — existing project files and presets continue to load.
- The `~/.k2/k2_defaults.json` user-config location is unchanged — existing user settings carry over.
- Git repository URL is unchanged.

---

## [3.0.7] - 2026-05-05

### Fixed
- **Internal Standard normalization direction was inverted.** The per-sample factor was computed as `IS(sample) / max(IS)` and applied multiplicatively, which scaled samples with lower IS response *down* — the opposite of the intended correction. The factor is now `max(IS) / IS(sample)`, so samples with reduced injection efficiency (or matrix suppression) are scaled *up* to the reference injection level. The sample carrying the maximum IS still keeps factor = 1; samples with no detectable IS are still flagged and left unnormalized.

### Action Required
- Any prior reanalysis that used IS normalization was directionally incorrect. Re-run those analyses with v3.0.7+ before publishing or interpreting them.

---

## [3.0.6] - 2026-04-29

### Added
- **Feature Detection Summary** (CSV + PDF): every observed feature with detection frequency (% of true samples with abundance > 0), per-sample abundances, and BFF pass/fail. Blanks are excluded from the frequency statistic but their abundances are still echoed for QA in the CSV.
- **Match Summary** (CSV + PDF): every library match keyed back to its feature, with RevDot/FwdDot/RHRMF and RI deltas. One row per (feature, candidate) pair.
- **Landscape PDF front pages**: both summary tables are rendered as the first pages of the report, in landscape orientation, before the per-match detail pages.
- **`blank_columns` parameter** added to `ReportGenerator` so the summary tables can compute detection frequency over true samples only (`engine.parser.blank_columns` is now passed in from the CLI).

### Fixed
- **GUI Results screen showing all "Unknown"**: The Results-screen CSV picker globbed `*.csv` and took `[0]`, which after v3.0.6 could pick `*_feature_summary.csv` (1866 rows, no `Compound_Name` column) instead of `*_matches_*.csv`. Now the picker explicitly prefers the matches file and ignores summary files.
- **PDF feature summary unreadable on real-sized studies**: With ~1800 features × ~150 samples, the per-sample abundance grid compressed into hairline columns or fanned out into hundreds of horizontally-chunked pages. The PDF now shows the stat overview only (Feat #, RT, RI, Det %, Det N, Tot N, Mean Abd, Max Abd, BFF) — the full per-sample grid lives in the companion CSV, where spreadsheet column widening makes it usable.
- **`generate_pdf` return value**: the method now returns the saved file path (it previously returned `None`, causing the CLI to print `[OK] PDF saved: None`).
- **PDF orientation restoration**: `render_summary_pdf_pages` now restores portrait orientation via a `finally` block, so a partial failure mid-render can no longer leave the canvas stuck in landscape and corrupt the per-match pages.
- **Summary table header overlap**: PDF column headers were drawn over each other when verbose names exceeded the column width. Replaced with abbreviated display headers and proportional column widths sized for content. CSV headers remain fully descriptive.

### Files
- New: `scripts/src/summary_tables.py` (table-building, CSV writing, PDF rendering)

---

## [3.0.5] - 2026-04-29

### Added
- **`--bff-c-factor` flag** (CLI, pipeline wrapper, GUI): the multiplier in front of the BFF threshold rule is now user-configurable. Applies to both `standard` and `adjusted` modes, so the two stay on the same scale. Validated as a positive number at every boundary; default remains `5.0` to preserve existing outputs.
- **GUI control**: numeric entry for the c-factor on the Analysis Parameters screen, alongside the existing BFF mode radio buttons. Invalid (non-numeric, ≤ 0) values are rejected with a dialog before the user can advance.
- **`BFF_CFactor` audit column** in the per-match CSV: records the multiplier used for each row alongside the existing BFF_Mode/BFF_Rule audit fields.

### Why This Change
- The legacy 5× multiplier on `(mean + 3·SD)` is conservative for some sample sets. Allowing the user to choose 1×, 2×, etc. relaxes the filter when blanks are clean enough that 5× masks real low-magnitude signals — without removing the legacy default.

### Backward Compatibility
- Default `bff_c_factor` is `5.0`; existing analyses produce byte-identical thresholds. Audit column is appended without disturbing existing column order.

---

## [3.0.4] - 2026-04-28

### Added
- **Adjusted BFF Mode**: New `bff_mode={standard,adjusted}` option for Blank Feature Filtering. Standard mode preserves existing `c_factor * (mean + 3*SD)` behavior unchanged. Adjusted mode runs a per-feature Shapiro-Wilk normality test (alpha=0.05) on the field blanks and selects between `mean + 3*SD` (normal blanks) and `median + 3 * 1.4826 * MAD` (non-normal). The 1.4826 scaling makes MAD a consistent estimator of sigma under normality, so adjusted mode reduces to the standard rule when blanks truly are normal — but is robust to sparse high-magnitude blank detections that would otherwise inflate the SD enough to mask real sample signal.
- **BFF Fallback Rules** (adjusted mode): When MAD = 0 but at least one blank is nonzero, threshold falls back to `max(blanks)`. When all blanks are zero, threshold is 0. Features whose blanks are all identical (zero variance, Shapiro can't run) are routed through these fallbacks as non-normal.
- **CLI / Pipeline Flag**: `--bff-mode {standard,adjusted}` added to both `cli.py` and `gcms_pipeline.py` (default: `standard`).
- **GUI Control**: Radio-button selector for BFF mode on the Analysis Parameters screen.
- **CSV Audit Columns**: Matches CSV now records `BFF_Mode`, `BFF_Rule`, `BFF_Shapiro_P`, and `BFF_Normal` per feature for downstream auditing. Existing `BFF_Threshold` column is unchanged.
- **`reset_to_defaults()` helper** in `K2Config` for scrubbing stale paths and secrets from a previous install.

### Changed
- **Saved-Config Path Validation**: On every load of `~/.k2/k2_defaults.json` (and on `load_preset`), path-type keys (`msconvert_path`, `mzmine_path`, `mzmine_user_file`, `mzmine_batch_file`, `library_path`, `ri_cal_path`) are checked against the filesystem and cleared if the target no longer exists. Prevents stale absolute paths from a previous install location from re-populating the GUI.
- **Preset Export Hygiene**: `export_preset()` now strips sensitive and per-machine keys (`epa_api_key`, `last_input_folder`, `last_output_folder`, `window_geometry`) before writing, so a `.K2config` preset can be shared with collaborators without leaking API keys or environment-specific state.

### Why This Change
- The old universal `mean + 3*SD` rule assumes normally distributed blanks. In practice, sparse high-magnitude detections in otherwise-clean field blanks inflate the SD enough that the threshold exceeds legitimate sample signal, filtering out real detections. Adjusted mode preserves the strict rule where blanks really are normal but switches to a MAD-based robust estimator otherwise.
- Saved configs frequently outlive their install location (repo moved, OneDrive synced to a new machine, software dir reinstalled). Path validation at load time keeps the GUI in a clean, browseable state instead of silently retaining dead absolute paths.

### Backward Compatibility
- Default `bff_mode` is `standard`; existing analyses produce byte-identical thresholds. Audit columns are appended to the CSV without disturbing existing column order.

---

## [3.0.3] - 2026-01-31

### Fixed
- **Default Configuration Paths**: Removed developer-specific paths from distribution. New users now see blank fields for library and RI calibration paths on first launch
- **Distribution Structure**: Documentation files (README, USER_GUIDE, QUICK_START) and templates folder now appear at top level alongside K2.exe instead of buried in _internal subfolder
- **User-Specific Files**: Removed user-specific .K2 project files and .K2config presets from templates folder

### Changed
- **GitHub Distribution**: Repository now configured for downloadable ZIP releases instead of requiring git clone
- **.gitignore**: Updated to exclude user config directory (.k2/) and .K2config preset files with personal paths
- **Build Script**: Enhanced create_distribution.bat to automatically restructure distribution after PyInstaller build

### Improved
- **First-Run Experience**: Clean slate for new users with no pre-populated file paths
- **Documentation Accessibility**: Key documentation files immediately visible when opening distribution folder
- **Release Workflow**: Simplified process for downloading and using K2 from GitHub releases

---

## [3.0.2] - 2026-01-25

### Changed
- **Structure Lookup Safety Improvement**: Removed compound name fallback in `get_structure_image()`
  - Structures are now fetched exclusively using InChIKey identifiers
  - If InChIKey is missing or invalid, "Structure Not Available" is displayed instead of potentially incorrect structure
  - Prevents ambiguous name searches from returning wrong chemical structures

### Why This Change
- Name-based PubChem searches can match similar compounds or derivatives
- Some library entries may have missing InChIKey values - better to show no structure than wrong structure
- Ensures displayed structures match the specific compound identified by the library entry

---

## [3.0.1] - 2026-01-25

### Fixed
- **Multiple Library Entries for Same Compound**: When the same compound (e.g., phenanthrene) appears multiple times in the library from different sources, each entry now generates its own unique spectral mirror plot in both PDF and GUI displays

### Added
- `library_index` attribute to `LibraryCompound` - unique identifier assigned to each library entry during loading
- `Library_Entry_ID` column in CSV output for tracking specific library entries
- Plot filenames now use `plot_{feat_id}_lib{library_index}.png` format for guaranteed uniqueness

### Changed
- **library_parser.py**: `LibraryCompound` class now includes `library_index` parameter; indices assigned after RI-sorting
- **reporter.py**: CSV headers include `Library_Entry_ID`; plot filenames use library index
- **k2_screens.py**: `update_visuals()` prioritizes library index format for finding plots, with fallback to legacy formats for backward compatibility

### Backward Compatibility
- Existing CSV files without `Library_Entry_ID` column continue to work (GUI falls back to older filename patterns)
- Library files require no changes (index is assigned dynamically during loading)

---

## [3.0.0] - 2026-01-28

### Major Feature: Surrogate Standard Recovery Analysis

This release introduces comprehensive surrogate standard recovery calculation, enabling users to track and quantify labeled (13C/deuterated) surrogate standards spiked into samples.

### New Files
- `scripts/src/surrogate_analyzer.py` - Core surrogate matching and recovery calculation
- `scripts/src/surrogate_reporter.py` - CSV, PDF, and GUI output generation

### New GUI Screens
- **SurrogateConfigScreen**: Configure surrogate standard recovery analysis
  - Enable/disable surrogate recovery calculation
  - Upload custom surrogate standard library (CSV/MSP)
  - Select/deselect specific compounds from the library

### Extended Sample Classification Screen
- New sample type: "Reference" (auto-detected by "ref" in filename)
- "Spiked" checkbox column for marking samples with surrogate spikes
- "Spike Ratio" column for relative spike amounts
- "Group" column for organizing samples by experimental groups
- Reference samples are automatically excluded from suspect screening

### New Results Tab
- "Surrogate Recovery" tab in ResultsScreen
- Recovery summary table with average, standard deviation, and per-sample values
- Match details for each surrogate compound
- Export functionality for surrogate data

### CLI Extensions
- `--surrogate-library` / `-sl`: Path to surrogate standard library
- `--surrogate-config`: JSON file with surrogate configuration
- `--reference-samples`: Comma-separated list of reference sample names

### Matching Engine Updates
- `reference_samples` parameter to exclude samples from BFF calculation
- Reference samples are excluded from suspect screening workflow
- Surrogate matching uses same criteria (RI, spectral scores, RHRMF) but skips BFF filter

### Recovery Calculation
- Formula: `% Recovery = (sample_abundance / sample_ratio) / avg(reference_abundances / reference_ratios) * 100`
- Group-based calculations allow different reference sets per experimental group
- IS normalization applied before recovery calculation if enabled

### Output Formats
- Separate CSV file: `SurrogateRecoveries_{ProjectName}_{date}.csv`
  - Normalized abundances table
  - % Recovery table with statistics
  - Match information table
- New page in PDF report
- Dedicated GUI tab with color-coded recovery values

---

## [2.9.1] - 2026-01-26

### Reverted
- Removed enhanced ToxValDB columns from CSV (data not available for most compounds)
- Removed severity index, NOAEL, genetox display from GUI

### Retained
- `ctx-python` package remains installed for future use
- `scripts/src/ctx_client.py` kept for potential future integration
- `Hazard_Summary` and `EPA_Link` columns continue to work as in v2.8.0

### Note
The ToxValDB data via ctx-python was not sufficiently populated for the compounds of interest.
CSV now shows only the GHS hazard category and EPA CompTox link.

---

## [2.9.0] - 2026-01-26

### Added
- **Enhanced Hazard Data Integration**: New integration with EPA CompTox via official `ctx-python` package
  - Quantitative toxicity values from ToxValDB (NOAEL, LOAEL, POD, RfD)
  - Ecological toxicity data (LC50, LD50)
  - Genetic toxicity summary (Ames test, positive/negative report counts)
  - Computed Severity Index (1-5 scale based on toxicity thresholds)

### New CSV Columns (removed in 2.9.1)
- `Tox_NOAEL` - Most protective No Observable Adverse Effect Level (mg/kg-day)
- `Tox_LOAEL` - Lowest Observable Adverse Effect Level (mg/kg-day)
- `Tox_POD` - Point of Departure (mg/kg-day)
- `Tox_RfD` - EPA Reference Dose (mg/kg-day)
- `Tox_Source` - Source of toxicity data (e.g., EPA IRIS, ATSDR)
- `Eco_LC50` - Fish LC50 (mg/L)
- `Eco_LD50` - Oral LD50 (mg/kg)
- `Genetox_Positive` - Count of positive genotoxicity reports
- `Genetox_Negative` - Count of negative genotoxicity reports
- `Genetox_Ames` - Ames test result (positive/negative)
- `Severity_Index` - Computed severity score (1-5)

### New Files
- `scripts/src/ctx_client.py` - EPA CompTox API client using ctx-python package

### Updated
- `scripts/src/structure_helper.py` - Added `get_enhanced_hazard()` method
- `scripts/src/reporter.py` - Added 11 new CSV columns for enhanced hazard data
- `scripts/k2_screens.py` - GUI now displays severity index and key toxicity values
- `requirements.txt` - Added ctx-python dependency

### Dependencies
- Added: `ctx-python>=0.1.0` for EPA CompTox API access

---

## [2.8.0] - 2026-01

### Added
- Internal Standard (IS) normalization integration in Sample Classification screen
- IS area and normalization factor columns in CSV reports
- IS area and normalization factor display in GUI sample table

### Fixed
- Spectral plot display in GUI (now generated during CSV export)
- IS Area showing as "0" in GUI
- Hazard summary and EPA link data consistency between CSV and PDF
- Multiple matches for same feature ID now show correct individual structures/plots

### Removed
- Log2FoldChange and P-value from GUI (deprecated statistics package)
- IS normalization info from PDF reports (CSV only)

---

## [2.7.0] - 2026

### Added
- Structure image helper module separated from statistics visualization
- High-resolution structure images from PubChem
- Hazard matrix visualization in PDF reports with color-coded badges

### Changed
- Replaced Visualizer with StructureHelper for cleaner architecture
- Statistics module deprecated (external analysis recommended)

---

## [2.6.0] - 2026

### Added
- MZmine integration for feature detection
- Universal parser supporting both MS-DIAL and MZmine formats
- Improved BFF (Blank Feature Filtering) calculations

---

## Previous Versions

See archived code in `scripts/archive/` for historical changes.
