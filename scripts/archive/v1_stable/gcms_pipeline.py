#!/usr/bin/env python3
"""
GC-MS Suspect Screening Pipeline
=================================
Unified pipeline for Agilent GC-QTOF data processing and annotation.

Entry points:
  --from-raw     Start from Agilent .D files (full pipeline)
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
USER_FILE = PIPELINE_ROOT / "users" / "brunetch.mzuser"
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


def validate_tool(path, name):
    """Check if a tool exists."""
    if not path.exists():
        print(f"  [X] {name}: NOT FOUND at {path}")
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


def find_d_files(input_folder):
    """Find all Agilent .D folders."""
    d_files = sorted(input_folder.glob("*.D"))
    if not d_files:
        d_files = sorted(input_folder.glob("*.d"))
    return d_files


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
# Stage 1: Convert .D to mzML
# ============================================================================
def run_conversion(input_folder, output_folder):
    """Convert all .D files to mzML format."""
    output_folder.mkdir(parents=True, exist_ok=True)
    
    d_files = find_d_files(input_folder)
    total = len(d_files)
    
    print(f"Converting {total} files to mzML...")
    print(f"Output: {output_folder}")
    print()
    
    for i, d_file in enumerate(d_files, 1):
        print(f"  [{i}/{total}] {d_file.name}")
        
        cmd = [
            str(MSCONVERT),
            str(d_file),
            "-o", str(output_folder),
            "--mzML",
            "--64",
            "--zlib"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
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

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

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
                         blank_id, ri_cal=None, api_key=None, grouping=None, avg_reps=False):
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
    if ri_cal:
        print(f"RI Cal:     {ri_cal}")
    if grouping:
        print(f"Grouping:   {grouping}")
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
        "--output", str(output_folder)
    ]
    
    if ri_cal:
        cmd.extend(["--ri-cal", str(ri_cal)])
    
    if api_key:
        cmd.extend(["--api-key", api_key])

    if grouping:
        cmd.extend(["--grouping", str(grouping)])
    
    if avg_reps:
        cmd.append("--avg-reps")
    
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
        input_type = "Agilent .D files"
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
    
    # Validate setup
    print()
    if not validate_setup(stages):
        print("Setup validation failed. Please check paths.")
        return 1
    
    # Count input files
    if 'convert' in stages:
        d_files = find_d_files(input_folder)
        if not d_files:
            print(f"ERROR: No .D files found in {input_folder}")
            return 1
        print(f"Found {len(d_files)} .D files")
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
        print_step(current_step, total_steps, "Converting .D files to mzML")
        
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
            avg_reps=args.avg_reps
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
  --from-raw     Full pipeline: .D -> mzML -> MZmine -> Library Matching
  --from-mzml    Skip conversion: mzML -> MZmine -> Library Matching
  --from-mzmine  Matching only: MZmine output -> Library Matching

Examples:
  # Full pipeline from raw Agilent data
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
        help='Start from folder containing Agilent .D files'
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
        '--avg-reps',
        action='store_true',
        help='Average replicates for statistics'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
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
