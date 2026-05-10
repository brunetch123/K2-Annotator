#!/usr/bin/env python3
"""
GC-MS Suspect Screening Pipeline
=================================
Unified pipeline for GC-MS data processing and annotation. Production
testing has been performed against Agilent .D folders; other vendor
formats supported by MSConvert are accepted on a best-effort basis.

Entry points:
  --from-raw     Start from a folder of vendor raw data (full pipeline)
  --from-mzml    Start from mzML files (skip conversion)
  --from-mzmine  Start from MZmine output (library matching only)

Usage:
  python gcms_pipeline.py --from-raw "path/to/D_files"
  python gcms_pipeline.py --from-mzml "path/to/mzML_files"
  python gcms_pipeline.py --from-mzmine "path/to/mzmine_output"
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

# ============================================================================
# Configuration - Edit these paths for your system
# ============================================================================
PIPELINE_ROOT = Path(__file__).resolve().parent.parent  # Auto-detect pipeline root
MSCONVERT = PIPELINE_ROOT / "software" / "pwiz-bin" / "msconvert.exe"
MZMINE = PIPELINE_ROOT / "software" / "mzmine" / "mzmine_console.exe"
USER_FILE = PIPELINE_ROOT / "users" / "default.mzuser"
BATCH_FILE = PIPELINE_ROOT / "config" / "gc_ei_workflow.mzbatch"
TEMP_DIR = PIPELINE_ROOT / "temp"
DEFAULT_LIBRARY = PIPELINE_ROOT / "unified_library_20251013.csv"
SCRIPTS_DIR = PIPELINE_ROOT / "scripts"
DEFAULT_THREADS = 2


def print_header(text):
    """Print a section header."""
    print()
    print("=" * 70)
    print(text)
    print("=" * 70)
    print()


def print_step(step_num, total, description):
    """Print a step indicator."""
    print()
    print(f"[{step_num}/{total}] {description}")
    print("-" * 50)


def _is_cloud_placeholder(path):
    """
    Return True if `path` is a OneDrive (or similar) cloud-only
    placeholder rather than an actually-local file.

    On modern Windows, on-demand cloud files are marked with one of:
      - FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS (0x00400000)  — the
        canonical "this file's data isn't local; reading it will
        trigger the cloud provider" marker used by OneDrive Files
        On-Demand
      - FILE_ATTRIBUTE_RECALL_ON_OPEN (0x00040000)          — older
        recall marker
      - FILE_ATTRIBUTE_OFFLINE (0x1000)                     — legacy
        offline marker, still set by some clients

    Any one of these three is sufficient to know that touching the
    file may fail with WinError 362 if the cloud client isn't
    running. (Note: Python's os.stat() does NOT always report
    REPARSE_POINT for these files even though Win32 does, so we
    can't gate on that bit.)

    On non-Windows hosts the concept doesn't apply and this returns
    False unconditionally.
    """
    if os.name != "nt":
        return False
    try:
        attrs = os.stat(path).st_file_attributes  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False
    RECALL_ON_DATA_ACCESS = 0x00400000
    RECALL_ON_OPEN = 0x00040000
    OFFLINE = 0x00001000
    return bool(attrs & (RECALL_ON_DATA_ACCESS | RECALL_ON_OPEN | OFFLINE))


def validate_tool(path, name):
    """Check that a tool exists AND is locally hydrated.

    A cloud-only placeholder will pass `path.exists()` but Windows
    will fail with `WinError 362: The cloud file provider is not
    running` the moment subprocess.run() tries to launch it (or read
    from it) while OneDrive is offline. Catching that case here turns
    a confusing mid-pipeline crash into a clear up-front error.
    """
    if not path.exists():
        print(f"  [X] {name}: NOT FOUND at {path}")
        return False
    if _is_cloud_placeholder(path):
        print(f"  [X] {name}: cloud-only placeholder at {path}")
        print(f"        The file is synced to a cloud provider "
              f"(e.g. OneDrive) but is not actually present on this")
        print(f"        machine. Either start the cloud client so it "
              f"can hydrate the file on demand, or right-click the")
        print(f"        software folder and choose \"Always keep on "
              f"this device\" to pin all files locally.")
        return False
    print(f"  [OK] {name}: {path}")
    return True


def validate_setup(stages):
    """
    Validate required tools based on which stages will run.
    
    Args:
        stages: list of stages to run ['convert', 'mzmine', 'match']
    """
    print("Validating setup...")
    
    valid = True
    
    if 'convert' in stages:
        valid &= validate_tool(MSCONVERT, "msconvert")
    
    if 'mzmine' in stages:
        valid &= validate_tool(MZMINE, "MZmine")
        valid &= validate_tool(USER_FILE, "User file")
        valid &= validate_tool(BATCH_FILE, "Batch file")
    
    print()
    return valid


def find_raw_data(input_folder):
    """Find vendor raw data files/folders that MSConvert can read.

    Scans for the common GC-MS / LC-MS vendor extensions:
      - .D / .d  (Agilent, Bruker — folder)
      - .raw     (Thermo — file; Waters — folder)
      - .wiff    (Sciex — file)
      - .lcd     (Shimadzu — file)

    MSConvert auto-detects the vendor from the input path, so all of
    these can be passed through unchanged.

    Production testing has only been performed against Agilent .D
    folders; other vendor formats are accepted on a best-effort basis
    via MSConvert's native readers.
    """
    patterns = ("*.D", "*.d", "*.raw", "*.RAW",
                "*.wiff", "*.WIFF", "*.lcd", "*.LCD")
    found = []
    for p in patterns:
        found.extend(input_folder.glob(p))
    # De-duplicate on case-insensitive filesystems where *.D and *.d
    # match the same path twice.
    seen = set()
    unique = []
    for f in sorted(found, key=lambda p: str(p).lower()):
        key = str(f).lower()
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


# Back-compat alias: older code paths called find_d_files() before
# multi-vendor support landed in v3.0.9.
find_d_files = find_raw_data


def find_mzml_files(input_folder):
    """Find all mzML files."""
    return sorted(input_folder.glob("*.mzML"))


def find_mzmine_outputs(input_folder):
    """
    Find MZmine output files (quant CSV and spectra MSP).
    Returns tuple of (quant_file, msp_file) or (None, None) if not found.
    """
    # Look for quant file patterns
    quant_patterns = ["*_quant.csv", "*_iimn_gnps.csv", "*quant*.csv", "*.csv"]
    quant_file = None
    for pattern in quant_patterns:
        matches = list(input_folder.glob(pattern))
        if matches:
            quant_file = matches[0]
            break
    
    # Look for MSP file
    msp_patterns = ["*_spectra.msp", "*.msp"]
    msp_file = None
    for pattern in msp_patterns:
        matches = list(input_folder.glob(pattern))
        if matches:
            msp_file = matches[0]
            break
    
    return quant_file, msp_file


# ============================================================================
# Stage 1: Convert vendor raw data → mzML
# ============================================================================
def run_conversion(input_folder, output_folder):
    """Convert all vendor raw files in the input folder to mzML."""
    output_folder.mkdir(parents=True, exist_ok=True)

    raw_files = find_raw_data(input_folder)
    total = len(raw_files)

    print(f"Converting {total} files to mzML...")
    print(f"Output: {output_folder}")
    print()

    for i, raw_file in enumerate(raw_files, 1):
        print(f"  [{i}/{total}] {raw_file.name}")

        cmd = [
            str(MSCONVERT),
            str(raw_file),
            "-o", str(output_folder),
            "--mzML",
            "--64",
            "--zlib"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as e:
            # WinError 362 = ERROR_CLOUD_FILE_PROVIDER_NOT_RUNNING.
            # The MSConvert binary or one of its dependencies is a
            # cloud-only placeholder and the provider isn't running.
            # Surface a clear actionable message instead of the raw
            # OSError trace.
            if getattr(e, "winerror", None) == 362:
                print(f"    ERROR: Cannot launch MSConvert because a "
                      f"cloud-only placeholder could not be hydrated.")
                print(f"           Either start your cloud client "
                      f"(e.g. OneDrive) so it can fetch the file, or")
                print(f"           pin the software folder locally "
                      f"(\"Always keep on this device\").")
                print(f"           Underlying error: {e}")
                return None
            raise

        if result.returncode != 0:
            print(f"    ERROR: Conversion failed")
            print(result.stderr)
            return None
    
    mzml_count = len(list(output_folder.glob("*.mzML")))
    print()
    print(f"Conversion complete: {mzml_count} mzML files created")
    return output_folder


# ============================================================================
# Stage 2: MZmine Processing
# ============================================================================
def run_mzmine(input_folder, output_folder, output_name, threads):
    """Run MZmine batch processing."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    output_folder.mkdir(parents=True, exist_ok=True)
    
    input_pattern = str(input_folder / "*.mzML")
    output_base = output_folder / output_name
    
    print(f"Input: {input_pattern}")
    print(f"Output: {output_base}")
    print(f"Threads: {threads}")
    print()
    
    cmd = [
        str(MZMINE),
        "-u", str(USER_FILE),
        "-b", str(BATCH_FILE),
        "-i", input_pattern,
        "-o", str(output_base),
        "-memory", "none",
        "-temp", str(TEMP_DIR),
        "-threads", str(threads)
    ]
    
    print("MZmine log (filtered):")
    print("-" * 40)

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
    except OSError as e:
        # WinError 362 = ERROR_CLOUD_FILE_PROVIDER_NOT_RUNNING. Same
        # diagnosis as the MSConvert path: the binary is a OneDrive
        # placeholder and the provider isn't running.
        if getattr(e, "winerror", None) == 362:
            print(f"    ERROR: Cannot launch MZmine because a cloud-only "
                  f"placeholder could not be hydrated.")
            print(f"           Either start your cloud client (e.g. "
                  f"OneDrive) so it can fetch the file, or")
            print(f"           pin the software folder locally "
                  f"(\"Always keep on this device\").")
            print(f"           Underlying error: {e}")
            return None
        raise

    error_lines = []
    for line in process.stdout:
        line = line.rstrip()
        # Always capture SEVERE and ERROR lines in full
        if "SEVERE" in line or "ERROR" in line:
            print(line)  # Print full error line
            error_lines.append(line)
        elif any(level in line for level in ["INFO", "WARNING"]):
            # Truncate other log lines
            if len(line) > 100:
                line = line[:97] + "..."
            print(line)

    process.wait()
    print("-" * 40)

    if process.returncode != 0:
        print("\nERROR: MZmine processing failed")
        if error_lines:
            print("\nError details:")
            for err in error_lines:
                print(f"  {err}")
        return None
    
    print("MZmine processing complete")
    return output_folder


# ============================================================================
# Stage 3: Library Matching
# ============================================================================
def run_library_matching(mzmine_folder, output_folder, project_name, library_file,
                         blank_id, ri_cal=None, api_key=None, grouping=None, is_config=None,
                         surrogate_library=None, surrogate_config=None, reference_samples=None,
                         bff_mode='standard', bff_c_factor=5.0):
    """Run library matching using cli.py."""

    # Find MZmine output files
    quant_file, msp_file = find_mzmine_outputs(mzmine_folder)

    if not quant_file:
        print(f"ERROR: No quantification CSV found in {mzmine_folder}")
        print("  Looked for: *_quant.csv, *_iimn_gnps.csv, *quant*.csv")
        return None

    if not msp_file:
        print(f"ERROR: No MSP file found in {mzmine_folder}")
        return None

    print(f"Quant file: {quant_file.name}")
    print(f"MSP file:   {msp_file.name}")
    print(f"Library:    {library_file}")
    print(f"Blank ID:   '{blank_id}'")
    print(f"BFF Mode:   {bff_mode}")
    print(f"BFF c:      {bff_c_factor}")
    if ri_cal:
        print(f"RI Cal:     {ri_cal}")
    if grouping:
        print(f"Grouping:   {grouping}")
    if is_config:
        print(f"IS Config:  {is_config}")
    if surrogate_library:
        print(f"Surrogate Library: {surrogate_library}")
    if surrogate_config:
        print(f"Surrogate Config:  {surrogate_config}")
    if reference_samples:
        print(f"Reference Samples: {reference_samples}")
    print()
    
    # Check if library exists
    if not library_file.exists():
        print(f"ERROR: Library file not found: {library_file}")
        return None
    
    # Build command for cli.py
    cli_script = SCRIPTS_DIR / "cli.py"
    
    if not cli_script.exists():
        # Try alternate location
        cli_script = SCRIPTS_DIR / "src" / "cli.py"
    
    if not cli_script.exists():
        print(f"ERROR: cli.py not found in {SCRIPTS_DIR}")
        return None
    
    output_folder.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        sys.executable,
        str(cli_script),
        "--quant", str(quant_file),
        "--msp", str(msp_file),
        "--library", str(library_file),
        "--blank-id", blank_id,
        "--bff-mode", bff_mode,
        "--bff-c-factor", str(bff_c_factor),
        "--output", str(output_folder)
    ]
    
    if ri_cal:
        cmd.extend(["--ri-cal", str(ri_cal)])
    
    if api_key:
        cmd.extend(["--api-key", api_key])

    if grouping:
        cmd.extend(["--grouping", str(grouping)])

    if is_config:
        cmd.extend(["--is-config", str(is_config)])

    # v3.0.0: Surrogate recovery parameters
    if surrogate_library:
        cmd.extend(["--surrogate-library", str(surrogate_library)])

    if surrogate_config:
        cmd.extend(["--surrogate-config", str(surrogate_config)])

    if reference_samples:
        cmd.extend(["--reference-samples", str(reference_samples)])

    print("Running library matching...")
    print("-" * 40)
    
    # Run cli.py and stream output
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(SCRIPTS_DIR)  # Run from scripts directory
    )
    
    for line in process.stdout:
        print(line.rstrip())
    
    process.wait()
    print("-" * 40)
    
    if process.returncode != 0:
        print("ERROR: Library matching failed")
        return None
    
    return output_folder


