# K2 Packaging and Distribution Guide

## Overview

This document describes how to package K2 for distribution as a standalone application.

---

## What to Include in Distribution

### ✅ INCLUDE These Files/Folders:

```
K2/
├── K2.bat                          # Windows launcher
├── K2Icon.png                      # Application icon
├── K2_USER_GUIDE.md                # User documentation
├── .venv/                          # Python virtual environment (full)
├── scripts/
│   ├── k2_gui.py                   # Main GUI application
│   ├── k2_config.py                # Configuration management
│   ├── k2_screens.py               # GUI screens
│   ├── cli.py                      # CLI interface
│   ├── gcms_pipeline.py            # Pipeline orchestrator
│   └── src/
│       ├── matching_engine.py
│       ├── universal_parser.py
│       ├── library_parser.py
│       ├── spectral_math.py
│       ├── ri_calibration.py
│       ├── rhrmf.py
│       ├── reporter.py
│       ├── visualizer.py
│       ├── epa_client.py
│       └── __init__.py
├── config/
│   ├── gc_ei_workflow.mzbatch     # Example MZmine batch
│   └── MZMinePresets_*.mzwizard   # Example presets
├── users/
│   └── default.mzuser             # Template user file
├── examplerawdata/                # Example data (optional)
│   ├── FieldBlank_AR1.D/
│   └── [other example files]
├── templates/                     # NEW - Create this
│   ├── example_library.csv        # Small example library
│   ├── example_library.msp        # Example MSP format
│   └── example_ri_cal.txt         # Example RI calibration
└── requirements.txt               # Python dependencies
```

### ❌ EXCLUDE These Files/Folders:

```
DO NOT INCLUDE:
├── software/                      # User must provide
│   ├── mzmine/                    # Too large (~500MB)
│   └── pwiz-bin/                  # Licensing/distribution restrictions
├── unified_library_20251013.csv   # Large, user-specific
├── MSDial_RICal.txt              # User-specific
├── results/                       # Generated data
├── converted/                     # Generated data
├── mzmine_output/                # Generated data
├── temp/                         # Temporary files
├── .idea/                        # IDE files
├── __pycache__/                  # Python cache
├── *.pyc                         # Compiled Python
├── .git/                         # Git repository
├── prompt*.txt                   # Development files
├── ToDO.txt                      # Development notes
└── venv/                         # Old broken venv (already removed)
```

---

## Packaging Steps

### 1. Prepare the Distribution Folder

```bash
# Create clean distribution directory
mkdir K2_v1.0_dist
cd K2_v1.0_dist

# Copy essential files
copy-item -Recurse .venv
copy-item -Recurse scripts
copy-item -Recurse config
copy-item -Recurse users
copy-item K2.bat
copy-item K2Icon.png
copy-item K2_USER_GUIDE.md
copy-item requirements.txt
```

### 2. Create Template Files

Create `templates/example_library.csv`:
```csv
name,formula,ri,peaks_json,cas,inchikey
Acetone,C3H6O,586.5,"[[43,999],[58,359],[42,20]]",67-64-1,CSCPPACGZOFKFQ-UHFFFAOYSA-N
Benzene,C6H6,652.3,"[[78,999],[77,200],[52,50]]",71-43-2,UHOVQNZJYSORNB-UHFFFAOYSA-N
Toluene,C7H8,763.1,"[[91,999],[92,730],[65,85]]",108-88-3,YXFVVABEGXRONW-UHFFFAOYSA-N
```

Create `templates/example_library.msp`:
```
NAME: Acetone
RI: 586.5
FORMULA: C3H6O
CAS: 67-64-1
NUM PEAKS: 3
43 999
58 359
42 20

NAME: Benzene
RI: 652.3
FORMULA: C6H6
CAS: 71-43-2
NUM PEAKS: 3
78 999
77 200
52 50

```

Create `templates/example_ri_cal.txt`:
```
Carbon_Number	Retention_Time
9	5.123
10	6.456
11	7.789
12	9.012
13	10.234
```

### 3. Clean the Virtual Environment (Optional)

To reduce size, you can remove unnecessary packages:

```bash
# Activate venv
.venv\Scripts\activate

# Remove development-only packages
pip uninstall -y pip setuptools wheel

# Or create a minimal requirements.txt and rebuild
pip freeze > requirements_full.txt
# Edit to keep only essential packages
pip install -r requirements_minimal.txt
```

### 4. Create Distribution Package

```bash
# Create ZIP archive
Compress-Archive -Path K2_v1.0_dist -DestinationPath K2_v1.0_Windows.zip
```

### 5. Create Installation README

Create `INSTALLATION.txt`:
```
K2 - GC-MS Analysis
Version 1.0

INSTALLATION
============

1. Extract this ZIP file to your desired location (e.g., C:\K2\)

2. Double-click K2.bat to launch the application

3. On first run, configure paths to:
   - MSConvert (download from proteowizard.sourceforge.net)
   - MZmine (download from github.com/mzmine/mzmine)
   - Your spectral library
   - RI calibration file (optional)

4. See K2_USER_GUIDE.md for detailed instructions

SYSTEM REQUIREMENTS
===================
- Windows 10 or higher
- 8GB RAM minimum (16GB recommended)
- 10GB free disk space
- Internet connection for EPA API (optional)

EXTERNAL SOFTWARE REQUIRED
===========================
You must download and install these separately:

1. ProteoWizard (for MSConvert)
   Download: http://proteowizard.sourceforge.net/

2. MZmine 3.x
   Download: https://github.com/mzmine/mzmine/releases

See User Guide for detailed setup instructions.

SUPPORT
=======
[Contact information]

```

