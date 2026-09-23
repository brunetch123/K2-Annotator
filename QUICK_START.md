# K2 - Quick Start Guide

## Launch K2 Right Now

```bash
# From this directory, just run:
K2.bat
```

That's it! The GUI should open immediately.

---

## First Time Setup (30 seconds)

When K2 opens:

1. Click **"Start New Analysis"**

2. Select your entry point (for testing, choose any)

3. **Browse** to select folders (use the example data if you want)

4. **Important:** Set paths to external tools:
   - MSConvert: e.g. `C:\Program Files\ProteoWizard\msconvert.exe`
     (if starting from raw vendor data)
   - MZmine: e.g. `C:\Program Files\mzmine\mzmine_console.exe`
   - User file: `users\default.mzuser` (included)
   - Batch file: `config\gc_ei_workflow.mzbatch` (included)
   - Library: your own CSV or MSP file (see `templates/`)
   - RI calibration: an n-alkane table such as `templates/ri_calibration_template.txt`
     (required for MZmine data — RI is a mandatory Level-2 criterion)
   - RI Cal: optional, your own tab-delimited alkane RT table

5. Check **"Save as default"** boxes so you don't have to do this again

6. Click **"Run Analysis"**

---

## Testing Without Running Full Pipeline

If you just want to test the GUI without running a full analysis:

1. Launch `K2.bat`
2. Click through each screen using **"Next"** buttons
3. Click **"Back"** to navigate backwards
4. Try the menu: **File → Save Project**
5. Try saving a preset: **File → Save Preset**
6. Close and reopen to test **"Load Existing Project"**

---

## Verify It Works

### ✅ GUI Should:
- Open without errors
- Show K2 logo (K2Icon.png / K2Logo.png are bundled)
- Display all screens cleanly (Welcome, Entry Select, Project Setup,
  Sample Classification, MSConvert, MZmine, Analysis Parameters,
  Surrogate Config, Execution, Results)
- Allow navigation back/forth
- Save/load projects and presets
- Execute pipeline when configured

### ❌ If Problems:
```bash
# Reinstall Python dependencies
pip install -r requirements.txt

# Try running directly:
python scripts\k2_gui.py

# Check for errors in output
```

---

## Common First-Run Issues

**"MSConvert not found"**
→ Click **Browse** and navigate to the exe
→ Or skip this screen if starting from .mzML or .MSP

**"No module named 'tkinter'"**
→ tkinter should be built-in
→ Reinstall Python with tk support if missing

**"Permission denied" when saving**
→ Run as administrator
→ Or choose a different output folder

---

## Example / Test Data

A tiny validation dataset is bundled in `templates/`:

- `library_template.csv` / `library_template.msp` — example library entries
- `test_quant.csv` / `test_spectra.msp` — example MZmine-format inputs
- `TEST_DATA_README.md` — explanation of the test features and expected matching behavior

This data is for sanity-checking the GUI flow and validating that the
matching engine runs end-to-end. It is not a production library or
sample set — use your own data for real analyses.

---

## Quick Feature Tour

### 🎯 Main Features:

**Project Management:**
- Save your work as `.K2` files
- Resume later exactly where you left off
- Share projects with colleagues

**Presets:**
- Save configurations as `.K2config` files
- Quickly switch between instrument setups
- Share standard methods

**Smart Defaults:**
- First-time setup is remembered
- Paths auto-populate from local software
- Less clicking next time

**Live Execution:**
- Watch pipeline progress in real-time
- See exactly what's happening
- Cancel if something goes wrong

**Results Viewer:**
- Browse matches interactively
- View detailed information in tabs
- Quick export to CSV/PDF

---

## Next Steps

1. **Read the Full Guide:** `K2_USER_GUIDE.md`
2. **Try With Your Data:** Use real samples
3. **Customize Settings:** Save your own presets
4. **Share With Team:** Distribute the package

---

## Need Help?

- Check `K2_USER_GUIDE.md` for detailed instructions
- Check `CHANGELOG.md` for the current version's behavioral changes
- Check console output for error messages
- Verify all external tools are installed

---

## Keyboard Shortcuts

- `Ctrl+N` - New Project
- `Ctrl+O` - Open Project
- `Ctrl+S` - Save Project

---

**Enjoy your new GC-MS analysis tool!** 🎉
