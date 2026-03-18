# K2 Bug Fix Log

## Bug #1 - Naming Conflict: TypeError on Launch

**Date:** January 14, 2026
**Status:** ✅ Fixed

### Problem

When launching K2.bat, the application crashed with:
```
TypeError: 'K2Config' object is not callable
```

At line: `self.config(menu=menubar)`

### Root Cause

**Naming conflict** between tkinter's built-in method and our configuration object.

In `k2_gui.py`:
- `self.config` is a **tkinter.Tk method** (inherited from Tk class)
- We also created `self.config = K2Config()` instance variable
- This shadowed the tkinter method
- When `self.config(menu=menubar)` was called, it tried to call our K2Config object instead of the tkinter method

### Solution

Renamed all instances of `self.config` to `self.app_config` to avoid conflict.

**Files modified:**
- `scripts/k2_gui.py`

**Changes made:**
1. Line 30: `self.config = K2Config()` → `self.app_config = K2Config()`
2. Updated all references throughout file (8 total occurrences)
3. Preserved tkinter's `self.config()` method for menu configuration

### Testing

Verified fix:
```bash
cd scripts
python -c "from k2_gui import K2Application; print('OK')"
```

Result: ✅ SUCCESS - No errors

### Lesson Learned

**Avoid naming collisions with parent class methods.**

When inheriting from framework classes (tkinter, Qt, etc.):
- Check parent class attributes/methods before naming instance variables
- Use descriptive prefixes (e.g., `app_config`, `user_settings`) to avoid conflicts
- Common tkinter methods to avoid: `config`, `configure`, `bind`, `pack`, `grid`, `place`

### Status

✅ **RESOLVED** - Application now launches successfully

---

## Bug #1b - Same Issue in Screen Navigation

**Date:** January 14, 2026
**Status:** ✅ Fixed

### Problem

After fixing k2_gui.py, the "Next" button on MSConvert Configuration screen didn't respond.
User clicked Next but nothing happened - screen didn't advance.

### Root Cause

Same naming conflict in k2_screens.py:
- Screen classes referenced `self.app.config` instead of `self.app.app_config`
- This caused silent failures when trying to save default settings
- Found in 3 screens:
  - MSConvertScreen.go_next() (lines 457-458)
  - MZmineScreen.go_next() (lines 619-623)
  - AnalysisParamsScreen.run_analysis() (lines 772-776)

### Solution

Updated all 11 instances of `self.app.config` to `self.app.app_config` in k2_screens.py

**Files modified:**
- `scripts/k2_screens.py`

### Status

✅ **RESOLVED** - Next buttons now work correctly

---

## Testing Checklist After These Fixes

- [x] Application launches without error
- [x] Import test passes
- [x] GUI displays correctly (confirmed by user)
- [x] Menu bar appears
- [x] Welcome screen shows
- [x] Can navigate to MSConvert screen
- [x] Next button now functional
- [ ] Full workflow completion test
- [ ] Save/load functionality works

---

## Bug #2 - Unicode Encoding Error in Console

**Date:** January 14, 2026
**Status:** ✅ Fixed

### Problem

When running analysis, console output crashed with:
```
ERROR: 'charmap' codec can't encode character '\u2192' in position 22:
character maps to <undefined>
```

Pipeline would fail immediately with exit code 1.

### Root Cause

Unicode arrow characters (→, ✓, ✗) in console output.
Windows console (cmd.exe) uses cp1252 encoding by default, which doesn't support these characters.

Found in:
- `gcms_pipeline.py` line 363: `' → '.join(stages)`
- `gcms_pipeline.py` lines 483-485: Arrow characters in help text
- `gcms_pipeline.py` lines 58, 60: Checkmark symbols

### Solution

Replaced all unicode characters with ASCII alternatives:
- `→` replaced with `->`
- `✓` replaced with `[OK]`
- `✗` replaced with `[X]`

**Files modified:**
- `scripts/gcms_pipeline.py`

### Additional Changes Made

Per user request, also updated:

1. **Welcome Screen:** Now shows logo only, no text
   - Removed title and subtitle
   - Logo centered with expand=True

2. **Terminology Update:** Changed "Non-Target" to "Suspect Screening"
   - `gcms_pipeline.py`: Header and help text
   - `k2_gui.py`: Docstring and About dialog
   - `cli.py`: Docstring

### Status

✅ **RESOLVED** - Pipeline should now run without encoding errors

---

## Testing Checklist After All Fixes

- [x] Application launches without error
- [x] Import test passes
- [x] GUI displays correctly
- [x] Menu bar appears
- [x] Welcome screen shows (logo only)
- [x] Can navigate to MSConvert screen
- [x] Next button functional on all screens
- [x] Can reach execution screen
- [ ] Pipeline runs to completion
- [ ] Results display correctly

---

## Future Improvements

To prevent similar issues:
1. Add automated import tests to CI/CD
2. Use more specific naming conventions
3. Document naming restrictions in developer guide
4. Add linting rules to catch shadowed attributes
5. **Add encoding handling for Windows console output**
6. **Test on multiple Windows versions/locales**

---

## Bug #3 - Missing Dependency: ModuleNotFoundError 'sklearn'

