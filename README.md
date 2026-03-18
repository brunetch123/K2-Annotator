# K2 GC-MS Suspect Screening Pipeline

**Version 3.0.2** | Open-source GC-MS data processing and Level 2 compound identification

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

1. Clone or download this repository
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install external tools (optional but recommended):
   - [ProteoWizard MSConvert](https://proteowizard.sourceforge.io/) for raw file conversion
   - [MZmine](https://mzmine.github.io/) for feature detection

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

## Documentation

- **[K2_USER_GUIDE.md](K2_USER_GUIDE.md)** - Complete user documentation
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes
- **[QUICK_START.md](QUICK_START.md)** - Quick start guide

## Library Formats

K2 supports two library formats:

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

## Dependencies

See [requirements.txt](requirements.txt) for Python packages:
- pandas, numpy - Data processing
- matplotlib, Pillow - Visualization
- reportlab - PDF generation
- pubchempy - PubChem API access
- ctx-python - EPA CompTox API

## Citation

If you use K2 in your research, please cite:

*[Citation information to be added]*

## License

*[License information to be added]*

## Support

For bug reports, feature requests, or questions:
- *[GitHub repository link to be added]*

---

**© 2026 K2 GC-MS Analysis Pipeline**
