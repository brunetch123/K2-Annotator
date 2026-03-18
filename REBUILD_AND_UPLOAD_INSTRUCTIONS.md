# K2 v3.0.3 - Rebuild and GitHub Upload Instructions

## Summary of Changes Made

All code changes have been completed by Claude. The following fixes were implemented:

### 1. Configuration Fixes
- ✅ Removed user-specific .K2 and .K2config files from templates folder
- ✅ Updated .gitignore to exclude .k2/ directory and .K2config files
- ✅ Default paths in k2_config.py were already correct (empty strings)

### 2. Version Updates
- ✅ Updated version to 3.0.3 in K2.spec
- ✅ Updated version to 3.0.3 in k2_gui.py (About dialog)
- ✅ Updated version to 3.0.3 in k2_screens.py (Welcome screen)
- ✅ Updated version to 3.0.3 in create_distribution.bat

### 3. Build Script Improvements
- ✅ Enhanced create_distribution.bat to automatically restructure files
- ✅ Documentation and templates now moved to top level after build
- ✅ Creates proper distribution hierarchy

### 4. Documentation
- ✅ Added comprehensive v3.0.3 entry to CHANGELOG.md

---

## PART 1: Clean and Rebuild

### Step 1: Open Command Prompt
```cmd
cd C:\Users\brune\OneDrive\Desktop\gcms_pipeline
```

### Step 2: Clean Previous Builds
```cmd
rmdir /s /q build
rmdir /s /q dist
del K2_v3.0.2_Windows.zip
rmdir /s /q K2_v3.0.2_Windows
rmdir /s /q K2_v3.0.3_Windows
```

### Step 3: Activate Virtual Environment (if using one)
```cmd


```

### Step 4: Build the Executable
```cmd
build_exe.bat
```
**Expected time:** 5-10 minutes

**Verify:** Check that `dist\K2\K2.exe` was created

### Step 5: Create Distribution Package
```cmd
create_distribution.bat
```

**This script will:**
1. Copy all files from dist\K2\ to K2_v3.0.3_Windows\
2. Copy documentation to top level
3. Move files from _internal to top level (README, USER_GUIDE, QUICK_START, templates)
4. Create K2_v3.0.3_Windows.zip

### Step 6: Test the Distribution
```cmd
cd K2_v3.0.3_Windows
K2.exe
```

**Verify the following:**
- [ ] GUI opens without errors
- [ ] Library path field is BLANK (no pre-filled path)
- [ ] RI calibration path field is BLANK
- [ ] At the distribution folder level, you see:
  - [ ] K2.exe at top level
  - [ ] README.md at top level
  - [ ] K2_USER_GUIDE.md at top level
  - [ ] QUICK_START.md at top level
  - [ ] templates/ folder at top level
  - [ ] config/ folder at top level
  - [ ] _internal/ folder (contains Python runtime)

Close K2 and return to the project root:
```cmd
cd ..
```

---

## PART 2: Prepare Git Repository

### Step 1: Check Git Status
```cmd
git status
```

**Note:** Since this is a fresh repository with no commits yet, you should see many untracked files.

### Step 2: Stage All Files
```cmd
git add .
```

### Step 3: Verify What Will Be Committed
```cmd
git status
```

**Verify that the following are NOT included (excluded by .gitignore):**
- No files in .k2/ directory
- No .K2config files (user presets with personal paths)
- No .venv/ files
- No __pycache__/ directories

### Step 4: Create Initial Commit
```cmd
git commit -m "Release v3.0.3 - Fixed distribution structure and default paths"
```

---

## PART 3: GitHub Setup and Upload

### Option A: Create New Repository (If Not Done Yet)

1. Go to https://github.com/new
2. Fill in:
   - **Repository name:** `K2-GCMS-Pipeline` (or your preferred name)
   - **Description:** "Open-source GC-MS suspect screening pipeline for Level 2 compound identification"
   - **Visibility:** Select **Private** or **Public** based on your preference
   - **IMPORTANT:** Do NOT check any boxes (no README, no .gitignore, no license)
3. Click "Create repository"
4. **Copy the repository URL** (will look like: `https://github.com/YOUR_USERNAME/K2-GCMS-Pipeline.git`)

### Option B: If Repository Already Exists

If you already created a private repository, just get the URL from the repository page.

### Step 5: Link Local Repository to GitHub
```cmd
git remote add origin https://github.com/YOUR_USERNAME/K2-GCMS-Pipeline.git
```
**Replace `YOUR_USERNAME` with your actual GitHub username!**