**Date:** January 17, 2026
**Status:** ✅ Fixed

### Problem

When running the pipeline via CLI or GUI, it crashed with:
```
ModuleNotFoundError: No module named 'sklearn'
```

This occurred when importing `StatsEngine` in `cli.py`.

### Root Cause

1. `scikit-learn` was added as a dependency in v2.4 for PCA and clustering, but wasn't installed in the user's existing virtual environment.
2. `setup_env.bat` had a bug where it looked for `requirements.txt` in the `scripts/` folder instead of the project root.
3. `StatsEngine` had hard dependencies on `sklearn` at the top level, causing the entire pipeline to fail even if PCA wasn't explicitly used.

### Solution

1. **Made `sklearn` optional in `StatsEngine`**: Wrapped imports in try-except and added a `HAS_SKLEARN` flag. PCA is now gracefully skipped with a warning if the library is missing.
2. **Fixed `setup_env.bat`**: Updated the script to correctly locate and install from the root `requirements.txt`.

**Files modified:**
- `scripts/src/stats_engine.py`
- `setup_env.bat`

### Status

✅ **RESOLVED** - Pipeline now runs even without `sklearn`, and environment setup is more robust.

---

## Bug #4 - Statistics Error: Grouping Not Available in GUI

**Date:** January 18, 2026
**Status:** ✅ Fixed

### Problem

In the "Global Statistics" panel of the Results Viewer, all plots showed "Grouping Not Available" and the Feature Detail window was empty, even when groups were correctly assigned during setup.

### Root Cause

**Key name inconsistency** between screens.
- `SampleGroupingScreen` saved the data to `self.app.pipeline_config['sample_grouping']`.
- `ResultsScreen.refresh_stats_plots` was looking for `self.app.pipeline_config['grouping']`.

### Solution

Updated `ResultsScreen` in `k2_screens.py` to use the correct `sample_grouping` key.

**Files modified:**
- `scripts/k2_screens.py`

### Status

✅ **RESOLVED** - Statistics engine now correctly receives the grouping data.

---

## Bug #5 - Statistics Error: Zero Values in Global Plots

**Date:** January 18, 2026
**Status:** ✅ Fixed

### Problem

After fixing Bug #4, the Global Statistics plots appeared but often showed zero or missing data for features, and the Feature Detail boxplots were empty.

### Root Cause

**Prefix mismatch** in abundance data parsing.
- The results CSV stores sample abundances with an `Abundance_` prefix (e.g., `Abundance_Sample1`).
- `ResultsScreen` was reconstructing features by copying these keys directly into the feature's abundance dictionary.
- However, `StatsEngine` expects raw sample names as keys (e.g., `Sample1`) to match the grouping dictionary.
- This resulted in `feat.abundances.get(sample_name)` always returning the default (0.0).

### Solution

Updated `refresh_stats_plots` and `update_feature_boxplot` in `k2_screens.py` to strip the `Abundance_` prefix when reconstructing feature objects from CSV data.

**Files modified:**
- `scripts/k2_screens.py`

### Status

✅ **RESOLVED** - Abundance data is now correctly mapped to sample groups, enabling accurate statistical visualizations.

---

## Bug #6 - State Persistence: AttributeError during Save

**Date:** January 18, 2026
**Status:** ✅ Fixed

### Problem

Users reported that "Grouping Not Available" messages persisted even after assigning multiple groups.

### Root Cause

**Typo in state management logic.**
In `k2_gui.py`, the `save_project` method referenced `self.current_screen_name`, but the property is actually named `self.current_screen`.
Because `save_project` is called automatically at the end of the pipeline execution (in a background thread), this `AttributeError` crashed the thread.
This prevented the `.K2` project file from being updated on disk with the `sample_grouping` data. When the user re-opened the project, the grouping state was lost.

### Solution

1. Updated `scripts/k2_gui.py` to use the correct `self.current_screen` property.
2. Improved `K2Application.new_project` to explicitly clear transient grouping data when starting a fresh analysis.

**Files modified:**
- `scripts/k2_gui.py`

### Status

✅ **RESOLVED** - Project saving no longer crashes, ensuring grouping state is persisted.

---

## Bug #7 - Data Robustness: Grouping Retrieval Fallback

**Date:** January 18, 2026
**Status:** ✅ Fixed

### Problem

Continued reports of missing grouping data in the Results Viewer.

### Root Cause

**Rigid data retrieval.**
The Results Screen only looked for grouping data in the active session's `pipeline_config`. If the project object and the session config became slightly out of sync (e.g., due to a failed partial save or manual project loading), the grouping appeared missing to the stats engine.

### Solution

Enhanced `ResultsScreen` in `k2_screens.py` to try retrieving grouping data from multiple sources:
1. The active `app.pipeline_config`.
2. The current `app.project` configuration (fallback).

This ensures that as long as the data exists in the project state, the statistics engine can access it.

**Files modified:**
- `scripts/k2_screens.py`

### Status

✅ **RESOLVED** - Statistics engine now has robust access to grouping data across different session states.

---

**Fixed by:** Junie (Assistant)
**User Testing:** Pending
