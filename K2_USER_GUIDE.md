# K2 Annotator — User Guide

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
**Example:** `unified_library_20251013.csv` (included)

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

### 4. RI Calibration File (Optional)

**Format:** Tab-delimited text file
**Example:** `MSDial_RICal.txt` (included)

**Format:**
```
Carbon_Number    Retention_Time
9    5.123
10    6.456
11    7.789
...
```

**Purpose:**
Converts retention time to retention index for more accurate matching.

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
     Shimadzu `.lcd`, etc. — anything MSConvert can read).
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
- `<PROJECT>_matches_<DATE>.csv`: Tabular results
- `<PROJECT>_report_<DATE>.pdf`: Visual report with spectra

**CSV Columns include:**
- Feature_ID
- Compound_Name
- Formula
- Total_Score, Spectral_Score, RI_Score
- Library_RI, Observed_RI, RI_Delta
- All sample abundances
- Metadata fields

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
**Cause:** The `software/` folder (containing MSConvert and/or MZmine) is being kept in OneDrive (or another cloud provider) and the binaries are *cloud-only placeholders* — they look like real files but their contents are not on disk. When the pipeline tries to launch them, Windows asks the cloud client to hydrate them and fails because the client isn't running.
**Solution (pick one):**
- Start OneDrive (Start menu → OneDrive) so it can fetch the files on demand. Re-run the pipeline.
- In File Explorer, right-click the `software/` folder and choose **"Always keep on this device"**. Wait for the green-check icon, then re-run.
- Or move the `software/` folder out of any cloud-synced location entirely (e.g. to `C:\K2\software\`) and update the configured paths in the GUI.

K2 Annotator now also catches this case at startup and refuses to run with an actionable error, so you should not see the raw `WinError 362` if you re-run after pulling the latest version.

---

**Problem:** MZmine fails at the import stage with `java.lang.InternalError: a fault occurred in an unsafe memory access operation` (often citing `MemoryMapStorage.java`)
**Cause:** MZmine uses Java NIO memory-mapped files for its scratch storage (`mzmine.tmp`). When that scratch directory is on a cloud-synced filesystem (OneDrive, Dropbox), the cloud client's filter driver intercepts the page-level reads MZmine relies on, and Java's `Unsafe` throws `InternalError` when a previously-mapped page is no longer where Java expects it.
**Solution:** From v3.0.15 onward K2 Annotator creates MZmine's scratch directory under the system temp folder (`%TEMP%\k2_mzmine_*`) on every run, regardless of where the pipeline itself lives, and cleans it up afterward. You should see `MZmine scratch: C:\Users\<you>\AppData\Local\Temp\k2_mzmine_xxxx` near the top of the MZmine stage. If you ever need to override this (e.g. to put scratch on a faster SSD), pass `--mzmine-temp PATH` to `gcms_pipeline.py` — but never point it at a OneDrive/Dropbox folder. The pipeline will warn you if you try.

---

**Problem:** MSConvert appears stuck for hours during the "writing to mzML" stage
**Cause:** Your output folder is on a network share (Z:, an SMB mount, a VPN-mounted volume, etc.). MSConvert writes the `.mzML` output incrementally with frequent fsyncs; doing that against a high-latency network filesystem can stretch a minute of conversion into many hours of wall time, because each write round-trips over the network.
**Solution:** From v3.0.13 onward K2 Annotator stages each conversion through a fast local temp directory (default `%TEMP%\k2_msconvert_*`) and copies the finished `.mzML` to the requested output folder in one shot. This is on by default — you should see a `Staging directory:` line at the top of the conversion stage. If you ever want to skip the staging step (e.g. because your output is already on a fast local SSD and you want to avoid the extra copy), pass `--no-stage-locally` to `gcms_pipeline.py`.

If staging is enabled and conversion is *still* slow, the bottleneck is now on the **read** side — MSConvert reading the raw `.D` folder from the network share. The simplest remedy is to copy the raw folder(s) to a local drive first and run the pipeline against that local copy.

---

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
Normalization Factor = Median IS Area / Sample IS Area
Normalized Abundance = Raw Abundance × Normalization Factor
```

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

If you use K2 in your research, please cite:

[Citation information to be added]

---

## Version History

### Version 3.0.2 (January 2026)
- Structure lookup safety: Only InChIKey used for PubChem queries (prevents ambiguous name matches)
- Fixed multiple library entry handling (same compound with different sources)

### Version 3.0.1 (January 2026)
- Fixed unique plot generation for multiple library entries of same compound
- Added Library_Entry_ID column for tracking specific library matches

### Version 3.0.0 (January 2026)
- **Major Feature**: Surrogate Standard Recovery Analysis
- New SurrogateConfigScreen for configuring labeled standard tracking
- Enhanced Sample Classification with Reference samples, Spiked status, Spike Ratios, and Groups
- Surrogate recovery calculations with group-based normalization
- New Surrogate Recovery tab in results viewer
- Separate surrogate CSV output file

### Version 2.9.x (January 2026)
- Enhanced EPA CompTox integration via ctx-python package
- Improved hazard data retrieval

### Version 2.8.0 (January 2026)
- Internal Standard normalization integration in Sample Classification screen
- Three IS methods: Manual entry, Auto m/z+RI/RT, Auto MSP spectrum
- IS area and normalization factor columns in CSV reports
- IS display in GUI sample table

### Version 2.7.0 (2026)
- Structure helper module for high-resolution images
- Hazard matrix visualization in PDF reports
- Statistics module deprecated (external analysis recommended)

### Version 2.6.0 (2026)
- MZmine integration for feature detection
- Universal parser supporting MS-DIAL and MZmine formats
- Improved Blank Feature Filtering

### Version 1.0 (January 2026)
- Initial release
- Full pipeline integration
- Interactive results viewer
- Project and preset management
- Support for .CSV and .MSP libraries

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

## Support

For bug reports, feature requests, or questions:
- [Contact information to be added]
- [GitHub repository link to be added]

---

**© 2026 K2 Annotator**
