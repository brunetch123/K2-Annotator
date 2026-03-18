# GitHub Release Description for v3.0.3

Copy and paste this into the GitHub release description field:

---

## What's New in v3.0.3

### Fixed
- **Default Configuration Paths**: Removed developer-specific paths from distribution. New users now see blank fields for library and RI calibration paths on first launch
- **Distribution Structure**: Documentation files (README, USER_GUIDE, QUICK_START) and templates folder now appear at top level alongside K2.exe instead of buried in _internal subfolder
- **User-Specific Files**: Removed user-specific .K2 project files and .K2config presets from templates folder

### Improved
- **First-Run Experience**: Clean slate for new users with no pre-populated file paths
- **Documentation Accessibility**: Key documentation files immediately visible when opening distribution folder
- **Release Workflow**: Simplified process for downloading and using K2 from GitHub releases

## Installation

1. Download `K2_v3.0.3_Windows.zip` below
2. Extract to your desired location
3. Double-click `K2.exe` to launch
4. See `K2_USER_GUIDE.md` for detailed instructions

## System Requirements

- Windows 10 or higher
- 8GB RAM minimum (16GB recommended)
- 10GB free disk space

## External Dependencies (Optional)

- ProteoWizard MSConvert (for raw file conversion)
- MZmine 3.x (for feature detection)

## Features

K2 provides a complete workflow for GC-MS suspect screening:

- **One-touch processing**: GUI-based workflow from raw data to annotated results
- **Level 2 identification**: Spectral matching with RI validation
- **Blank Feature Filtering**: Automatic removal of background contamination
- **Internal Standard normalization**: Multiple methods for inter-sample variability correction
- **Surrogate recovery**: Track labeled surrogate standards through sample processing
- **Hazard assessment**: Integrated EPA CompTox database lookups

---

**Full changelog:** See [CHANGELOG.md](../blob/main/CHANGELOG.md) in the repository

**Need help?** Check out [K2_USER_GUIDE.md](../blob/main/K2_USER_GUIDE.md) for complete documentation

---

**Note:** Remember to replace the GitHub links with your actual repository URL when pasting!
