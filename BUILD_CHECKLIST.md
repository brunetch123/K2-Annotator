# K2 Release Build Checklist

Use this checklist before creating and distributing a new release.

## Pre-Build Checks

- [ ] All code changes committed to git
- [ ] Version number updated in:
  - [ ] K2.spec (line 4)
  - [ ] CHANGELOG.md
  - [ ] K2_USER_GUIDE.md (if applicable)
- [ ] No debug/console logging left in code
- [ ] K2.spec has `console=False` (line 148)

## Build Process

- [ ] Run `build_release.bat` (or manual steps below)

### If building manually:
- [ ] Run `build_clean.bat`
- [ ] Run `pyinstaller K2.spec --clean`
- [ ] Run `build_restore.bat`

## Post-Build Verification

- [ ] Executable created at: `dist\K2\K2.exe`
- [ ] Required files present in `dist\K2\`:
  - [ ] K2.exe
  - [ ] K2Icon.png
  - [ ] K2Logo2.png
  - [ ] K2_USER_GUIDE.md
  - [ ] README.md
  - [ ] CHANGELOG.md
  - [ ] QUICK_START.md
  - [ ] \_internal\ folder
  - [ ] config\ folder
  - [ ] users\ folder
  - [ ] templates\ folder

## Testing on Clean Environment

- [ ] Copy `dist\K2\` to a test directory (e.g., `C:\K2_Test\`)
- [ ] Delete your user config: `del %USERPROFILE%\.k2\k2_defaults.json`
- [ ] Launch the test executable
- [ ] Verify Analysis Parameters screen shows:
  - [ ] **BLANK** Spectral Library field (NO PATHS!)
  - [ ] **BLANK** RI Calibration File field (NO PATHS!)
  - [ ] **BLANK** EPA API Key field
  - [ ] Default blank identifier: `fieldblank`
- [ ] Test basic workflow:
  - [ ] Welcome screen loads
  - [ ] Can navigate through screens
  - [ ] Browse buttons work correctly
  - [ ] No crashes or errors
- [ ] Restore your config: `copy %USERPROFILE%\.k2\k2_defaults.json.backup %USERPROFILE%\.k2\k2_defaults.json`

## Package for Distribution

- [ ] Rename `dist\K2\` to `K2_v{VERSION}_Windows\` (e.g., `K2_v3.0.4_Windows\`)
- [ ] Create ZIP archive of the entire folder
- [ ] ZIP filename: `K2_v{VERSION}_Windows.zip`
- [ ] ZIP contains:
  - [ ] K2.exe (in root of extracted folder)
  - [ ] All documentation files
  - [ ] All support folders
- [ ] Test ZIP extraction and run on another machine if possible

## Upload to GitHub

- [ ] Create git tag: `git tag v{VERSION}`
- [ ] Push tag: `git push origin v{VERSION}`
- [ ] Create GitHub Release:
  - [ ] Title: `K2 v{VERSION}`
  - [ ] Description from CHANGELOG.md
  - [ ] Attach ZIP file
  - [ ] Mark as pre-release if beta
- [ ] Test download link from GitHub

## Final Verification

- [ ] Download the release from GitHub
- [ ] Extract on a clean system (or VM)
- [ ] Run fresh and verify **NO developer paths appear**
- [ ] Paths should be **completely blank**
- [ ] Users should browse to their own files

## If Issues Found

- [ ] Do NOT distribute
- [ ] Fix the issues
- [ ] Repeat full checklist
- [ ] Increment patch version if needed

---

## Quick Test for Developer Paths

If you see ANY of these in a fresh install, **DO NOT RELEASE**:

❌ `C:\Users\brune\...`
❌ `C:\users\brune\...`
❌ `OneDrive\Desktop\gcms_pipeline\...`
❌ Any absolute paths to YOUR system

✅ Fields should be **completely empty/blank**
✅ Users browse for their own files
✅ First run detects properly and uses clean defaults

---

**Last Updated**: 2025-02-01
**Current Version**: 3.0.3 (update this with each release)
