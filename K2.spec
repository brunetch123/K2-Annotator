# -*- mode: python ; coding: utf-8 -*-
"""
K2 Annotator - PyInstaller Build Specification
Version 3.0.8

Build with: pyinstaller K2.spec --clean
Output: dist/K2/K2.exe (folder mode) or dist/K2.exe (onefile mode)
"""

import os
import sys

block_cipher = None

# Get the directory containing this spec file
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))

# Define data files to include
# Format: (source, destination_folder)
datas = [
    # Icons and images
    ('K2Icon.png', '.'),
    ('K2Logo.png', '.'),
    ('K2Logo2.png', '.'),  # legacy fallback
    
    # Documentation
    ('K2_USER_GUIDE.md', '.'),
    ('README.md', '.'),
    ('CHANGELOG.md', '.'),
    ('QUICK_START.md', '.'),
    
    # Configuration files
    ('config', 'config'),
    
    # User templates
    ('users', 'users'),
    
    # Library templates
    ('templates', 'templates'),
    
    # Source modules (needed for imports)
    ('scripts/src', 'scripts/src'),
    
    # Additional scripts that may be called
    ('scripts/cli.py', 'scripts'),
    ('scripts/gcms_pipeline.py', 'scripts'),
    ('scripts/k2_config.py', 'scripts'),
    ('scripts/k2_screens.py', 'scripts'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    # GUI
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinter.scrolledtext',
    
    # Image processing
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    
    # Data processing
    'pandas',
    'numpy',
    'numpy.core._methods',
    'numpy.lib.format',
    
    # Visualization
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.backends.backend_agg',
    'matplotlib.backends.backend_tkagg',
    
    # PDF generation
    'reportlab',
    'reportlab.lib',
    'reportlab.lib.pagesizes',
    'reportlab.lib.colors',
    'reportlab.pdfgen',
    'reportlab.pdfgen.canvas',
    
    # Chemistry APIs
    'pubchempy',
    'requests',
    
    # EPA CompTox API
    'ctxpy',
    
    # Molecular calculations
    'molmass',
    
    # Standard library
    'json',
    'csv',
    'subprocess',
    'pathlib',
    'datetime',
    'statistics',
    'bisect',
    'xml.etree.ElementTree',
]

# Exclude modules to reduce size (note: don't exclude unittest - pyparsing needs it)
excludes = [
    'test',
    'tests',
    'pytest',
    'IPython',
    'jupyter',
    'notebook',
    'sphinx',
    'docutils',
]

a = Analysis(
    ['scripts/k2_gui.py'],
    pathex=[SPEC_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Option 1: One-folder distribution (recommended for first build)
# Creates dist/K2/ folder with K2.exe and supporting files
# Faster startup, easier debugging
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='K2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True for debugging (shows console window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='K2Icon.ico',  # Windows icon (create from K2Icon.png)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='K2',
)

# Option 2: Single-file executable (uncomment to use instead)
# Creates single dist/K2.exe file
# Slower startup but simpler distribution
# To use: comment out the EXE and COLLECT above, uncomment below:
"""
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='K2Icon.ico',
)
"""
