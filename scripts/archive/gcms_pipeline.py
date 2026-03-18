#!/usr/bin/env python3
"""
GC-MS Non-Target Analysis Pipeline
Converts Agilent .D files to mzML and processes through MZmine.

Usage:
    python gcms_pipeline.py <input_folder> [--output-name NAME] [--threads N]
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# ============================================================================
# Configuration - Edit these paths for your system
# ============================================================================
PIPELINE_ROOT = Path(r"X:\Data\ChrisB\Non-Target\gcms_pipeline")
MSCONVERT = Path(r"C:\Users\cbrunet\AppData\Local\OpenMS-3.1.0\share\OpenMS\THIRDPARTY\pwiz-bin\msconvert.exe")
MZMINE = PIPELINE_ROOT / "software" / "mzmine" / "mzmine_console.exe"
USER_FILE = PIPELINE_ROOT / "users" / "brunetch.mzuser"
BATCH_FILE = PIPELINE_ROOT / "config" / "gc_ei_workflow.mzbatch"
TEMP_DIR = PIPELINE_ROOT / "temp"
DEFAULT_THREADS = 2


def print_header(text):
    """Print a section header."""
    print()
    print("=" * 60)
    print(text)
    print("=" * 60)
    print()


def validate_setup():
    """Check that all required tools exist."""
    print("Validating setup...")
    
    errors = []
    if not MSCONVERT.exists():
        errors.append(f"  ERROR: msconvert not found: {MSCONVERT}")
    else:
        print(f"  ✓ msconvert: {MSCONVERT}")
    
    if not MZMINE.exists():
        errors.append(f"  ERROR: MZmine not found: {MZMINE}")
    else:
        print(f"  ✓ MZmine: {MZMINE}")
    
    if not USER_FILE.exists():
        errors.append(f"  ERROR: User file not found: {USER_FILE}")
    else:
        print(f"  ✓ User file: {USER_FILE}")
    
    if not BATCH_FILE.exists():
        errors.append(f"  ERROR: Batch file not found: {BATCH_FILE}")
    else:
        print(f"  ✓ Batch file: {BATCH_FILE}")
    
    if errors:
        print()
        for e in errors:
            print(e)
        return False
    
    print()
    return True


def find_d_files(input_folder):
    """Find all Agilent .D folders."""
    d_files = sorted(input_folder.glob("*.D"))
    if not d_files:
        d_files = sorted(input_folder.glob("*.d"))
    return d_files


def convert_to_mzml(input_folder, output_folder):
    """Convert all .D files to mzML."""
    output_folder.mkdir(parents=True, exist_ok=True)
    
    d_files = find_d_files(input_folder)
    total = len(d_files)
    
    print(f"Converting {total} files to mzML...")
    print(f"Output: {output_folder}")
    print()
    
    for i, d_file in enumerate(d_files, 1):
        print(f"[{i}/{total}] {d_file.name}")
        
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
            print(f"  ERROR: Conversion failed")
            print(result.stderr)
            return False
    
    # Count output files
    mzml_count = len(list(output_folder.glob("*.mzML")))
    print()
    print(f"Conversion complete: {mzml_count} mzML files created")
    return True


def run_mzmine(input_folder, output_base, threads):
    """Run MZmine batch processing."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    output_base.parent.mkdir(parents=True, exist_ok=True)
    
    input_pattern = str(input_folder / "*.mzML")
    
    print(f"Input: {input_pattern}")
    print(f"Output: {output_base}")
    print(f"Threads: {threads}")
    print()
    print("MZmine processing output:")
    print("-" * 40)
    
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
    
    # Run and stream output to console
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    for line in process.stdout:
        # Print INFO, WARNING, SEVERE lines
        if any(level in line for level in ["INFO", "WARNING", "SEVERE", "ERROR"]):
            print(line.rstrip())
    
    process.wait()
    
    print("-" * 40)
    
    if process.returncode != 0:
        print("ERROR: MZmine processing failed")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="GC-MS Non-Target Analysis Pipeline"
    )
    parser.add_argument(
        "input_folder",
        type=Path,
        help="Folder containing Agilent .D files"
    )
    parser.add_argument(
        "--output-name", "-o",
        type=str,
        default=None,
        help="Name for output folders (default: timestamp)"
    )
    parser.add_argument(
        "--threads", "-t",
        type=int,
        default=DEFAULT_THREADS,
        help=f"Number of threads (default: {DEFAULT_THREADS})"
    )
    
    args = parser.parse_args()
    
    # Generate output name
    if args.output_name:
        output_name = args.output_name
    else:
        output_name = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print_header("GC-MS Non-Target Analysis Pipeline")
    
    # Validate
    if not validate_setup():
        print("Setup validation failed. Please check paths in the script.")
        return 1
    
    # Check input
    input_folder = args.input_folder
    if not input_folder.exists():
        print(f"ERROR: Input folder not found: {input_folder}")
        return 1
    
    d_files = find_d_files(input_folder)
    if not d_files:
        print(f"ERROR: No .D files found in {input_folder}")
        return 1
    
    print(f"Input folder: {input_folder}")
    print(f"Found {len(d_files)} .D files")
    print(f"Output name: {output_name}")
    
    # Setup output paths
    converted_dir = PIPELINE_ROOT / "converted" / output_name
    mzmine_output = PIPELINE_ROOT / "mzmine_output" / output_name
    
    # Step 1: Convert
    print_header("Step 1: Converting .D files to mzML")
    
    if not convert_to_mzml(input_folder, converted_dir):
        return 1
    
    # Step 2: MZmine
    print_header("Step 2: Processing with MZmine")
    
    output_base = mzmine_output / output_name
    if not run_mzmine(converted_dir, output_base, args.threads):
        return 1
    
    # Done
    print_header("Pipeline Complete!")
    
    print(f"Results saved to: {mzmine_output}")
    print()
    print("Output files:")
    for f in sorted(mzmine_output.glob("*.*")):
        print(f"  {f.name}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
