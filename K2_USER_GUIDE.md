# K2 Annotator User Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Installation](#installation)
3. [First-Time Setup](#first-time-setup)
4. [Using K2](#using-k2)
5. [File Formats](#file-formats)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Features](#advanced-features)

---

## Introduction

K2 is a comprehensive GUI application for GC-MS non-target analysis. It wraps a complete pipeline including:
- Raw data conversion (vendor raw → .mzML)
- Feature detection and deconvolution (MZmine)
- Spectral library matching
- Retention index calibration
- Automated reporting (CSV and PDF)

### System Requirements
- Windows 10 or higher
- Python 3.8+ (included in distribution)
- 8GB RAM minimum (16GB recommended)
- 10GB free disk space

---

## Installation

### Quick Start
1. Extract the K2 package to your desired location (e.g., `C:\K2\`)
2. Double-click `K2.bat` to launch the application
3. The virtual environment will activate automatically

### Manual Installation
If you need to set up from source:

```bash
# Navigate to K2 directory
cd path\to\gcms_pipeline

# Activate virtual environment
.venv\Scripts\activate

# Verify dependencies
pip list

# Launch GUI
python scripts\k2_gui.py
```

---

## First-Time Setup

K2 requires external software for certain pipeline stages. You only need to set these up once.

### 1. MSConvert (Required for raw instrument data conversion)

**What is it?**
MSConvert converts vendor instrument files (Agilent `.D`, Bruker `.d`, Thermo `.raw`, Sciex `.wiff`, Waters `.raw`, Shimadzu `.lcd`, etc.) to the open mzML format.

> ⚠️ K2 Annotator has been tested against Agilent `.D` folders. Other vendor formats are passed through to MSConvert's native readers and are accepted on a best-effort basis.

**Where to get it:**
Download ProteoWizard from: http://proteowizard.sourceforge.net/

**Installation:**
1. Download the Windows installer
2. Install to default location (e.g., `C:\Program Files\ProteoWizard`)
3. Note the path to `msconvert.exe`

**Typical location:**
`C:\Program Files\ProteoWizard\msconvert.exe`

or in the included software folder:
`<K2_DIR>\software\pwiz-bin\msconvert.exe`

---

### 2. MZmine (Required for feature detection)

**What is it?**
MZmine performs mass spectral feature detection and deconvolution.

**Where to get it:**
Download from: https://github.com/mzmine/mzmine/releases

**Installation:**
1. Download the Windows installer (version 3.x or higher)
2. Install to your preferred location
3. Note the path to `mzmine_console.exe`

**Important Files:**
- **mzmine_console.exe**: Located in the MZmine installation directory
- **User File (.mzuser)**: Template provided in `<K2_DIR>\users\default.mzuser`
- **Batch File (.mzbatch)**: Example provided in `<K2_DIR>\config\gc_ei_workflow.mzbatch`

**Creating Your Own Configuration:**
1. Open MZmine GUI
2. Configure your preferred workflow (import → detection → deconvolution)
3. Export as batch file (.mzbatch)
4. Save user preferences as .mzuser

---

### 3. Spectral Library (Required)

**Format:** CSV or MSP
**Templates:** `templates/library_template.csv` and `templates/library_template.msp`

K2 Annotator does not bundle a production spectral library, so you must supply your own (e.g. an export of NIST/Wiley, MassBank, or an in-house library). See `templates/library_template.{csv,msp}` for the expected schema and `templates/TEST_DATA_README.md` for a tiny test library used by the validation harness.

**CSV Format Requirements:**
- Must have columns: `name`, `formula`, `ri`, `peaks_json`
- `peaks_json`: JSON array of [m/z, intensity] pairs
- Example:
```csv
name,formula,ri,peaks_json,cas,inchikey
Acetone,C3H6O,586.5,"[[43,999],[58,359],[42,20]]",67-64-1,CSCPPACGZO FKC-UHFFFAOYSA-N
```

**MSP Format Requirements:**

K2 fully supports MSP (Mass Spectral Peak) format for spectral libraries. This is the standard format used by NIST, MassBank, and other spectral databases.

**Required Fields:**
- `NAME:` or `COMPOUND NAME:` - Compound name
- `RI:` or `RETENTIONINDEX:` or `RETENTION INDEX:` or `KOVATS:` - Retention index value
- `NUM PEAKS:` - Number of spectral peaks
- Peak list: m/z intensity pairs (one per line)

**Recommended Fields:**
- `FORMULA:` or `MOLECULAR FORMULA:` - Molecular formula

**Optional Metadata Fields (become searchable metadata):**
- `CAS:` - CAS registry number
- `INCHIKEY:` - InChI Key identifier
- `MW:` - Molecular weight
- `SOURCE:` - Data source (e.g., NIST, Custom, EPA)
- `INSTRUMENT:` - Instrument type (e.g., GC-EI-MS, GC-EI-Orbitrap)
- `COMMENTS:` - Additional notes
- Any other fields you want to track

**Format Notes:**
- Field names are **case-insensitive**
- Fields use colon `:` separator
- Peak list starts after `NUM PEAKS:` line
- Compounds separated by blank lines
- m/z and intensity are space-separated
- Intensity typically normalized to 999 for base peak

**Example MSP Entry:**
```
NAME: Benzene
RI: 652
RETENTIONINDEX: 652
FORMULA: C6H6
CAS: 71-43-2
INCHIKEY: UHOVQNZJYSORNB-UHFFFAOYSA-N
MW: 78
SOURCE: EPA CompTox
INSTRUMENT: GC-EI-QQQ
TOXICITY: Carcinogenic
COMMENTS: Aromatic hydrocarbon, priority pollutant
NUM PEAKS: 9
39 89
50 156
51 234
52 567
74 67
75 45
76 34
77 345
78 999

```

**Template File:**
A complete MSP library template is available at: `templates/library_template.msp`

This file contains three example compounds demonstrating all required and recommended fields.

---

### 4. RI Calibration File (Required for MZmine data)

**Format:** two columns (carbon number, retention time in minutes), tab, comma,
semicolon or space separated, header optional. Example:
`templates/ri_calibration_template.txt`.

```
Carbon number    RT(min)
9    12.482
10   15.252
11   18.289
...
```

**Purpose:** converts retention time to retention index (RI = 100 × carbon
number, cubic-spline interpolation). RI agreement is a mandatory Level-2
criterion, so K2 refuses to run MZmine data without a calibration file.

Features that elute before the first or after the last alkane receive an
extrapolated RI and are flagged `RI_Extrapolated = Yes` in every output table,
and a warning with the count is printed at load. Extrapolated RIs are not
reliable far from the alkane range, so the alkane series should span all
features of interest. The `--ri-extrapolation linear` option switches from
cubic-spline to linear (van den Dool) extrapolation outside the range and does
not change RIs inside it.

Duplicate carbon numbers, non-increasing retention times and fewer than three
alkanes are rejected with an explicit message.

---

### 5. EPA CompTox API Key (Optional)

**What is it?**
Enables automatic toxicity data retrieval for identified compounds.

**How to get it:**
1. Visit: https://comptox.epa.gov/dashboard/web-services
2. Register for a free API key
3. Copy your key and paste it in K2

---

## Using K2

### Starting a New Analysis

1. **Launch K2**
   - Double-click `K2.bat` or run `python scripts\k2_gui.py`

2. **Welcome Screen**
   - Choose "Start New Analysis"
   - Or load an existing project (.K2 file)
   - Or load a preset configuration (.K2config file)

3. **Select Entry Point**
   Choose where to start in the pipeline:
   - **Raw Instrument Data**: Full pipeline from vendor raw files
     (Agilent `.D`, Bruker `.d`, Thermo `.raw`, Sciex `.wiff`,
     Shimadzu `.lcd`, etc., that is, anything MSConvert can read).
     Tested with Agilent `.D` folders; other vendor formats are
     accepted on a best-effort basis.
   - **Instrument Files (.mzML)**: Skip conversion, start with MZmine
   - **Deconvoluted Spectra (.MSP)**: Skip to library matching only

4. **Project Setup**
   - **Input Folder**: Select folder containing your files
   - **Project Name**: Give your analysis a name (auto-filled from folder)
   - **Output Folder**: Where to save results

5. **Configure Tools** (depending on entry point)

   **If starting from raw instrument data:**
   - Locate `msconvert.exe`
   - Check "Save as default" to remember for next time

   **If processing with MZmine:**
   - Locate `mzmine_console.exe`
   - Select your user file (.mzuser)
   - Select your batch file (.mzbatch)
   - Set thread count (2-4 recommended)
   - Check "Save as default"

6. **Analysis Parameters**
   - **Library**: Select your spectral library (.CSV or .MSP)
   - **RI Calibration**: Optional, but recommended
   - **EPA API Key**: Optional, for toxicity data
   - **Blank Identifier**: String to identify blank samples (e.g., "fieldblank", "blank", "control")

7. **Save Configuration** (Optional)
   - Click "Save Current Configuration as Preset"
   - Creates a .K2config file for reuse

8. **Run Analysis**
   - Click "Run Analysis"
   - Monitor progress in the console window
   - Analysis may take 10 minutes to several hours depending on data size

9. **View Results**
   - Interactive results viewer appears automatically
   - Browse matches in left panel
   - View details in right panel tabs:
     - **Overview**: Key match information
     - **Spectral Match**: Scoring details
     - **Metadata**: All additional data
   - Export buttons open CSV and PDF reports

---

### Loading an Existing Project

**From Welcome Screen:**
- Click "Load Existing Project (.K2)"
- Browse to your .K2 file
- Project configuration and status restored

**From Menu:**
- File → Open Project (Ctrl+O)

**Completed Projects:**
- Automatically opens results viewer
- Can re-run analysis if needed

---

### Using Configuration Presets

**Save a Preset:**
1. Configure all your settings
2. In Analysis Parameters screen, click "Save Current Configuration as Preset"
3. Or use File → Save Preset
4. Saves paths, parameters, thread counts, etc.

**Load a Preset:**
1. From Welcome screen, click "Load Preset Configuration"
2. Or use File → Load Preset
3. All settings applied automatically
4. You can still modify individual settings before running

**What's Saved in Presets:**
- All tool paths (msconvert, mzmine, etc.)
- Library and RI calibration paths
- API keys
- Thread counts
- Blank identifiers
- Other analysis parameters

**What's NOT Saved:**
- Project name
- Input/output folder locations
- Analysis results

---

## File Formats

### .K2 (Project Files)

**Purpose:** Save complete analysis sessions
**Contains:**
- Project metadata (name, dates)
- All configuration settings
- Input/output paths
- Analysis status
- Results file locations

**Usage:**
- Save: File → Save Project (Ctrl+S)
- Load: File → Open Project (Ctrl+O)
- Allows resuming or re-running analyses

**Format:** JSON

---

### .K2config (Configuration Presets)

**Purpose:** Save and share tool configurations
**Contains:**
- Tool paths
- Analysis parameters
- Default settings

**Does NOT contain:**
- Project-specific data
- File paths that change between projects

**Usage:**
- Create templates for different analysis types
- Share configurations with colleagues
- Quickly switch between instrument setups

**Format:** JSON

---

### Output Files

K2 generates results in:
`<PIPELINE_ROOT>/results/<PROJECT_NAME>/`

**Files created:**
- `<PROJECT>_matches_<DATE>.csv`: one row per (feature, library candidate) that passed every Level-2 criterion
- `<PROJECT>_<DATE>_feature_summary.csv`: every feature with detection frequency, abundances, `Passed_BFF`, `RI_Extrapolated`
- `<PROJECT>_<DATE>_match_summary.csv`: compact per-match score table
- `<PROJECT>_report_<DATE>.pdf`: summary tables plus one page per match with mirror plot and hazard badges
- `run_manifest.json`: K2 and package versions, the SHA-256 hash of every input file, all resolved options (including `max_lib_peaks` and the RI extrapolation mode), the sample classification, library statistics, calibration range, feature and match counts, and the availability of the external hazard services. It should be kept with the results.
- `pipeline_log.txt` and `mzmine_log.txt` (GUI / pipeline runs)

**Key CSV columns:** `Feature ID`, `RT`, `RI_Exp`, `RI_Extrapolated`, `RI_Lib`, `RI_Err`, `RI_Err%`,
`Compound_Name`, `Formula`, `HighRes?`, `RHRMF` (`N/A` for exact-mass library entries), `HR_RevDot`/`HR_FwdDot`
(10 ppm peak-paired scores, exact-mass entries only), `RevDot`, `FwdDot`, `MaxAbundance`, `BFF_Threshold`,
BFF audit columns, IS columns, metadata (`CAS`, `InChIKey`, `Source`, `Instrument`, `Comments`), hazard
summary, and one `Abundance_<sample>` column per sample. Candidates for a feature are ordered by
descending reverse dot product (the first is the "best match").

---

## Troubleshooting

### Common Issues

**Problem:** "msconvert.exe not found"
**Solution:**
- Verify ProteoWizard is installed
- Check the path in MSConvert Configuration screen
- Try browsing to the file manually
- Ensure you have the correct version (3.0+)

---

**Problem:** "MZmine processing failed"
**Solution:**
- Check MZmine logs in console output
- Verify input files are valid .mzML
- Ensure user file (.mzuser) matches your MZmine version
- Try reducing thread count
- Check available memory (MZmine is memory-intensive)

---

**Problem:** "No matches found"
**Solution:**
- Verify library file contains compounds with RI values
- Check blank identifier matches your sample names
- Ensure spectral quality is sufficient
- Review RI calibration (if used)
- Lower matching thresholds in library matching code

---

**Problem:** "Library file invalid"
**Solution:**
- **For CSV:** Verify required columns exist (name, formula, ri, peaks_json)
- **For MSP:** Ensure NAME, RI, and NUM PEAKS fields are present
- Check file encoding (should be UTF-8)
- Validate JSON format in peaks_json column (CSV only)

---

**Problem:** GUI won't launch
**Solution:**
- Verify Python installation: `python --version`
- Check virtual environment: `.venv\Scripts\activate`
- Test dependencies: `pip list | grep tk`
- Try launching directly: `python scripts\k2_gui.py`
- Check for error messages in console

---

**Problem:** Analysis cancelled/interrupted
**Solution:**
- Check console output for specific errors
- Verify all input files are accessible
- Ensure output directory is writable
- Check disk space availability
- Review pipeline log files

---

**Problem:** `[WinError 362] The cloud file provider is not running` during conversion or MZmine launch
**Cause:** The `software/` folder (containing MSConvert and/or MZmine) is being kept in OneDrive (or another cloud provider) and the binaries are *cloud-only placeholders*, they look like real files but their contents are not on disk. When the pipeline tries to launch them, Windows asks the cloud client to hydrate them and fails because the client isn't running.
**Solution (pick one):**
- Start OneDrive (Start menu → OneDrive) so it can fetch the files on demand. Re-run the pipeline.
- In File Explorer, right-click the `software/` folder and choose **"Always keep on this device"**. Wait for the green-check icon, then re-run.
- Or move the `software/` folder out of any cloud-synced location entirely (e.g. to `C:\K2\software\`) and update the configured paths in the GUI.

K2 Annotator now also catches this case at startup and refuses to run with an actionable error, so you should not see the raw `WinError 362` if you re-run after pulling the latest version.

---

**Problem:** MZmine fails at the import stage with `java.lang.InternalError: a fault occurred in an unsafe memory access operation` (typically citing `MemoryMapStorage.java`)
**Cause:** MZmine uses Java NIO memory-mapped files for scratch storage during mzML import. The crash happens when MZmine's mapped pages are pulled out from under the JVM mid-read. On Windows there are three common reasons for that:

1. **Scratch on a cloud-synced path.** OneDrive / Dropbox filter drivers intercept page-level reads and the JVM faults. From v3.0.15 onward K2 Annotator creates MZmine's scratch under `%TEMP%\k2_mzmine_*` automatically, you should see that path near the top of the MZmine stage. If you ever pass `--mzmine-temp` explicitly, do *not* point it at a OneDrive/Dropbox folder.
2. **Parallel import threads racing on the same rotating scratch file.** When MZmine's `mzmine.tmp` fills up it gets rotated; a concurrent import thread's mmap of the previous file becomes invalid mid-write and the JVM faults inside `Unsafe`. From v3.0.16 onward K2 Annotator serialises the mzML import phase to a single thread by default. The overall `--threads` value is still used for the post-import stages. You can raise the import cap with `--mzmine-import-threads N` if your `mzmine.tmp` rotation doesn't trip on your dataset.
3. **Antivirus real-time scanning.** Defender / corporate AV products see `mzmine.tmp` being written and grab a read handle for scanning; the JVM's mapped view then disappears or stalls. Exclude the scratch directory (or the whole `%TEMP%` tree) from real-time scanning. This is the single most common cause we see in the wild.

**Other knobs:**
- `--mzmine-memory {none,all,features,centroids,raw,masses_features}`, forwarded to MZmine 4.x's `-memory` flag (uses MZmine's `KeepInMemory` enum). Default is `none`, which matches MZmine's own fallback (everything in JVM heap). `all` memory-maps everything to disk for the lowest heap pressure (best on machines with a small Windows page file). `masses_features` maps the mass-list and feature layers but keeps raw scans in heap. `features` / `centroids` / `raw` map only the named layer. **Note:** earlier versions of this guide listed `{none,mass,all}`, but `mass` is not a valid `KeepInMemory` value in MZmine 4.x, passing it triggers a non-fatal WARNING in the MZmine log followed by a silent exit-1 a few steps later. If you see `Issue while reading keep in memory option from CLI argument` in the log and the pipeline aborts right after, you are running an old K2 that passes the now-invalid `mass` value.

---

**Problem:** MZmine fails mid-import with `OpenJDK 64-Bit Server VM warning: INFO: os::commit_memory(...) failed; error='The paging file is too small for this operation to complete' (DOS error/errno=1455)` and `There is insufficient memory for the Java Runtime Environment to continue`.
**Cause:** Windows error 1455 (`ERROR_COMMITMENT_LIMIT`) means the JVM tried to commit more virtual memory than your machine has available across RAM + page file. The JVM heap is set proportional to system RAM by MZmine's launcher, so on a machine where the Windows page file is small or fixed-size, the JVM can fail to expand its heap mid-run. **This is a Windows configuration issue, not an MZmine bug.**
**Solution (do this first):** Let Windows manage the page file dynamically.
1. Press **Win + R**, type `sysdm.cpl`, press Enter.
2. Advanced tab → Performance → **Settings**.
3. Advanced tab → Virtual memory → **Change**.
4. Tick **"Automatically manage paging file size for all drives"**.
5. Click **OK**, restart Windows when prompted.

**Fallback (if you can't change the page file):** Run with `--mzmine-memory all` (memory-map everything to disk, lowest heap pressure) or `--mzmine-memory masses_features` (map mass lists + features, keep raw scans in heap). The default `none` keeps everything in heap, fine on machines with plenty of RAM + a healthy page file, but the first thing to change if you hit `paging file is too small`. If switching still fails, you can edit `mzmine.vmoptions` in your MZmine install folder and set a smaller heap, e.g. `-Xmx2g`. The pipeline does not control MZmine's heap size directly.
- If MZmine still fails on this dataset after the above, copy the **`MZmine command: ...`** line printed by the pipeline and run it manually in a terminal. If it fails there too, the issue is in MZmine's environment, not K2 Annotator.

---

**Problem:** MSConvert appears stuck for hours during the "writing to mzML" stage
**Cause:** Your output folder is on a network share (Z:, an SMB mount, a VPN-mounted volume, etc.). MSConvert writes the `.mzML` output incrementally with frequent fsyncs; doing that against a high-latency network filesystem can stretch a minute of conversion into many hours of wall time, because each write round-trips over the network.
**Solution:** From v3.0.13 onward K2 Annotator stages each conversion through a fast local temp directory (default `%TEMP%\k2_msconvert_*`) and copies the finished `.mzML` to the requested output folder in one shot. This is on by default, you should see a `Staging directory:` line at the top of the conversion stage. If you ever want to skip the staging step (e.g. because your output is already on a fast local SSD and you want to avoid the extra copy), pass `--no-stage-locally` to `gcms_pipeline.py`.

If staging is enabled and conversion is *still* slow, the bottleneck is now on the **read** side, MSConvert reading the raw `.D` folder from the network share. The simplest remedy is to copy the raw folder(s) to a local drive first and run the pipeline against that local copy.

---

### Error messages introduced in v3.1.0

| Message | Cause | Fix |
|---|---|---|
| `MZmine input has retention times only; an alkane RI calibration file (--ri-cal) is required` | No calibration file for MZmine data | Provide the alkane table (see First-Time Setup §4) |
| `No blank columns were identified ...` | `--blank-id` / grouping matched nothing | Correct the identifier or classify blanks in the GUI table; `--allow-no-blanks` only if you really have none |
| `No sample columns remain after classification` | Every column matched the blank identifier | Use a more specific identifier or the grouping table |
| `sample classification names not found among the quantification columns` | Names in the grouping do not match the quant headers | Names are compared after stripping extensions and `Peak area`; check spelling |
| `No quantification columns found in the MZmine CSV` | Export lacks `Peak area` / `Peak height` / `datafile:...:area` columns | Re-export the aligned feature list with areas |
| `'row ID' is not an integer` | Wrong file passed as the quant table | Check the file |
| `Library ... yielded no usable entries` | No entry had both an RI and a peak list | Check the RI field spelling and the peak-line format (see templates/TEST_DATA_README.md) |
| `[OK] Analysis complete - NO Level 2 matches.` (exit code 2) | The run completed and no candidate passed | Check `Passed_BFF` and `RI_Extrapolated` in `*_feature_summary.csv`, and the per-candidate trace written when `K2_DIAG_MATCHING_CSV` is set |
| `[API] pubchem.ncbi.nlm.nih.gov is not responding ... Skipping all further requests` | The hazard service timed out or refused the connection | Nothing to do; the run continues to the report and the remaining compounds read `Skipped (API unavailable)`. Use `--no-hazard` to skip the lookups from the start, or set `K2_API_FAILURE_LIMIT` to allow more failures before giving up |
| `N of M features elute outside the alkane calibration range` | Alkane series too short | Extend the alkane series; treat flagged RIs with caution |

### Getting Help

**Check Console Output:**
- Detailed error messages appear in the execution console
- Copy error messages for troubleshooting

**Verify File Paths:**
- Use File Explorer to confirm files exist
- Check for typos in manual path entry
- Use Browse buttons when possible

**Test Individual Components:**
- Run msconvert manually on one raw input file
- Test MZmine with a small dataset
- Validate library file format

---

## Advanced Features

### Keyboard Shortcuts
- `Ctrl+N`: New Project
- `Ctrl+O`: Open Project
- `Ctrl+S`: Save Project

### Menu Options
- **File Menu**: Project and preset management
- **Help Menu**: User guide and about information

### Batch Processing
To process multiple datasets:
1. Create a preset with your standard configuration
2. For each dataset:
   - Start new analysis
   - Load preset
   - Select input folder
   - Run analysis

### Custom MZmine Workflows
1. Open MZmine GUI
2. Design your workflow:
   - Mass detection parameters
   - Chromatogram building
   - Deconvolution settings
   - Alignment options
3. Save as .mzbatch file
4. Use in K2 MZmine Configuration

### Integration with Other Tools
- Export CSV results for downstream analysis
- Import results into R, Python, Excel
- Combine with multivariate statistics
- Use for suspect screening workflows

---

## Surrogate Standard Recovery Analysis (v3.0.0+)

Surrogate standard recovery analysis tracks labeled (13C, deuterated) surrogate compounds through your sample processing workflow to assess method performance and matrix effects.

### What Are Surrogate Standards?

Surrogate standards are isotope-labeled versions of target analytes (or chemically similar compounds) that are spiked into samples before extraction. Their recovery rate indicates:
- Extraction efficiency
- Matrix effects
- Sample processing losses

### Enabling Surrogate Recovery

1. **Surrogate Configuration Screen**
   - After Analysis Parameters, click Next to access the Surrogate Config screen
   - Check "Enable Surrogate Recovery Analysis"

2. **Upload Surrogate Library**
   - Click "Browse" to select your surrogate library file
   - Supports same formats as main library (CSV or MSP)
   - Library should contain only your surrogate standards

3. **Select Compounds**
   - Review detected compounds in the list
   - Check/uncheck individual surrogates to include in analysis
   - Use "Select All" / "Deselect All" for bulk operations

### Sample Classification for Surrogates

In the Sample Classification screen, additional options appear when surrogate analysis is enabled:

- **Reference**: Samples marked as Reference are used to calculate expected recovery
  - Auto-detected: Samples with "ref" in filename are automatically marked as Reference
  - Reference samples are excluded from main suspect screening

- **Spiked**: Check this box for samples that were spiked with surrogates
  - Typically all samples except blanks are spiked

- **Spike Ratio**: Enter the relative spike amount
  - 1.0 = standard spike level
  - 0.5 = half spike, 2.0 = double spike
  - Used to normalize recovery calculations

- **Group**: Assign samples to experimental groups
  - Recovery is calculated within each group
  - Useful for batch-specific reference samples

### Recovery Calculation

Recovery is calculated as:

```
% Recovery = (Normalized Sample Abundance / Spike Ratio) / 
             Average(Normalized Reference Abundances / Reference Spike Ratios) × 100
```

Where:
- Normalized abundance = IS-normalized abundance (if IS enabled) or raw abundance
- Calculations are performed per experimental group

### Viewing Results

**GUI Tab**: A "Surrogate Recovery" tab appears in the Results screen showing:
- Recovery summary table with average, standard deviation
- Per-sample recovery values
- Color-coded recovery indicators (green: 70-130%, yellow: 50-70%/130-150%, red: <50%/>150%)

**CSV Output**: Separate file `SurrogateRecoveries_<ProjectName>_<date>.csv` containing:
- Normalized abundances table
- Recovery percentages table
- Match information (scores, RI error, etc.)

**PDF Report**: Surrogate recovery pages appended to main report

### Best Practices

1. Include reference samples in each batch
2. Spike surrogates before extraction
3. Use spike ratios to account for concentration differences
4. Monitor recovery trends across batches
5. Investigate recoveries outside 70-130% range

---

## Enhanced Sample Classification (v3.0.0+)

The Sample Classification screen allows you to configure how each sample is treated in the analysis.

### Sample Types

- **Sample**: Standard analytical sample (default)
- **Blank**: Field blank, method blank, or control
- **Reference**: Reference sample for surrogate recovery (excluded from suspect screening)

### Additional Fields

**Spiked Checkbox**
- Check for samples spiked with surrogate standards
- Used for surrogate recovery calculations

**Spike Ratio**
- Relative spike concentration (default: 1.0)
- Adjust for diluted (0.5) or concentrated (2.0) spikes

**Group**
- Assign samples to experimental groups
- Groups allow batch-specific reference samples
- Click "Add Group" to create new groups

### Auto-Detection

- Samples containing "blank" (case-insensitive) are auto-classified as Blank
- Samples containing "ref" (case-insensitive) are auto-classified as Reference
- Reference samples are automatically marked as Spiked

### Bulk Operations

Right-click context menu provides:
- Set as Sample/Blank/Reference
- Mark as Spiked / Not Spiked
- Copy settings to selected rows

---

## Internal Standard Normalization (v2.8.0+)

Internal Standard (IS) normalization corrects for inter-sample variability in injection volume, ionization efficiency, and recovery.

### When to Use IS Normalization

- When you've added a known internal standard to all samples
- To correct for injection volume differences
- To improve quantitative accuracy
- For comparing absolute abundances across samples

### Configuration

In the Sample Classification screen, expand the "Internal Standard Normalization" section:

1. **Enable IS Normalization**: Check to activate
2. **Select Method**: Choose detection method

### Available Methods

**Manual Entry**
- Directly enter IS peak area for each sample
- Use when you have IS areas from external software
- Click on sample rows to enter values

**Auto m/z + RI/RT Detection**
- Automatically find IS feature by mass and retention
- Parameters:
  - Target m/z: Base peak m/z of your IS
  - m/z Tolerance: Search window (default: 0.5 Da)
  - Target RI or RT: Expected retention index or time
  - RI/RT Tolerance: Search window
  - Use RT instead of RI: Check if using retention time

**Auto MSP Spectrum Matching**
- Match IS by full spectrum comparison
- Upload MSP file containing IS spectrum
- Best spectral match is used as IS feature

### Understanding Results

After normalization, the following appear in your output:

**CSV Columns:**
- `IS_Normalized`: Yes/No - whether normalization was applied
- `IS_Method`: Which method was used
- `IS_Area_<sample>`: Detected IS area in each sample
- `IS_NormFactor_<sample>`: Normalization factor applied

**GUI Display:**
- IS Area and Norm Factor columns in Sample Data tab
- Abundances shown are already normalized

### Calculation

```
Normalization Factor = max(IS Area over samples) / Sample IS Area
Normalized Abundance = Raw Abundance × Normalization Factor
```

The sample with the largest IS response keeps factor 1; every other sample is
scaled *up*. Samples without an IS value keep factor 1 and are listed in a
warning. Normalisation is applied once, from the parsed abundances, however
many times a project is re-run in a session. Surrogate recoveries use the
normalised abundances directly (they are not scaled a second time).

### Best Practices

1. Add IS at consistent concentration to all samples
2. Choose an IS that doesn't interfere with analytes
3. Verify IS detection before running full analysis
4. Monitor IS areas for outliers (instrument issues)
5. Consider multiple IS for different compound classes

---

## Tips for Best Results

1. **Quality Control**
   - Include field blanks in every batch
   - Use consistent naming conventions
   - Document acquisition parameters

2. **Library Selection**
   - Use RI-indexed libraries when available
   - Prefer high-resolution libraries for QTOF data
   - Consider matrix-matched libraries

3. **Parameter Optimization**
   - Test different MZmine parameters on representative samples
   - Adjust spectral matching thresholds based on instrument type
   - Validate RI calibration with standards

4. **Data Management**
   - Use descriptive project names
   - Save projects frequently
   - Keep backup copies of configurations
   - Archive raw data and results together

---

## Citation
If you use K2 Annotator in your research, please cite:

Brunet, C. (2026). K2 Annotator: an open-source GC-MS suspect screening pipeline. DOI: 10.5281/zenodo.20149465


---

## Level 2 Matching Criteria (v3.1.x)

Each computation is described in [docs/SCORING_METHODS.md](docs/SCORING_METHODS.md) in a form suitable for a methods section. In brief, a candidate receives a Level 2 annotation only when it satisfies all of the following.

1. **Blank feature filter.** The maximum abundance of the feature in any non-reference sample must exceed `c × (mean_blank + 3·SD_blank)`, with c = 5 by default (`--bff-c-factor`). A run in which no blank column is identified is refused unless `--allow-no-blanks` is given. The `--bff-mode adjusted` option (a median and MAD based rule) is not part of the Koelmel et al. (2022) framework and is off by default.
2. **Retention index.** |ΔRI| must be at most 50 and at most 1.5% of the feature RI. RIs come from the alkane calibration, and extrapolated values are flagged.
3. **Spectral similarity.** The reverse dot product must exceed 600 and the forward dot product 500 (unit-mass bins, weights of √intensity × m/z, squared cosine scaled to 1000). The reverse dot product ignores feature peaks that are absent from the library entry. Library entries are trimmed to their 20 most intense peaks at load (`--max-lib-peaks`, recorded in the manifest).
4. **Exact-mass evidence.** For exact-mass library entries (identified by a metadata flag, or by at least two peaks with three or more decimal digits, one of them among the three most intense) the dot products are recomputed with 10 ppm peak pairing and must again exceed 600 and 500 (`HR_RevDot` and `HR_FwdDot`). For all other entries the RHRMF must exceed 75. The RHRMF follows Kwiecien et al. (2015): a ±10 ppm window about the measured cation m/z (electron mass subtracted), sub-formulas of the candidate formula, isotopologue variants for 13C, 37Cl, 81Br, 34S, and 30Si, and a total-ion-current weighted score. Labeled formulas (D, 13C) are supported.

Sample classification comes from the GUI table (`--grouping` on the command line). Samples typed as *Reference* are excluded from the blank-filter maximum and from the summary statistics.

---

## Version History

See [CHANGELOG.md](CHANGELOG.md) for the authoritative version history, including bug fixes and feature additions through the current release.

---

## Support

For bug reports, feature requests, or questions email: brunet.chris@gmail.com. I am not a professional software developer and make no garuntees about what I will be able to help with but will try my best to resolve issues
or address your needs from the software. 

---

**© 2026 K2 Annotator**