---

## Alternative: PyInstaller Executable

For a true standalone executable (no Python required):

### Install PyInstaller

```bash
pip install pyinstaller
```

### Create Spec File

Create `K2.spec`:
```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['scripts\\k2_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('K2Icon.png', '.'),
        ('config', 'config'),
        ('users', 'users'),
        ('templates', 'templates'),
        ('K2_USER_GUIDE.md', '.'),
    ],
    hiddenimports=[
        'tkinter',
        'PIL',
        'reportlab',
        'matplotlib',
        'pubchempy',
        'scipy',
        'pandas',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='K2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='K2Icon.ico'  # Create .ico from .png
)
```

### Build Executable

```bash
pyinstaller K2.spec
```

Output will be in `dist/K2.exe`

### Notes on PyInstaller

**Advantages:**
- No Python installation required
- Single executable file
- Easier distribution

**Disadvantages:**
- Larger file size (~100-200MB)
- Slower startup time
- May trigger antivirus false positives
- More complex debugging

---

## Distribution Checklist

- [ ] Clean all temporary files
- [ ] Remove development files
- [ ] Include example templates
- [ ] Test on clean Windows machine
- [ ] Verify all external tools install correctly
- [ ] Test full workflow with example data
- [ ] Check file paths are relative (no hardcoded paths)
- [ ] Ensure K2Icon.png is present
- [ ] Include user guide
- [ ] Include installation instructions
- [ ] Test preset save/load
- [ ] Test project save/load
- [ ] Verify .K2 and .K2config file formats

---

## Size Optimization

Expected sizes:
- **Minimal** (no venv, user installs Python): ~5MB
- **With venv** (recommended): ~200-300MB
- **PyInstaller executable**: ~150-250MB
- **With example data**: Add ~50-100MB per dataset

### Reducing Size

1. **Virtual Environment:**
   - Use `--copies` instead of symlinks
   - Remove `.pyc` files: `find .venv -name "*.pyc" -delete`
   - Remove pip cache: `pip cache purge`

2. **Example Data:**
   - Include only 1-2 small example .D files
   - Or provide download link for full examples

3. **Documentation:**
   - Keep as Markdown (smaller than PDF)
   - Or provide web link to full documentation

---

## Testing the Distribution

### On Your Machine

```bash
# Extract to a new location
cd C:\Temp\K2_Test
# Extract K2_v1.0_Windows.zip here

# Test launcher
K2.bat

# Verify:
# - GUI launches
# - All screens load
# - Can browse for files
# - Defaults save/load
# - Help menu works
```

### On a Clean Machine

1. Use a fresh Windows 10/11 VM
2. Do NOT install Python
3. Extract K2 package
4. Follow installation instructions
5. Verify external tool setup
6. Run complete workflow
7. Check results

### Test Cases

- [ ] Launch GUI without errors
- [ ] Create new project
- [ ] Configure all paths
- [ ] Save as preset
- [ ] Load preset
- [ ] Run full pipeline (.D → results)
- [ ] Run partial pipeline (.mzML → results)
- [ ] Run matching only (.MSP → results)
- [ ] Save project as .K2
- [ ] Load .K2 project
- [ ] View results
- [ ] Export CSV/PDF
- [ ] Test with MSP library
- [ ] Test with CSV library
- [ ] Test without RI calibration
- [ ] Test with EPA API key

---

## Version Numbering

Format: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes to file formats or workflow
- **MINOR**: New features, backwards compatible
- **PATCH**: Bug fixes only

Example:
- `1.0.0`: Initial release
- `1.1.0`: Added new library format support
- `1.1.1`: Fixed bug in RI calculation

---

## License and Legal

**Before Distribution:**

1. **Check dependencies licenses:**
   - All Python packages (MIT/BSD compatible)
   - Verify redistribution allowed

2. **External software:**
   - Do NOT include MSConvert or MZmine
   - Provide download links only
   - Check their licenses

3. **Your code:**
   - Add license file (MIT recommended)
   - Add copyright notices
   - Include attribution

4. **User data:**
   - Do NOT include user-specific libraries
   - Do NOT include proprietary data
   - Example data should be public/licensed

---

## Future Enhancements

Potential packaging improvements:

1. **Installer:**
   - Create NSIS or Inno Setup installer
   - Add to Windows PATH
   - Create Start Menu shortcuts
   - File associations (.K2, .K2config)

2. **Auto-updater:**
   - Check for updates on launch
   - Download and apply updates
   - Maintain user settings

3. **Portable Version:**
   - Run from USB drive
   - No installation required
   - Settings stored locally

4. **Cross-platform:**
   - macOS version
   - Linux version
   - Platform-specific installers

---

## Support and Maintenance

### User Support

- GitHub Issues for bug reports
- Email support for questions
- FAQ document
- Video tutorials
- Example workflows

### Updates

- Release notes for each version
- Migration guides for breaking changes
- Backwards compatibility policy
- Deprecation warnings

---

**Ready to Package!**

Your K2 distribution is now ready. Test thoroughly before public release.
