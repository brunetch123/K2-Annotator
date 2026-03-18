# GitHub and Zenodo Setup Guide for K2

This guide walks you through setting up GitHub (for version control and collaboration) and Zenodo (for DOI and citation) for the K2 GC-MS Pipeline.

---

## Part 1: Build the Executable

Before uploading to GitHub, build the distributable package:

### Step 1: Open Command Prompt

```cmd
cd C:\Users\brune\OneDrive\Desktop\gcms_pipeline
```

### Step 2: Activate your Python environment (if using venv)

```cmd
.venv\Scripts\activate
```

### Step 3: Create the icon file

```cmd
python create_icon.py
```

### Step 4: Build the executable

```cmd
build_exe.bat
```

This will take 5-10 minutes. When complete, you'll have `dist\K2\K2.exe`.

### Step 5: Create the distribution package

```cmd
create_distribution.bat
```

This creates `K2_v3.0.2_Windows.zip` ready for distribution.

### Step 6: Test the executable

Navigate to `K2_v3.0.2_Windows\` and double-click `K2.exe` to verify it works.

---

## Part 2: Set Up GitHub Repository

### Step 1: Create GitHub Account (if needed)

1. Go to https://github.com
2. Click "Sign up"
3. Follow the registration process

### Step 2: Create New Repository

1. Go to https://github.com/new
2. Fill in:
   - **Repository name**: `K2-GCMS-Pipeline` (or your preferred name)
   - **Description**: "Open-source GC-MS suspect screening pipeline for Level 2 compound identification"
   - **Visibility**: **Private** (select this to limit access)
   - **Do NOT** check "Add a README file" (we already have one)
   - **Do NOT** check "Add .gitignore" (we already have one)
   - **Do NOT** check "Choose a license" (we already have one)
3. Click "Create repository"

### Step 3: Initialize Local Git Repository

Open Command Prompt in your project folder:

```cmd
cd C:\Users\brune\OneDrive\Desktop\gcms_pipeline

:: Initialize git repository
git init

:: Add all files (respects .gitignore)
git add .

:: Verify what will be committed
git status

:: Create initial commit
git commit -m "Initial release v3.0.2 - K2 GC-MS Suspect Screening Pipeline"
```

### Step 4: Connect to GitHub and Push

Replace `YOUR_USERNAME` with your GitHub username:

```cmd
:: Rename branch to main (GitHub default)
git branch -M main

:: Add remote repository
git remote add origin https://github.com/YOUR_USERNAME/K2-GCMS-Pipeline.git