# ============================================================================
# Main Pipeline Logic
# ============================================================================
def run_pipeline(args):
    """Run the pipeline based on entry point."""
    
    # Determine input folder and stages
    if args.from_raw:
        input_folder = Path(args.from_raw)
        stages = ['convert', 'mzmine', 'match']
        input_type = "vendor raw data"
    elif args.from_mzml:
        input_folder = Path(args.from_mzml)
        stages = ['mzmine', 'match']
        input_type = "mzML files"
    elif args.from_mzmine:
        input_folder = Path(args.from_mzmine)
        stages = ['match']
        input_type = "MZmine output"
    else:
        print("ERROR: Must specify --from-raw, --from-mzml, or --from-mzmine")
        return 1
    
    # Validate input folder
    if not input_folder.exists():
        print(f"ERROR: Input folder not found: {input_folder}")
        return 1
    
    # Determine project name
    if args.name:
        project_name = args.name
    else:
        project_name = input_folder.name
        # Clean up name if it's a generic folder
        if project_name.lower() in ['raw', 'raw_data', 'data', 'input']:
            project_name = input_folder.parent.name
    
    # Add timestamp to make unique if not user-specified
    if not args.name:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        run_name = f"{project_name}_{timestamp}"
    else:
        run_name = project_name
    
    # Resolve library path
    library_file = Path(args.library) if args.library else DEFAULT_LIBRARY
    
    # Print header
    print_header("GC-MS Suspect Screening Pipeline")

    print(f"Input:        {input_folder}")
    print(f"Input type:   {input_type}")
    print(f"Project name: {project_name}")
    print(f"Run name:     {run_name}")
    print(f"Stages:       {' -> '.join(stages)}")
    print(f"Threads:      {args.threads}")
    if 'match' in stages:
        print(f"Library:      {library_file}")
        print(f"Blank ID:     '{args.blank_id}'")
        print(f"BFF Mode:     {args.bff_mode}")
        print(f"BFF c-factor: {getattr(args, 'bff_c_factor', 5.0)}")
    
    # Validate setup
    print()
    if not validate_setup(stages):
        print("Setup validation failed. Please check paths.")
        return 1
    
    # Count input files
    if 'convert' in stages:
        raw_files = find_raw_data(input_folder)
        if not raw_files:
            print(f"ERROR: No vendor raw data files found in {input_folder} "
                  f"(looked for .D, .d, .raw, .wiff, .lcd)")
            return 1
        print(f"Found {len(raw_files)} raw input file(s)")
    elif 'mzmine' in stages:
        mzml_files = find_mzml_files(input_folder)
        if not mzml_files:
            print(f"ERROR: No .mzML files found in {input_folder}")
            return 1
        print(f"Found {len(mzml_files)} mzML files")
    else:
        quant, msp = find_mzmine_outputs(input_folder)
        if not quant or not msp:
            print(f"ERROR: MZmine output files not found in {input_folder}")
            return 1
        print(f"Found MZmine outputs: {quant.name}, {msp.name}")
    
    # Define output directories
    # Use output argument if provided, otherwise default to PIPELINE_ROOT
    if args.output:
        base_output = Path(args.output)
    else:
        base_output = PIPELINE_ROOT

    converted_dir = base_output / "converted" / run_name
    mzmine_dir = base_output / "mzmine_output" / run_name
    results_dir = base_output / "results" / run_name
    
    total_steps = len(stages)
    current_step = 0
    
    # ========================================================================
    # Stage 1: Conversion
    # ========================================================================
    if 'convert' in stages:
        current_step += 1
        print_step(current_step, total_steps, "Converting raw data to mzML")
        
        result = run_conversion(input_folder, converted_dir)
        if result is None:
            return 1
        
        mzml_input = converted_dir
    else:
        mzml_input = input_folder
    
    # ========================================================================
    # Stage 2: MZmine Processing
    # ========================================================================
    if 'mzmine' in stages:
        current_step += 1
        print_step(current_step, total_steps, "Processing with MZmine")
        
        result = run_mzmine(mzml_input, mzmine_dir, run_name, args.threads)
        if result is None:
            return 1
        
        mzmine_output = mzmine_dir
    else:
        mzmine_output = input_folder
    
    # ========================================================================
    # Stage 3: Library Matching
    # ========================================================================
    if 'match' in stages:
        current_step += 1
        print_step(current_step, total_steps, "Running library matching")
        
        ri_cal = Path(args.ri_cal) if args.ri_cal else None
        
        result = run_library_matching(
            mzmine_folder=mzmine_output,
            output_folder=results_dir,
            project_name=project_name,
            library_file=library_file,
            blank_id=args.blank_id,
            ri_cal=ri_cal,
            api_key=args.api_key,
            grouping=args.grouping,
            is_config=args.is_config if hasattr(args, 'is_config') else None,
            surrogate_library=args.surrogate_library if hasattr(args, 'surrogate_library') else None,
            surrogate_config=args.surrogate_config if hasattr(args, 'surrogate_config') else None,
            reference_samples=args.reference_samples if hasattr(args, 'reference_samples') else None,
            bff_mode=getattr(args, 'bff_mode', 'standard'),
            bff_c_factor=getattr(args, 'bff_c_factor', 5.0)
        )
        if result is None:
            return 1
    
    # ========================================================================
    # Complete
    # ========================================================================
    print_header("Pipeline Complete!")
    
    print("Output locations:")
    if 'convert' in stages:
        print(f"  Converted mzML: {converted_dir}")
    if 'mzmine' in stages:
        print(f"  MZmine output:  {mzmine_dir}")
    if 'match' in stages:
        print(f"  Results:        {results_dir}")
    
    # List result files
    if 'match' in stages and results_dir.exists():
        print()
        print("Result files:")
        for f in sorted(results_dir.glob("*.*")):
            print(f"  {f.name}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="GC-MS Suspect Screening Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Entry Points:
  --from-raw     Full pipeline: raw -> mzML -> MZmine -> Library Matching
  --from-mzml    Skip conversion: mzML -> MZmine -> Library Matching
  --from-mzmine  Matching only: MZmine output -> Library Matching

Examples:
  # Full pipeline from vendor raw data
  python gcms_pipeline.py --from-raw "X:\\Data\\Project\\raw_data"

  # Start from mzML files
  python gcms_pipeline.py --from-mzml "X:\\Data\\Project\\converted" --threads 4

  # Just run library matching on existing MZmine output
  python gcms_pipeline.py --from-mzmine "X:\\Data\\Project\\mzmine_output\\run_001"

  # Specify project name and custom library
  python gcms_pipeline.py --from-raw "X:\\Data\\raw" --name "NYC_Winter_2024" \\
                          --library "X:\\Libraries\\custom_lib.csv"
        """
    )
    
    # Entry point arguments (mutually exclusive)
    entry = parser.add_mutually_exclusive_group(required=True)
    entry.add_argument(
        '--from-raw', '-r',
        metavar='FOLDER',
        help='Start from folder containing vendor raw data '
             '(Agilent .D / Bruker .d folders, Thermo .raw files, '
             'Sciex .wiff files, Shimadzu .lcd files)'
    )
    entry.add_argument(
        '--from-mzml', '-m',
        metavar='FOLDER',
        help='Start from folder containing mzML files'
    )
    entry.add_argument(
        '--from-mzmine', '-z',
        metavar='FOLDER',
        help='Start from folder containing MZmine output (quant CSV + MSP)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--name', '-n',
        type=str,
        default=None,
        help='Project name (default: input folder name + timestamp)'
    )
    
    parser.add_argument(
        '--threads', '-t',
        type=int,
        default=DEFAULT_THREADS,
        help=f'Number of MZmine threads (default: {DEFAULT_THREADS})'
    )
    
    parser.add_argument(
        '--library', '-l',
        type=str,
        default=None,
        help=f'Library file path (default: {DEFAULT_LIBRARY.name})'
    )
    
    parser.add_argument(
        '--blank-id', '-b',
        type=str,
        default='fieldblank',
        help='String to identify blank samples (default: "fieldblank")'
    )

    parser.add_argument(
        '--bff-mode',
        choices=['standard', 'adjusted'],
        default='standard',
        help='BFF rule: "standard" (legacy mean+3SD) or "adjusted" (Shapiro-gated MAD-based '
             'rule, robust to non-normal blanks). Default: standard.'
    )

    parser.add_argument(
        '--bff-c-factor',
        type=float,
        default=5.0,
        help='Multiplier on the BFF threshold rule (e.g. 5 -> 5*(mean+3SD)). '
             'Default: 5.0 (legacy). Lower values (1, 2) relax the filter.'
    )


    parser.add_argument(
        '--ri-cal',
        type=str,
        default=None,
        help='RI calibration file (tab-delimited: Carbon number, RT)'
    )
    
    parser.add_argument(
        '--api-key', '-k',
        type=str,
        default=None,
        help='EPA CompTox API key for toxicity data (optional)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output base directory (default: pipeline root)'
    )
    
    parser.add_argument(
        '--grouping',
        type=str,
        default=None,
        help='JSON file containing sample grouping info'
    )

    parser.add_argument(
        '--is-config',
        type=str,
        default=None,
        help='JSON file containing IS normalization configuration (v2.6.0)'
    )

    # Surrogate Standard Recovery (v3.0.0)
    parser.add_argument(
        '--surrogate-library',
        type=str,
        default=None,
        help='Path to surrogate standard library (CSV/MSP)'
    )

    parser.add_argument(
        '--surrogate-config',
        type=str,
        default=None,
        help='JSON file with surrogate configuration (spiked samples, ratios, groups)'
    )

    parser.add_argument(
        '--reference-samples',
        type=str,
        default=None,
        help='Comma-separated list of reference sample names to exclude from suspect screening'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    # External-tool path overrides. These let the GUI (or a CLI user
    # who keeps tools elsewhere) point the pipeline at MSConvert,
    # MZmine, the MZmine user profile, and the MZmine batch file
    # explicitly. Without these flags the pipeline falls back to its
    # bundled-relative defaults, which is wrong on any install where
    # the user moved or replaced the software/ directory.
    parser.add_argument(
        '--msconvert',
        type=str,
        default=None,
        metavar='PATH',
        help='Path to msconvert.exe (overrides bundled default)'
    )
    parser.add_argument(
        '--mzmine',
        type=str,
        default=None,
        metavar='PATH',
        help='Path to mzmine_console.exe (overrides bundled default)'
    )
    parser.add_argument(
        '--user-file',
        type=str,
        default=None,
        metavar='PATH',
        help='Path to MZmine .mzuser profile (overrides bundled default)'
    )
    parser.add_argument(
        '--batch-file',
        type=str,
        default=None,
        metavar='PATH',
        help='Path to MZmine .mzbatch workflow (overrides bundled default)'
    )

    args = parser.parse_args()

    # Apply tool-path overrides. We rebind the module-level constants
    # so existing call sites (validate_setup / run_conversion /
    # run_mzmine_processing) pick them up without further plumbing.
    global MSCONVERT, MZMINE, USER_FILE, BATCH_FILE
    if args.msconvert:
        MSCONVERT = Path(args.msconvert)
    if args.mzmine:
        MZMINE = Path(args.mzmine)
    if args.user_file:
        USER_FILE = Path(args.user_file)
    if args.batch_file:
        BATCH_FILE = Path(args.batch_file)

    try:
        return run_pipeline(args)
    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n\nERROR: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