### Step 6: Rename Branch to 'main' (GitHub Standard)
```cmd
git branch -M main
```

### Step 7: Push to GitHub
```cmd
git push -u origin main
```

**You may be prompted to authenticate.** Use your GitHub credentials or personal access token.

---

## PART 4: Create GitHub Release with Downloadable ZIP

### Step 1: Go to Your Repository
Navigate to: `https://github.com/YOUR_USERNAME/K2-GCMS-Pipeline`

### Step 2: Create a New Release
1. Click on **"Releases"** (right side of the repository page)
2. Click **"Draft a new release"** or **"Create a new release"**

### Step 3: Fill in Release Information

**Tag version:** `v3.0.3`
- Create new tag: `v3.0.3` on publish

**Release title:** `K2 v3.0.3 - Windows Distribution`

**Description:** Copy and paste the following:
```markdown
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

---

**Full changelog:** [CHANGELOG.md](https://github.com/YOUR_USERNAME/K2-GCMS-Pipeline/blob/main/CHANGELOG.md)
```
**Replace `YOUR_USERNAME` in the link!**

### Step 4: Attach Distribution ZIP
1. Under **"Attach binaries"**, click **"Attach files by dropping them here or selecting them"**
2. Browse and select: `K2_v3.0.3_Windows.zip`
3. Wait for upload to complete (may take a few minutes depending on file size)

### Step 5: Publish Release
- **For private repository:** Only collaborators can access
- **For public repository:** Anyone can download

Click **"Publish release"**

---

## PART 5: Verify Everything Works

### Step 1: Test GitHub Download
1. Go to your repository's Releases page
2. Find the v3.0.3 release
3. Click on `K2_v3.0.3_Windows.zip` to download it
4. Extract to a NEW location (e.g., `C:\Temp\K2_Test\`)

### Step 2: Test Clean Installation
1. Navigate to the extracted folder
2. Verify file structure:
   ```
   K2_v3.0.3_Windows/
   ├── K2.exe                    ← TOP LEVEL
   ├── README.md                 ← TOP LEVEL
   ├── K2_USER_GUIDE.md          ← TOP LEVEL
   ├── QUICK_START.md            ← TOP LEVEL
   ├── CHANGELOG.md              ← TOP LEVEL
   ├── templates/                ← TOP LEVEL FOLDER
   │   ├── library_template.msp
   │   └── library_template.csv
   ├── config/
   └── _internal/                ← Python runtime (technical files)
   ```

3. Double-click `K2.exe`
4. **CRITICAL CHECKS:**
   - [ ] Application opens successfully
   - [ ] Library path is BLANK
   - [ ] RI cal path is BLANK
   - [ ] No error messages on startup

---

## Success Checklist

- [ ] Build completed without errors
- [ ] Distribution structure is correct (docs at top level)
- [ ] Test launch shows blank configuration paths
- [ ] Committed to Git successfully
- [ ] Pushed to GitHub successfully
- [ ] Release created with ZIP attachment
- [ ] Downloaded ZIP and verified clean installation
- [ ] Clean installation shows blank paths

---

## Troubleshooting

### Issue: Git push fails with authentication error
**Solution:** Generate a GitHub Personal Access Token:
1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with `repo` scope
3. Use token as password when prompted

### Issue: ZIP file too large for GitHub
**Solution:** GitHub has a 2GB release asset limit. If your ZIP exceeds this:
1. Consider using Git LFS for large files
2. Or host the ZIP on another service (Zenodo, Google Drive, etc.)

### Issue: Distribution structure still shows files in _internal
**Solution:** The create_distribution.bat script should handle this. Verify:
1. The script completed without errors
2. Check the K2_v3.0.3_Windows folder manually
3. If needed, manually move files from _internal to top level

### Issue: Paths still pre-filled when testing
**Solution:**
1. Delete the .k2 folder in your user home directory: `C:\Users\brune\.k2\`
2. Retry launching K2.exe

---

## Next Steps After Release

1. **Share with collaborators:** Send them the GitHub repository URL
2. **Collect feedback:** Ask testers to verify the installation process
3. **Update documentation:** If any issues are found, document them
4. **Plan next release:** Track bugs and feature requests in GitHub Issues

---

## Contact

If you encounter any issues during this process, review the error messages carefully and check:
1. File permissions
2. Available disk space
3. GitHub repository access
4. Internet connectivity for uploads

**End of Instructions**
