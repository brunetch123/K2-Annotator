# K2 Build Instructions

## Problem Solved

Previously, when building K2 releases, your personal file paths from `C:\Users\brune\.k2\k2_defaults.json` were being loaded and displayed to new users. This happened because:

1. Your local config file was being read during development/testing
2. Fallback paths in the code pointed to your development directory
3. These paths were being saved back to config on every "Next" click

## Solutions Implemented

### 1. Code Changes

**scripts/k2_screens.py** - Removed fallback paths
- Eliminated automatic path detection that used `__file__` directory
- Users now start with blank fields and must browse for their own files
- This prevents any developer-specific paths from appearing

**scripts/k2_config.py** - Enhanced first-run detection
- Added clearer messaging when first run is detected
- Ensures clean defaults are used on first launch

### 2. Build Scripts

Three new scripts have been created to ensure clean builds:

#### `build_clean.bat` - Pre-Build Cleanup
- Backs up your local config file
- Temporarily moves it out of the way during build
- Cleans previous build artifacts (build/, dist/)
- Run this BEFORE building

#### `build_restore.bat` - Post-Build Restore
- Restores your local config after build completes
- Returns your development environment to normal
- Run this AFTER building

#### `build_release.bat` - Complete Build Process
- **RECOMMENDED**: Runs cleanup, build, and restore automatically
- One command to create a clean release build
- Handles errors and restores config even if build fails

## Building a Release

### Method 1: Automated (Recommended)

Simply run:
```batch
build_release.bat
```

This will:
1. Clean your environment
2. Build the executable
3. Restore your config
4. Verify the build

### Method 2: Manual Steps

If you prefer manual control:

```batch
# Step 1: Clean
build_clean.bat

# Step 2: Build
pyinstaller K2.spec --clean

# Step 3: Restore
build_restore.bat
```

## Verification Steps

After building, verify that the executable works correctly for new users:

1. **Move the executable to a test directory**
   ```batch
   mkdir C:\K2_Test
   xcopy /E /I dist\K2 C:\K2_Test\K2
   ```

2. **Delete the test user config** (to simulate first-run)
   ```batch
   del "%USERPROFILE%\.k2\k2_defaults.json"
   ```

3. **Run the test executable**
   ```batch
   C:\K2_Test\K2\K2.exe
   ```

4. **Check that the Analysis Parameters screen has:**
   - Empty "Spectral Library" field
   - Empty "RI Calibration File" field
   - Empty "EPA CompTox API Key" field
   - Default "Blank Sample Identifier": `fieldblank`

5. **Restore your config**
   ```batch
   copy "%USERPROFILE%\.k2\k2_defaults.json.backup" "%USERPROFILE%\.k2\k2_defaults.json"
   ```

## Why This Happens

The issue occurs because:

1. **Config Persistence**: K2 saves user preferences to `%USERPROFILE%\.k2\k2_defaults.json`
2. **Development Testing**: When you test the app during development, your paths get saved
3. **Build Process**: If this file exists during development/testing, those paths can influence the code

## Best Practices

### Before Every Release Build:

1. ✅ Run `build_release.bat` instead of building manually
2. ✅ Test the built executable with a fresh user profile
3. ✅ Check that no hardcoded paths appear in the UI
4. ✅ Verify the `.k2/` directory is in `.gitignore`

### During Development:

1. ✅ Keep `.gitignore` up to date (already includes `.k2/`)
2. ✅ Don't commit `k2_defaults.json` or personal config files
3. ✅ Test with fresh config occasionally: delete `%USERPROFILE%\.k2\k2_defaults.json`

### When Distributing:

1. ✅ Always use the `dist\K2\` output directory
2. ✅ Zip the entire `K2` folder, not just `K2.exe`
3. ✅ Include README, CHANGELOG, and user guide in the distribution
4. ✅ Test on a clean Windows VM or different user account if possible

## Troubleshooting

### Issue: Paths still appear after rebuild

**Solution**:
1. Check that `build_clean.bat` successfully moved your config file
2. Verify no config file exists at `%USERPROFILE%\.k2\k2_defaults.json` during build
3. Close all running instances of K2 before building

### Issue: Build script fails

**Solution**:
1. Make sure PyInstaller is installed: `pip install pyinstaller`
2. Run from the project root directory
3. Check that K2.spec exists in the current directory
4. Ensure Python scripts directory is in PATH

### Issue: Executable doesn't start

**Solution**:
1. Run with console enabled to see errors: Edit K2.spec line 148 to `console=True`
2. Rebuild and check console output for error messages
3. Verify all dependencies are installed in your Python environment
4. Check that required data files (icons, docs) are present

## Additional Notes

- Your backup config is saved as `k2_defaults.json.backup` for safety
- Build scripts are Windows batch files (.bat) - for cross-platform builds, create equivalent shell scripts
- The `.k2/` directory in your home folder is already ignored by git
- Personal user files (`*.mzuser`, `*.K2`, `*.K2config`) are also gitignored

## Questions?

If paths still appear after following these steps:
1. Check the code changes were applied correctly
2. Verify the build scripts ran without errors
3. Test with a completely fresh Windows user account
4. Open an issue on GitHub with screenshots of the problem
