# K2 GC-MS Suspect Screening Pipeline

**Version 3.0.3** | Open-source GC-MS data processing and Level 2 compound identification

## Overview

K2 Analyzer is an open-source pipeline for non-targeted GC-MS suspect screening, providing automated processing from raw instrument files to Level 2 compound identification. The pipeline integrates:

- **Raw file conversion** via ProteoWizard MSConvert
- **Feature detection and deconvolution** via MZmine
- **Spectral library matching** with Retention Index and RHRMF validation
- **Hazard screening** via EPA CompTox APIs
- **Surrogate standard recovery** calculation (v3.0.0+)

## Features

- **One-touch processing**: GUI-based workflow from raw data to annotated results
- **Level 2 identification**: Spectral matching with RI validation following Koelmel et al. 2022 criteria
- **Blank Feature Filtering**: Automatic removal of background contamination
- **Internal Standard normalization**: Multiple methods for inter-sample variability correction
- **Surrogate recovery**: Track labeled surrogate standards through sample processing
- **Hazard assessment**: Integrated EPA CompTox database lookups with GHS classification

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Windows 10/11 (for GUI features)

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/brunetch123/K2-GCMS-Pipeline.git
   cd K2-GCMS-Pipeline
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install external tools (required for full pipeline):
   - [ProteoWizard MSConvert](https://proteowizard.sourceforge.io/) — for raw file conversion (.D → mzML)
   - [MZmine 3](https://mzmine.github.io/) — for feature detection and deconvolution
4. Provide a spectral library in CSV or MSP format (see **Library Formats** below)

### Running the GUI

```bash
python scripts/k2_gui.py
```

Or use the provided batch file:
```bash
K2.bat
```

### Command Line Usage

```bash
python scripts/cli.py --quant data.csv --msp spectra.msp --library library.msp --output results/
```

## External Dependencies

K2 requires the following tools to be installed separately (they are not bundled due to size and licensing):

| Tool | Purpose | Download |
|------|---------|----------|
| **ProteoWizard MSConvert** | Convert raw instrument files (.D) to mzML | [proteowizard.sourceforge.io](https://proteowizard.sourceforge.io/) |
| **MZmine 3** | Feature detection, deconvolution, quantification | [mzmine.github.io](https://mzmine.github.io/) |

Place these in a `software/` directory alongside this repository, or configure their paths in the K2 GUI settings.

## Spectral Library

K2 requires a spectral library for compound identification. Users must provide their own library file in one of the supported formats below. Example templates are included in the `templates/` directory.

### CSV Format
```csv
name,formula,ri,cas,inchikey,peaks_json
Naphthalene,C10H8,1181,91-20-3,UFWIBTONFRDIAS-UHFFFAOYSA-N,"[[128,999],[127,150]]"
```

### MSP Format (NIST-compatible)
```
NAME: Naphthalene
FORMULA: C10H8
RI: 1181
CAS: 91-20-3
INCHIKEY: UFWIBTONFRDIAS-UHFFFAOYSA-N
Num Peaks: 2
128 999
127 150
```

## Documentation

- **[K2_USER_GUIDE.md](K2_USER_GUIDE.md)** — Complete user documentation
- **[QUICK_START.md](QUICK_START.md)** — Quick start guide
- **[INSTALLATION.txt](INSTALLATION.txt)** — Detailed installation instructions
- **[CHANGELOG.md](CHANGELOG.md)** — Version history and changes

## Project Structure

```
K2-GCMS-Pipeline/
├── scripts/
│   ├── k2_gui.py          # Main GUI application
│   ├── cli.py             # Command-line interface
│   ├── gcms_pipeline.py   # Pipeline orchestration
│   ├── k2_config.py       # Configuration management
│   ├── k2_screens.py      # GUI screen definitions
│   ├── main.py            # Entry point
│   └── src/               # Core processing modules
│       ├── universal_parser.py    # Multi-format data parser
│       ├── library_parser.py      # Library file parser
│       ├── matching_engine.py     # Spectral matching
│       ├── spectral_math.py       # Dot product scoring
│       ├── reporter.py            # Report generation
│       ├── is_normalizer.py       # Internal standard normalization
│       ├── ri_calibration.py      # Retention index calibration
│       ├── rhrmf.py               # HR mass formula validation
│       ├── structure_helper.py    # PubChem structure lookup
│       ├── surrogate_analyzer.py  # Surrogate recovery analysis
│       ├── surrogate_reporter.py  # Surrogate recovery reports
│       ├── ctx_client.py          # EPA CompTox API client
│       ├── epa_client.py          # Legacy EPA API client
│       └── msdial_parser.py       # MS-DIAL format parser
├── config/                # MZmine workflow configurations
├── templates/             # Library format templates and test data
├── users/                 # MZmine user profiles
├── K2.bat                 # Windows launch script
├── K2.spec                # PyInstaller build specification
├── requirements.txt       # Python dependencies
└── LICENSE                # MIT License
```

## Building the Executable (Optional)

To build a standalone Windows executable:

```bash
pip install pyinstaller
pyinstaller K2.spec
```

The executable will be created in `dist/K2/`.

## Python Dependencies

See [requirements.txt](requirements.txt):
- **pandas**, **numpy** — Data processing
- **matplotlib**, **Pillow** — Visualization
- **reportlab** — PDF generation
- **pubchempy** — PubChem API access
- **ctx-python** — EPA CompTox API
- **molmass** — Molecular weight calculations
- **requests** — HTTP client

## Citation

If you use K2 in your research, please cite:

*Brunet, T. (2026). K2 GC-MS Suspect Screening Pipeline (v3.0.3). GitHub. https://github.com/brunetch123/K2-GCMS-Pipeline*

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Support

For bug reports, feature requests, or questions:
- [GitHub Issues](https://github.com/brunetch123/K2-GCMS-Pipeline/issues)

---

**© 2026 K2 GC-MS Analysis Pipeline**
