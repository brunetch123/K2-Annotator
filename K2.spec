# -*- mode: python ; coding: utf-8 -*-
"""
K2 Annotator - PyInstaller Build Specification
Version 3.1.1

Build with: pyinstaller K2.spec --clean
Output: dist/K2/K2.exe (folder mode) or dist/K2.exe (onefile mode)

v3.1.0: the frozen GUI runs gcms_pipeline and cli.py IN-PROCESS (there is
no python.exe to spawn inside a bundle), so those modules and everything
under scripts/src must be analysed by PyInstaller. scripts/ is on pathex
and the modules are listed as hidden imports below.
"""

import os
import sys

block_cipher = None

# Get the directory containing this spec file
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
SCRIPTS_DIR = os.path.join(SPEC_DIR, 'scripts')

# Windows icon is optional: only pass icon= when the .ico actually exists
# (create it from K2Icon.png if you want one).
ICON_FILE = os.path.join(SPEC_DIR, 'K2Icon.ico')
EXE_ICON = ICON_FILE if os.path.exists(ICON_FILE) else None

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
    
    # Source copies of the pipeline scripts. The modules themselves are
    # compiled into the bundle via hiddenimports; these plain copies are
    # kept so gcms_pipeline's SCRIPTS_DIR (= sys._MEIPASS/scripts) exists
    # and users can read the code that ran.
    ('scripts/src', 'scripts/src'),
    ('scripts/cli.py', 'scripts'),
    ('scripts/gcms_pipeline.py', 'scripts'),
    ('scripts/k2_config.py', 'scripts'),
    ('scripts/k2_screens.py', 'scripts'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    # Pipeline modules executed in-process by the frozen GUI (v3.1.0)
    'gcms_pipeline',
    'cli',
    'k2_config',
    'k2_screens',
    'src',
    'src.matching_engine',
    'src.reporter',
    'src.summary_tables',
    'src.surrogate_analyzer',
    'src.surrogate_reporter',
    'src.structure_helper',
    'src.ctx_client',
    'src.http_session',
    'src.is_normalizer',
    'src.library_parser',
    'src.universal_parser',
    'src.ri_calibration',
    'src.rhrmf',
    'src.spectral_math',
    'src.msp_reader',
    'src.run_manifest',
    'src.version',

    # Scientific stack used by the matching engine
    'scipy',
    'scipy.interpolate',
    'scipy.stats',
    'scipy.special',
    'scipy.linalg',

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
    pathex=[SPEC_DIR, SCRIPTS_DIR],
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
    icon=EXE_ICON,  # Windows icon (optional; None when K2Icon.ico is absent)
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
    icon=EXE_ICON,
)
"""