:: Push to GitHub (you'll be prompted to login)
git push -u origin main
```

If prompted for credentials:
- Username: Your GitHub username
- Password: A Personal Access Token (not your password)
  - Create at: https://github.com/settings/tokens
  - Select scopes: `repo` (full control of private repositories)

### Step 5: Add Collaborators

1. Go to your repository on GitHub
2. Click **Settings** (top menu)
3. Click **Collaborators** (left sidebar)
4. Click **Add people**
5. Enter their GitHub username or email
6. Click **Add to repository**
7. They will receive an email invitation to accept

### Step 6: Create a Release

1. Go to your repository on GitHub
2. Click **Releases** (right sidebar)
3. Click **Create a new release**
4. Fill in:
   - **Tag version**: `v3.0.2`
   - **Release title**: `K2 v3.0.2 - Initial Release`
   - **Description**: 
     ```
     ## K2 GC-MS Suspect Screening Pipeline v3.0.2
     
     ### Features
     - Full pipeline from raw .D files to Level 2 compound identification
     - Spectral library matching with RI validation
     - Surrogate standard recovery analysis
     - Internal standard normalization
     - EPA CompTox hazard screening
     - PDF and CSV report generation
     
     ### Installation
     1. Download K2_v3.0.2_Windows.zip
     2. Extract to desired location
     3. Run K2.exe
     4. See INSTALLATION.txt for external software setup
     
     ### Requirements
     - Windows 10/11
     - ProteoWizard MSConvert (for .D files)
     - MZmine 3.x (for feature detection)
     ```
5. Drag and drop `K2_v3.0.2_Windows.zip` to attach it
6. Check **Set as the latest release**
7. Click **Publish release**

---

## Part 3: Set Up Zenodo for DOI

Zenodo provides permanent DOIs for your releases, making them citable in publications.

### Step 1: Create Zenodo Account

1. Go to https://zenodo.org
2. Click **Sign Up** (top right)
3. Choose **Sign up with GitHub** (recommended - links accounts automatically)
4. Authorize Zenodo to access your GitHub

### Step 2: Link Your Repository

1. Go to https://zenodo.org/account/settings/github/
2. Find your repository in the list
3. Toggle the switch to **ON** for `K2-GCMS-Pipeline`
4. Zenodo will now automatically archive each GitHub release

### Step 3: Create Release to Generate DOI

If you already created a release in Step 6 above:
1. Zenodo should automatically create an archive
2. Go to https://zenodo.org/deposit to see your deposit
3. If not appearing, create a new release on GitHub

### Step 4: Configure Zenodo Metadata

1. Go to your Zenodo deposit
2. Click **Edit**
3. Fill in metadata:
   - **Title**: K2 GC-MS Suspect Screening Pipeline
   - **Authors**: Add all contributors with ORCID if available
   - **Description**: 
     ```
     K2 is an open-source pipeline for GC-MS non-targeted suspect screening,
     providing automated processing from raw instrument files to Level 2 
     compound identification following Koelmel et al. 2022 criteria.
     ```
   - **Keywords**: GC-MS, mass spectrometry, suspect screening, environmental chemistry, metabolomics
   - **License**: MIT License
   - **Related identifiers**: Link to GitHub repository
4. Click **Save** then **Publish**

### Step 5: Access Control on Zenodo

For **restricted access** (share with select people only):

1. In your Zenodo deposit, click **Edit**
2. Under **Access**, change from "Open Access" to:
   - **Restricted Access**: You manually approve each access request
   - **Embargoed Access**: Becomes public after a set date
3. Save changes

To share with collaborators:
1. Copy the Zenodo DOI link (e.g., `https://doi.org/10.5281/zenodo.XXXXXXX`)
2. Send this link to collaborators
3. They click "Request access"
4. You receive email notification
5. Go to Zenodo and approve their request

---

## Part 4: Sharing with Collaborators

### Option A: GitHub Only (Source Code Access)

For collaborators who need to:
- View and modify source code
- Submit bug reports
- Contribute improvements

1. Add them as GitHub collaborators (Step 5 above)
2. They clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/K2-GCMS-Pipeline.git
   ```

### Option B: Release ZIP Only (End Users)

For collaborators who just need to:
- Run the software
- Not modify code

1. Go to GitHub Releases
2. Share the direct download link:
   ```
   https://github.com/YOUR_USERNAME/K2-GCMS-Pipeline/releases/download/v3.0.2/K2_v3.0.2_Windows.zip
   ```
   (Note: Only works if they have repository access or it's public)

For a truly private link, use:
- Zenodo restricted access (they request, you approve)
- Or share the ZIP file directly via email/cloud storage

### Option C: Zenodo DOI (For Citations)

For publications and formal citations:

1. Use the Zenodo DOI in papers:
   ```
   K2 GC-MS Pipeline (Version 3.0.2). Zenodo. https://doi.org/10.5281/zenodo.XXXXXXX
   ```

2. The DOI is permanent and citable

---

## Quick Reference Commands

### Update Repository After Changes

```cmd
cd C:\Users\brune\OneDrive\Desktop\gcms_pipeline
git add .
git commit -m "Description of changes"
git push
```

### Create New Version

1. Update version numbers in code
2. Update CHANGELOG.md
3. Commit changes:
   ```cmd
   git add .
   git commit -m "Release v3.0.3"
   git push
   ```
4. Create new release on GitHub (tag: v3.0.3)
5. Zenodo automatically creates new DOI

### Check Repository Status

```cmd
git status
git log --oneline -5
```

---

## Troubleshooting

### "Permission denied" when pushing

Solution: Create a Personal Access Token
1. https://github.com/settings/tokens
2. Generate new token (classic)
3. Select `repo` scope
4. Use token as password when pushing

### Zenodo not syncing

1. Check webhook: GitHub repo Settings > Webhooks
2. Ensure Zenodo webhook is listed and active
3. Try disconnecting and reconnecting repo in Zenodo settings

### Large files rejected

GitHub has 100MB file size limit. Solutions:
- Don't commit the `dist/` folder
- Don't commit `.venv/` or `software/` folders
- Upload large files only as release assets

---

## Summary

After completing this guide, you will have:

1. **GitHub Private Repository**
   - Version-controlled source code
   - Collaborator access management
   - Release management with downloadable ZIP

2. **Zenodo Archive**
   - Permanent DOI for citations
   - Restricted access control
   - Version history preserved

3. **Distribution Package**
   - Standalone K2.exe (no Python required)
   - All documentation included
   - Ready to share with collaborators

---

**Questions?** Create an issue on the GitHub repository.
