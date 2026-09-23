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
import inspect
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

# ============================================================================
# Configuration - Edit these paths for your system
# ============================================================================
if getattr(sys, 'frozen', False):
    # v3.1.0: inside a PyInstaller bundle the bundled scripts/ and src/
    # copies live under sys._MEIPASS, not two levels above this module.
    PIPELINE_ROOT = Path(sys._MEIPASS)
else:
    PIPELINE_ROOT = Path(__file__).resolve().parent.parent  # Auto-detect pipeline root
MSCONVERT = PIPELINE_ROOT / "software" / "pwiz-bin" / "msconvert.exe"
MZMINE = PIPELINE_ROOT / "software" / "mzmine" / "mzmine_console.exe"
USER_FILE = PIPELINE_ROOT / "users" / "default.mzuser"
BATCH_FILE = PIPELINE_ROOT / "config" / "gc_ei_workflow.mzbatch"
TEMP_DIR = PIPELINE_ROOT / "temp"
DEFAULT_LIBRARY = PIPELINE_ROOT / "unified_library_20251013.csv"
SCRIPTS_DIR = PIPELINE_ROOT / "scripts"
DEFAULT_THREADS = 2

# Exit code returned when the run completed but cli.py found zero Level-2
# matches (summaries are still written). Mirrors cli.py's own exit code.
EXIT_NO_MATCHES = 2

# Environment variable through which the EPA CompTox API key is handed to
# cli.py (v3.1.0). Never placed on a command line so it cannot leak into
# process listings, GUI console echoes or log files.
API_KEY_ENV = "K2_EPA_API_KEY"


# ============================================================================
# v3.1.0 plumbing helpers: log tee, cancellation, process-tree kill,
# command redaction, name sanitising, unique output directories.
# ============================================================================
class _Tee:
    """Minimal file-like object that fans writes out to several sinks.

    Sinks may be file objects (anything with .write) or plain callables
    (called with the text chunk). A sink of None is ignored, which covers
    PyInstaller windowed builds where sys.stdout is None.
    """

    def __init__(self, *sinks):
        self._sinks = [s for s in sinks if s is not None]
        self._lock = threading.Lock()

    def write(self, text):
        if not text:
            return 0
        with self._lock:
            for sink in self._sinks:
                try:
                    if callable(sink) and not hasattr(sink, 'write'):
                        sink(text)
                    else:
                        sink.write(text)
                except Exception:
                    pass
        return len(text)

    def flush(self):
        for sink in self._sinks:
            try:
                if hasattr(sink, 'flush'):
                    sink.flush()
            except Exception:
                pass

    def isatty(self):
        return False

    @property
    def encoding(self):
        return 'utf-8'


class _StdoutRedirect:
    """Context manager: route sys.stdout/sys.stderr through a _Tee that
    also feeds `extra` (a file object or callable), restoring on exit."""

    def __init__(self, extra):
        self._extra = extra
        self._saved = None

    def __enter__(self):
        self._saved = (sys.stdout, sys.stderr)
        sys.stdout = _Tee(self._saved[0], self._extra)
        sys.stderr = _Tee(self._saved[1], self._extra)
        return self

    def __exit__(self, *exc):
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        sys.stdout, sys.stderr = self._saved
        return False


# Cancellation support for in-process (frozen GUI) runs: the GUI cannot
# kill a thread, so it sets this event and we kill whatever external tool
# is currently running and stop between stages.
_CANCEL = threading.Event()
_CHILDREN = set()
_CHILDREN_LOCK = threading.Lock()


def _register_child(proc):
    with _CHILDREN_LOCK:
        _CHILDREN.add(proc)


def _unregister_child(proc):
    with _CHILDREN_LOCK:
        _CHILDREN.discard(proc)


def kill_process_tree(proc):
    """Kill `proc` and every descendant.

    Windows: `taskkill /T /F` walks the tree (MZmine spawns a JVM, MSConvert
    may spawn helpers). Elsewhere: os.killpg on the process group, which is
    why callers launch children with start_new_session=True.
    """
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == 'nt':
            subprocess.run(
                ['taskkill', '/T', '/F', '/PID', str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def request_cancel():
    """Ask a running in-process pipeline to stop (used by the frozen GUI)."""
    _CANCEL.set()
    with _CHILDREN_LOCK:
        children = list(_CHILDREN)
    for proc in children:
        kill_process_tree(proc)


def _reset_cancel():
    _CANCEL.clear()


def _popen_kwargs():
    """Popen keyword arguments so a child (and its descendants) can be
    killed as a tree by kill_process_tree()."""
    if os.name == 'nt':
        return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    return {'start_new_session': True}


def redact_command(cmd):
    """Return a copy-pasteable command string with secrets masked.

    Uses subprocess.list2cmdline so arguments containing spaces are quoted
    exactly as the shell needs them. Any value following --api-key / -k is
    replaced by '***'.
    """
    cmd = [str(c) for c in cmd]
    out = []
    mask_next = False
    for tok in cmd:
        if mask_next:
            out.append('***')
            mask_next = False
        elif tok in ('--api-key', '-k'):
            out.append(tok)
            mask_next = True
        elif tok.startswith('--api-key='):
            out.append('--api-key=***')
        else:
            out.append(tok)
    return subprocess.list2cmdline(out)


def sanitise_name(name):
    """Make `name` safe as a single path component.

    Characters outside [A-Za-z0-9._-] become '_'. A name that sanitises to
    nothing (or only dots) becomes 'run'.
    """
    cleaned = re.sub(r'[^A-Za-z0-9._-]', '_', str(name).strip())
    if not cleaned or set(cleaned) <= {'.'}:
        cleaned = 'run'
    return cleaned


def unique_run_name(base_output, run_name, stages):
    """Return `run_name`, or `run_name_2`, `run_name_3`, ... — the first
    variant for which none of the stage output directories already exist.

    Never overwrites an earlier run: the GUI always passes --name, so
    without this a re-run would silently clobber results/<name>.
    """
    def _dirs(candidate):
        dirs = [base_output / "results" / candidate]
        if 'convert' in stages:
            dirs.append(base_output / "converted" / candidate)
        if 'mzmine' in stages:
            dirs.append(base_output / "mzmine_output" / candidate)
        return dirs

    if not any(d.exists() for d in _dirs(run_name)):
        return run_name
    n = 2
    while any(d.exists() for d in _dirs(f"{run_name}_{n}")):
        n += 1
    return f"{run_name}_{n}"


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
    # v3.1.0: glob order is filesystem-dependent, so pick deterministically:
    # newest file first (by mtime, name as tie-break) and warn when the
    # choice was ambiguous.
    def _pick(patterns, label):
        for pattern in patterns:
            matches = list(input_folder.glob(pattern))
            if not matches:
                continue
            matches.sort(key=lambda p: (p.stat().st_mtime, p.name),
                         reverse=True)
            if len(matches) > 1:
                print(f"  WARNING: {len(matches)} candidate {label} files "
                      f"match '{pattern}' in {input_folder}; using the "
                      f"newest: {matches[0].name}", flush=True)
                for other in matches[1:]:
                    print(f"           (ignored: {other.name})", flush=True)
            return matches[0]
        return None

    quant_file = _pick(["*_quant.csv", "*_iimn_gnps.csv", "*quant*.csv", "*.csv"],
                       "quant CSV")
    msp_file = _pick(["*_spectra.msp", "*.msp"], "MSP")

    return quant_file, msp_file


# ============================================================================
# Stage 1: Convert vendor raw data → mzML
# ============================================================================
def run_conversion(input_folder, output_folder, stage_locally=True):
    """Convert all vendor raw files in the input folder to mzML.

    `stage_locally` (default True): convert into a local scratch
    directory first, then move the finished `.mzML` to
    `output_folder`. MSConvert writes the output file incrementally
    with fsyncs; doing that directly against a slow network share
    (Z:, SMB, VPN-mounted) can stretch a sub-minute conversion into
    many hours. Staging to local disk makes the slow part one
    bulk-copy at the end instead of many tiny synchronous writes.

    Set `stage_locally=False` (or pass `--no-stage-locally` on the
    CLI) to write directly to `output_folder` — only worth doing if
    the output is already on a fast local disk.
    """
    output_folder.mkdir(parents=True, exist_ok=True)

    raw_files = find_raw_data(input_folder)
    total = len(raw_files)

    if stage_locally:
        # Anchor the scratch dir under the system temp drive (usually
        # C:\Users\<user>\AppData\Local\Temp) so we are guaranteed a
        # fast local filesystem regardless of where output_folder is.
        stage_root = Path(tempfile.mkdtemp(prefix="k2_msconvert_"))
        print(f"Converting {total} files to mzML...", flush=True)
        print(f"  Staging directory: {stage_root}", flush=True)
        print(f"  Final output:      {output_folder}", flush=True)
        print(flush=True)
    else:
        stage_root = None
        print(f"Converting {total} files to mzML (direct write)...",
              flush=True)
        print(f"Output: {output_folder}", flush=True)
        print(flush=True)

    try:
        for i, raw_file in enumerate(raw_files, 1):
            print(f"  [{i}/{total}] {raw_file.name}", flush=True)

            # Per-file staging dir keeps the move loop simple — at the
            # end of each conversion, whatever .mzML files appear in
            # this folder are the ones MSConvert just produced.
            if stage_locally:
                write_dir = stage_root / f"_run_{i:04d}"
                write_dir.mkdir(parents=True, exist_ok=True)
            else:
                write_dir = output_folder

            cmd = [
                str(MSCONVERT),
                str(raw_file),
                "-o", str(write_dir),
                "--mzML",
                "--64",
                "--zlib"
            ]

            # Stream MSConvert output line-by-line rather than
            # capturing it to a buffer; we want live progress.
            if _CANCEL.is_set():
                print("    Cancelled.", flush=True)
                return None

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    **_popen_kwargs(),
                )
            except OSError as e:
                if getattr(e, "winerror", None) == 362:
                    print(f"    ERROR: Cannot launch MSConvert because "
                          f"a cloud-only placeholder could not be "
                          f"hydrated.", flush=True)
                    print(f"           Either start your cloud client "
                          f"(e.g. OneDrive) so it can fetch the file, or",
                          flush=True)
                    print(f"           pin the software folder locally "
                          f"(\"Always keep on this device\").", flush=True)
                    print(f"           Underlying error: {e}", flush=True)
                    return None
                raise

            _register_child(proc)
            try:
                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        print(f"    [msconvert] {line}", flush=True)
                proc.wait()
            finally:
                _unregister_child(proc)

            if _CANCEL.is_set():
                print("    Cancelled.", flush=True)
                return None

            if proc.returncode != 0:
                print(f"    ERROR: Conversion failed (exit code "
                      f"{proc.returncode})", flush=True)
                return None

            # Move what MSConvert just produced to the real output dir.
            if stage_locally:
                produced = sorted(write_dir.glob("*.mzML"))
                if not produced:
                    print(f"    WARNING: MSConvert reported success "
                          f"but produced no .mzML for {raw_file.name}",
                          flush=True)
                for mzml in produced:
                    final_path = output_folder / mzml.name
                    size_mb = mzml.stat().st_size / (1024 * 1024)
                    print(f"    [copy] {mzml.name} ({size_mb:.1f} MB) "
                          f"-> {output_folder}", flush=True)
                    # shutil.move falls back to copy+remove when the
                    # source and destination are on different volumes,
                    # which is exactly our case (local scratch -> Z:).
                    shutil.move(str(mzml), str(final_path))
                # Drop the now-empty per-file scratch dir.
                try:
                    write_dir.rmdir()
                except OSError:
                    pass
    finally:
        # Always clean up the staging root, even on failure.
        if stage_locally and stage_root and stage_root.exists():
            shutil.rmtree(stage_root, ignore_errors=True)
    
    mzml_count = len(list(output_folder.glob("*.mzML")))
    print()
    print(f"Conversion complete: {mzml_count} mzML files created")
    return output_folder


# ============================================================================
# Stage 2: MZmine Processing
# ============================================================================
def run_mzmine(input_folder, output_folder, output_name, threads,
               mzmine_temp=None, memory_mode="none", import_threads=None,
               log_file=None):
    """Run MZmine batch processing.

    `log_file` (optional Path, v3.1.0): the complete, unfiltered MZmine
    stdout/stderr is written here (the console only shows a filtered
    view). The GUI passes <results_dir>/mzmine_log.txt.

    Parameters that matter for the import-stability story:

    `mzmine_temp` (optional Path): scratch directory MZmine uses for
    its memory-mapped intermediate files. If None, a fresh per-run
    subdirectory of the system temp dir is created and removed on
    exit. Default avoids cloud-synced paths so OneDrive's filter
    driver can't interfere with Java NIO memory mapping.

    `memory_mode` (str): forwarded to MZmine's `-memory` flag.
    MZmine 4.x's `KeepInMemory.parse()` accepts:
      * "none"            — nothing memory-mapped, all in JVM heap
        (MZmine's own default; highest heap pressure)
      * "all"             — everything memory-mapped to disk (lowest
        heap pressure; safest on small Windows page files)
      * "masses_features" — mass lists + features mapped to disk,
        raw scans in heap
      * "features"        — only features mapped
      * "centroids"       — only mass lists mapped (alias for
        MZmine's MASS_LISTS)
      * "raw"             — only raw scans mapped
    NOTE: pre-v3.0.18 versions of this pipeline defaulted to "mass",
    which is NOT a valid value in MZmine 4 — `KeepInMemory.parse`
    throws `IllegalStateException`, MZmine logs a non-fatal WARNING
    ("Issue while reading keep in memory option from CLI argument"),
    falls back to NONE internally, then exits with code 1 a few
    steps later. We now default to "none" to match MZmine's own
    fallback. If you hit JVM commit-memory failures on a Windows
    machine with a small page file, try "all" or "masses_features".

    `import_threads` (int or None, default None): optional cap on
    `-threads` for the duration of MZmine's run. Concurrent mzML import
    threads share the same rotating `mzmine.tmp` scratch file; when one
    thread rotates the file mid-write, the other thread's mmap is
    invalidated and the JVM faults inside `Unsafe`. Passing 1 here
    serialises the import, which is dramatically more stable on Windows,
    at a small speed cost (mzML parse is I/O-bound). MZmine does not let
    us split import/post-import thread counts on the CLI, so the cap
    applies to the whole run: we pass `min(threads, import_threads)`.
    With None (the default since v3.1.0) `threads` is used unchanged —
    previously the default of 1 silently overrode the requested thread
    count, so the GUI's "Thread Count" had no effect.
    """
    output_folder.mkdir(parents=True, exist_ok=True)

    # Resolve the MZmine scratch directory:
    #   - If the caller passed an explicit path, use it (and create
    #     it). This is the override path for users who know what
    #     they're doing.
    #   - Otherwise, make a fresh per-run temp dir under the
    #     guaranteed-local system temp, and clean it up on exit.
    if mzmine_temp is not None:
        mzmine_scratch = Path(mzmine_temp)
        mzmine_scratch.mkdir(parents=True, exist_ok=True)
        scratch_is_owned = False
        # Warn loudly if an explicitly-passed path looks like a
        # cloud-synced location.
        scratch_str = str(mzmine_scratch).lower()
        if "onedrive" in scratch_str or "dropbox" in scratch_str:
            print(f"  WARNING: MZmine scratch directory {mzmine_scratch} "
                  f"looks like a cloud-synced path. MZmine uses memory-"
                  f"mapped files there, and cloud filter drivers can "
                  f"cause java.lang.InternalError on import. Strongly "
                  f"recommend pointing --mzmine-temp at a true-local "
                  f"directory (e.g. %TEMP%).", flush=True)
    else:
        mzmine_scratch = Path(tempfile.mkdtemp(prefix="k2_mzmine_"))
        scratch_is_owned = True

    input_pattern = str(input_folder / "*.mzML")
    output_base = output_folder / output_name

    # Optionally cap the thread count (e.g. 1 to serialise mzML import and
    # avoid the rotating-tmp-file mmap fault). See docstring above.
    if import_threads is None:
        effective_threads = max(1, int(threads))
    else:
        effective_threads = max(1, min(int(threads), int(import_threads)))

    # Pre-flight disk-space check against the scratch directory.
    # MZmine memory-maps mzML data into rotating temp files under
    # `-temp`. When the disk fills up mid-import, the write truncates,
    # the mapped region becomes invalid, and the next access faults
    # with `java.lang.InternalError: a fault occurred in an unsafe
    # memory access operation` (MemoryMapStorage.storeData line 206
    # at time of writing). The user just sees a Java stack trace with
    # no mention of disk space. Catching it here turns a confusing
    # mid-run crash into a clear up-front error.
    #
    # Heuristic: MZmine's mmap scratch typically peaks at ~1–3x the
    # total input mzML size depending on rotation count, deconv stage
    # outputs, and how much survives the GC. We refuse below 1.5x and
    # warn below 3x. These are calibrated to GC-EI workflows; LC-MS /
    # IMS workflows may need more headroom.
    try:
        input_bytes = sum(p.stat().st_size for p in
                          input_folder.glob("*.mzML"))
    except OSError:
        input_bytes = 0
    try:
        free_bytes = shutil.disk_usage(str(mzmine_scratch)).free
    except OSError:
        free_bytes = None

    def _fmt_gb(n):
        return f"{n / (1024**3):.1f} GB"

    if input_bytes and free_bytes is not None:
        required_min = int(input_bytes * 1.5)
        recommended = int(input_bytes * 3)
        if free_bytes < required_min:
            print(f"  ERROR: Insufficient free disk space for MZmine "
                  f"scratch.", flush=True)
            print(f"         Input mzML total: "
                  f"{_fmt_gb(input_bytes)}", flush=True)
            print(f"         Free on scratch volume "
                  f"({mzmine_scratch}): {_fmt_gb(free_bytes)}",
                  flush=True)
            print(f"         Required minimum (1.5x input): "
                  f"{_fmt_gb(required_min)}", flush=True)
            print(f"         Recommended (3x input): "
                  f"{_fmt_gb(recommended)}", flush=True)
            print(f"         MZmine memory-maps mzML data into "
                  f"rotating temp files under -temp. When the disk",
                  flush=True)
            print(f"         fills up mid-import the next memory "
                  f"access faults with `java.lang.InternalError: a "
                  f"fault", flush=True)
            print(f"         occurred in an unsafe memory access "
                  f"operation` — no mention of disk space in the log.",
                  flush=True)
            print(f"         Fix: free space on the scratch volume, "
                  f"or pass --mzmine-temp pointing at a different",
                  flush=True)
            print(f"         (true-local, non-cloud-synced) drive "
                  f"with more headroom.", flush=True)
            if scratch_is_owned and mzmine_scratch.exists():
                shutil.rmtree(mzmine_scratch, ignore_errors=True)
            return None
        if free_bytes < recommended:
            print(f"  WARNING: Free disk space on the MZmine scratch "
                  f"volume ({mzmine_scratch}) is "
                  f"{_fmt_gb(free_bytes)} —", flush=True)
            print(f"           input mzML total is "
                  f"{_fmt_gb(input_bytes)} and we recommend at least "
                  f"3x ({_fmt_gb(recommended)}).", flush=True)
            print(f"           If MZmine fails partway through import "
                  f"with `java.lang.InternalError: a fault occurred",
                  flush=True)
            print(f"           in an unsafe memory access operation`, "
                  f"the disk filled up — that's the cause.",
                  flush=True)
            print(f"           Either free space here or pass "
                  f"--mzmine-temp pointing at a roomier drive.",
                  flush=True)

    print(f"Input: {input_pattern}", flush=True)
    print(f"Output: {output_base}", flush=True)
    print(f"Threads: {effective_threads} (requested {threads})", flush=True)
    print(f"MZmine scratch: {mzmine_scratch}", flush=True)
    print(f"MZmine memory mode: {memory_mode}", flush=True)
    if input_bytes and free_bytes is not None:
        print(f"Scratch volume free: {_fmt_gb(free_bytes)} "
              f"(input mzML total: {_fmt_gb(input_bytes)})", flush=True)
    print(flush=True)

    cmd = [
        str(MZMINE),
        "-u", str(USER_FILE),
        "-b", str(BATCH_FILE),
        "-i", input_pattern,
        "-o", str(output_base),
        "-memory", memory_mode,
        "-temp", str(mzmine_scratch),
        "-threads", str(effective_threads)
    ]

    # Print the exact command so the user can reproduce manually if
    # something goes wrong below (list2cmdline quotes paths with spaces).
    print(f"MZmine command: {subprocess.list2cmdline(cmd)}", flush=True)
    print(flush=True)
    if log_file is not None:
        print(f"Full MZmine log: {log_file}", flush=True)
    print("MZmine log (filtered):", flush=True)
    print("-" * 40, flush=True)

    if _CANCEL.is_set():
        print("Cancelled.", flush=True)
        if scratch_is_owned and mzmine_scratch.exists():
            shutil.rmtree(mzmine_scratch, ignore_errors=True)
        return None

    # v3.1.0: keep the complete MZmine output on disk, untruncated.
    log_fh = None
    if log_file is not None:
        try:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            log_fh = open(log_file, 'w', encoding='utf-8', errors='replace')
            log_fh.write(f"# MZmine command: {subprocess.list2cmdline(cmd)}\n")
            log_fh.write(f"# Started: {datetime.now().isoformat()}\n\n")
        except OSError as e:
            print(f"  WARNING: could not open MZmine log file {log_file}: {e}",
                  flush=True)
            log_fh = None

    try:
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                **_popen_kwargs(),
            )
        except OSError as e:
            # WinError 362 = ERROR_CLOUD_FILE_PROVIDER_NOT_RUNNING.
            if getattr(e, "winerror", None) == 362:
                print(f"    ERROR: Cannot launch MZmine because a "
                      f"cloud-only placeholder could not be hydrated.")
                print(f"           Either start your cloud client (e.g. "
                      f"OneDrive) so it can fetch the file, or")
                print(f"           pin the software folder locally "
                      f"(\"Always keep on this device\").")
                print(f"           Underlying error: {e}")
                return None
            raise

        # Rolling buffer so we can dump tail-of-log on failure.
        from collections import deque
        TAIL_LINES = 200
        all_lines = deque(maxlen=TAIL_LINES)
        error_lines = []

        _register_child(process)
        try:
            for line in process.stdout:
                line = line.rstrip()
                if log_fh is not None:
                    log_fh.write(line + "\n")
                all_lines.append(line)
                if any(tok in line for tok in
                       ("SEVERE", "ERROR", "Exception", "Caused by", "Traceback")):
                    print(line, flush=True)
                    error_lines.append(line)
                elif any(level in line for level in ("INFO", "WARNING")):
                    if len(line) > 100:
                        line = line[:97] + "..."
                    print(line, flush=True)

            process.wait()
        finally:
            _unregister_child(process)
            if log_fh is not None:
                try:
                    log_fh.write(f"\n# Exit code: {process.returncode}\n")
                    log_fh.close()
                except OSError:
                    pass
        print("-" * 40, flush=True)

        if _CANCEL.is_set():
            print("Cancelled.", flush=True)
            return None

        if process.returncode != 0:
            print(f"\nERROR: MZmine processing failed (exit code "
                  f"{process.returncode})", flush=True)
            if error_lines:
                print("\nError lines captured:", flush=True)
                for err in error_lines:
                    print(f"  {err}", flush=True)
            else:
                print("\n(No SEVERE/ERROR/Exception lines were emitted. "
                      "Last lines of MZmine output follow — they often "
                      "show what went wrong, e.g. a Java startup fault, "
                      "an unreadable .mzbatch, or a CLI usage error.)",
                      flush=True)
            if all_lines:
                print(f"\n--- Last {len(all_lines)} line(s) of MZmine "
                      f"output (verbatim) ---", flush=True)
                for raw in all_lines:
                    print(f"  {raw}", flush=True)
                print(f"--- end MZmine output ---", flush=True)

            # Specific diagnosis for the
            #   java.lang.InternalError: a fault occurred in an unsafe
            #   memory access operation
            # crash inside MemoryMapStorage. This is the most common
            # MZmine failure mode on Windows and has several distinct
            # causes — surface them all explicitly so the user has
            # something to act on.
            joined = "\n".join(all_lines)
            if "InternalError" in joined and "unsafe memory access" in joined:
                print(
                    "\nDIAGNOSIS: MZmine crashed inside its memory-mapped "
                    "storage layer (MemoryMapStorage). On Windows this is "
                    "almost always one of these four things, in roughly "
                    "decreasing order of likelihood:",
                    flush=True,
                )
                # Disk-space diagnosis is FIRST because (a) the pre-flight
                # check above might have run with a stale free-space
                # reading, (b) MZmine's own log line at the point of
                # failure is "Cannot memory map array of length N, not
                # enough space left" — which sounds like a memory issue
                # but is actually disk-space exhaustion, and users
                # consistently miss it. Re-check live here so we can
                # report the post-failure number.
                try:
                    free_now = shutil.disk_usage(str(mzmine_scratch)).free
                    free_fmt = f"{free_now / (1024**3):.1f} GB"
                except OSError:
                    free_fmt = "unknown"
                print(
                    f"  1. The scratch volume ran OUT OF DISK SPACE during "
                    f"import. MZmine memory-maps mzML data into rotating "
                    f"temp files;\n"
                    f"     when the disk fills mid-write the mapped region "
                    f"becomes invalid and the next access faults. Current "
                    f"free space\n"
                    f"     on {mzmine_scratch}: {free_fmt}. If this number "
                    f"is in the low-GB range relative to your input mzML "
                    f"size,\n"
                    f"     this is your problem — free space here or pass "
                    f"--mzmine-temp pointing at a roomier drive.\n"
                    f"     (MZmine's own \"Cannot memory map ... not "
                    f"enough space left\" log line is misleading — it is "
                    f"disk, not heap.)",
                    flush=True,
                )
                scratch_str = str(mzmine_scratch).lower()
                if "onedrive" in scratch_str or "dropbox" in scratch_str:
                    print(
                        "  2. The scratch directory is on a CLOUD-SYNCED "
                        "path. Pass --mzmine-temp pointing at a true-local "
                        "directory, or drop the override entirely.",
                        flush=True,
                    )
                else:
                    print(
                        "  2. Parallel import threads racing on the shared "
                        "scratch file. Try --threads 1 (we already serialise "
                        "import internally, but a higher --threads pushes "
                        "concurrency into other stages).",
                        flush=True,
                    )
                print(
                    "  3. Antivirus real-time scanning grabbing the "
                    f"mzmine.tmp file mid-write. Exclude\n"
                    f"     {mzmine_scratch}\n"
                    "     (and ideally all of %TEMP%) from Defender or your "
                    "AV's real-time scan list and retry.",
                    flush=True,
                )
                print(
                    "  4. MZmine's memory mode forcing the mmap path. Try "
                    "--mzmine-memory all (everything memory-mapped, more "
                    "deterministic) or --mzmine-memory none (everything in "
                    "heap, if your dataset fits in RAM). Valid values for "
                    "MZmine 4.x: none, all, features, centroids, raw, "
                    "masses_features.",
                    flush=True,
                )
                print(
                    f"\nThe exact MZmine command we ran is printed above. "
                    f"Try copy-pasting it into a terminal to reproduce "
                    f"outside the pipeline — if it fails there too, the "
                    f"issue is in MZmine's environment, not K2 Annotator.",
                    flush=True,
                )

            # Specific diagnosis for the JVM-level commit-memory failure
            # we see on Windows machines with a small/fixed page file.
            # Detect by both the OS error code (1455) and the JVM's
            # human-readable banner.
            if ("paging file is too small" in joined.lower()
                    or "errno=1455" in joined
                    or "commit_memory" in joined
                    or "insufficient memory for the Java Runtime"
                    in joined):
                print(
                    "\nDIAGNOSIS: The JVM could not commit virtual memory "
                    "(Windows error 1455 / ERROR_COMMITMENT_LIMIT). This "
                    "is a Windows page-file sizing problem, not an "
                    "MZmine bug. Two ways to fix:",
                    flush=True,
                )
                print(
                    "  1. Increase the Windows page file. Settings → "
                    "System → About → Advanced system settings → "
                    "Performance Settings → Advanced → Virtual memory → "
                    "Change. Tick \"Automatically manage paging file "
                    "size for all drives\" (or set it to System Managed "
                    "on C:). Re-run after the system finishes resizing.",
                    flush=True,
                )
                print(
                    "  2. Lower MZmine's memory footprint by switching "
                    "to --mzmine-memory all (memory-map everything to "
                    "disk) or --mzmine-memory masses_features (map the "
                    "bulk data, keep raw scans in heap). If you are "
                    "already memory-mapping and still failing, the fix "
                    "is on the OS side (item 1). NOTE: pre-v3.0.18 "
                    "this hint recommended --mzmine-memory mass, but "
                    "\"mass\" is NOT a valid value in MZmine 4.x and "
                    "is what caused the silent exit-1 you may have "
                    "just hit on an earlier run.",
                    flush=True,
                )
                print(
                    f"\nNote that mzmine_console.exe sets its own JVM "
                    f"heap size from your system RAM; this pipeline "
                    f"does not control --Xmx directly. If you need a "
                    f"smaller heap, edit mzmine.vmoptions in your "
                    f"MZmine install.",
                    flush=True,
                )
            return None

        print("MZmine processing complete", flush=True)
        return output_folder
    finally:
        # Clean up the scratch dir if we own it. Skip cleanup when the
        # user passed an explicit --mzmine-temp.
        if scratch_is_owned and mzmine_scratch.exists():
            shutil.rmtree(mzmine_scratch, ignore_errors=True)


# ============================================================================
# Stage 3: Library Matching
# ============================================================================
def _run_cli_in_process(cli_args, env):
    """Invoke scripts/cli.py's main() inside this interpreter.

    Used by the PyInstaller build, where sys.executable is K2.exe and
    spawning `python cli.py` is impossible. cli.main() may accept an
    argv list (v3.1.0) or read sys.argv; both are handled. cli.py
    signals its result with sys.exit(), so SystemExit is translated
    back into an integer return code (0 ok, 2 no matches, 1 error).
    """
    scripts_dir = str(SCRIPTS_DIR)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import cli  # noqa: E402  (scripts/cli.py)

    saved_env = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    saved_argv = sys.argv
    sys.argv = ['cli.py'] + list(cli_args)
    try:
        try:
            params = inspect.signature(cli.main).parameters
        except (TypeError, ValueError):
            params = {}
        try:
            if params:
                rc = cli.main(list(cli_args))
            else:
                rc = cli.main()
        except SystemExit as e:
            rc = e.code
        if rc is None:
            rc = 0
        if not isinstance(rc, int):
            print(str(rc), flush=True)
            rc = 1
        return rc
    finally:
        sys.argv = saved_argv
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_library_matching(mzmine_folder, output_folder, project_name, library_file,
                         blank_id, ri_cal=None, api_key=None, grouping=None, is_config=None,
                         surrogate_library=None, surrogate_config=None, reference_samples=None,
                         bff_mode='standard', bff_c_factor=5.0, max_lib_peaks=20,
                         ri_extrapolation='spline', allow_no_blanks=False):
    """Run library matching using cli.py.

    Returns (output_folder, cli_exit_code) on completion, where the exit
    code is 0 (matches found) or EXIT_NO_MATCHES (2: the run completed
    but no Level-2 matches were found; summaries are still written).
    Returns None on failure.
    """

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
    print(f"Max lib peaks: {max_lib_peaks}")
    print(f"RI extrapolation: {ri_extrapolation}")
    if allow_no_blanks:
        print(f"Allow no blanks: yes")
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
    
    frozen = getattr(sys, 'frozen', False)

    # Build command for cli.py
    cli_script = SCRIPTS_DIR / "cli.py"

    if not cli_script.exists():
        # Try alternate location
        cli_script = SCRIPTS_DIR / "src" / "cli.py"

    if not cli_script.exists() and not frozen:
        print(f"ERROR: cli.py not found in {SCRIPTS_DIR}")
        return None

    output_folder.mkdir(parents=True, exist_ok=True)

    # Arguments for cli.py (the interpreter/script prefix is added only
    # for the subprocess path; the frozen build calls cli.main() directly).
    # v3.1.0: cli.py runs with cwd=scripts/, so every path must be absolute
    # (relative inputs such as "data/quant.csv" were previously "not found").
    def _abs(p):
        return str(Path(p).resolve())

    cli_args = [
        "--quant", _abs(quant_file),
        "--msp", _abs(msp_file),
        "--library", _abs(library_file),
        "--blank-id", blank_id,
        "--bff-mode", bff_mode,
        "--bff-c-factor", str(bff_c_factor),
        "--max-lib-peaks", str(max_lib_peaks),  # v3.0.19
        "--ri-extrapolation", str(ri_extrapolation),  # v3.1.0
        "--name", str(project_name),  # v3.1.0: used for output file names
        "--output", _abs(output_folder)
    ]
    cmd = cli_args

    if allow_no_blanks:
        cmd.append("--allow-no-blanks")  # v3.1.0

    if ri_cal:
        cmd.extend(["--ri-cal", _abs(ri_cal)])

    # v3.1.0: the API key travels in the environment, never on the
    # command line (cli.py reads K2_EPA_API_KEY as its --api-key fallback).
    env = os.environ.copy()
    if api_key:
        env[API_KEY_ENV] = api_key

    if grouping:
        cmd.extend(["--grouping", _abs(grouping)])

    if is_config:
        cmd.extend(["--is-config", _abs(is_config)])

    # v3.0.0: Surrogate recovery parameters
    if surrogate_library:
        cmd.extend(["--surrogate-library", _abs(surrogate_library)])

    if surrogate_config:
        cmd.extend(["--surrogate-config", _abs(surrogate_config)])

    if reference_samples:
        cmd.extend(["--reference-samples", str(reference_samples)])

    print("Running library matching...")
    if frozen:
        print(f"cli.py arguments (in-process): "
              f"{redact_command(['cli.py'] + cli_args)}")
    else:
        print(f"cli.py command: "
              f"{redact_command([sys.executable, str(cli_script)] + cli_args)}")
    if api_key:
        print(f"(EPA API key passed via {API_KEY_ENV}, not shown)")
    print("-" * 40)

    if _CANCEL.is_set():
        print("Cancelled.")
        return None

    if frozen:
        # PyInstaller build: sys.executable is K2.exe, so run cli.py's
        # main() in this interpreter instead of spawning a child.
        try:
            returncode = _run_cli_in_process(cli_args, {API_KEY_ENV: api_key}
                                             if api_key else {})
        except Exception as e:
            print(f"ERROR: Library matching raised {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None
    else:
        # Run cli.py and stream output
        process = subprocess.Popen(
            [sys.executable, "-u", str(cli_script)] + cli_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(SCRIPTS_DIR),  # Run from scripts directory
            env=env,
            **_popen_kwargs(),
        )
        _register_child(process)
        try:
            for line in process.stdout:
                print(line.rstrip())
            process.wait()
        finally:
            _unregister_child(process)
        returncode = process.returncode

    print("-" * 40)

    if _CANCEL.is_set():
        print("Cancelled.")
        return None

    if returncode == EXIT_NO_MATCHES:
        # v3.1.0: cli.py exits 2 when it completed but found zero
        # Level-2 matches. Summaries were still written; this is a
        # warning, not a failure.
        print("WARNING: Library matching completed with NO Level-2 matches "
              "(exit code 2). Feature summaries were still written.")
        return output_folder, EXIT_NO_MATCHES

    if returncode != 0:
        print(f"ERROR: Library matching failed (exit code {returncode})")
        return None

    return output_folder, 0


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
    
    # Determine project name. v3.1.0: --name is sanitised so it is safe
    # as a path component (results/<name>, converted/<name>, ...).
    if args.name:
        project_name = sanitise_name(args.name)
        if project_name != args.name:
            print(f"NOTE: project name {args.name!r} sanitised to "
                  f"{project_name!r} for use in paths")
    else:
        project_name = input_folder.name
        # Clean up name if it's a generic folder
        if project_name.lower() in ['raw', 'raw_data', 'data', 'input']:
            project_name = input_folder.parent.name
        project_name = sanitise_name(project_name)

    # Add timestamp to make unique if not user-specified
    if not args.name:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        run_name = f"{project_name}_{timestamp}"
    else:
        run_name = project_name

    # Resolve library path
    library_file = Path(args.library) if args.library else DEFAULT_LIBRARY

    # Define output directories
    # Use output argument if provided, otherwise default to PIPELINE_ROOT
    if args.output:
        base_output = Path(args.output)
    else:
        base_output = PIPELINE_ROOT

    # v3.1.0: never overwrite an earlier run — append _2, _3, ... when
    # the output directories for this run name already exist.
    unique_name = unique_run_name(base_output, run_name, stages)
    if unique_name != run_name:
        print(f"NOTE: output for run '{run_name}' already exists; "
              f"using '{unique_name}' instead (never overwritten)")
        run_name = unique_name

    converted_dir = base_output / "converted" / run_name
    mzmine_dir = base_output / "mzmine_output" / run_name
    results_dir = base_output / "results" / run_name

    # v3.1.0: tee everything the pipeline prints from here on into
    # <results_dir>/pipeline_log.txt (K2_LOG_FILE).
    results_dir.mkdir(parents=True, exist_ok=True)
    log_path = results_dir / "pipeline_log.txt"
    try:
        log_fh = open(log_path, 'w', encoding='utf-8', errors='replace')
    except OSError as e:
        print(f"WARNING: could not open pipeline log {log_path}: {e}")
        log_fh = None
    os.environ['K2_LOG_FILE'] = str(log_path)

    try:
        with _StdoutRedirect(log_fh):
            return _run_pipeline_stages(
                args, input_folder, input_type, stages, project_name,
                run_name, library_file, converted_dir, mzmine_dir,
                results_dir, log_path)
    finally:
        if log_fh is not None:
            try:
                log_fh.close()
            except OSError:
                pass


def _run_pipeline_stages(args, input_folder, input_type, stages, project_name,
                         run_name, library_file, converted_dir, mzmine_dir,
                         results_dir, log_path):
    """Body of run_pipeline(), executed with stdout teed to the log file."""

    # Print header
    print_header("GC-MS Suspect Screening Pipeline")

    print(f"Input:        {input_folder}")
    print(f"Input type:   {input_type}")
    print(f"Project name: {project_name}")
    print(f"Run name:     {run_name}")
    print(f"Stages:       {' -> '.join(stages)}")
    print(f"Threads:      {args.threads}")
    if getattr(args, 'mzmine_import_threads', None) is not None:
        print(f"MZmine import thread cap: {args.mzmine_import_threads}")
    print(f"Pipeline log: {log_path}")
    if 'match' in stages:
        print(f"Library:      {library_file}")
        print(f"Blank ID:     '{args.blank_id}'")
        print(f"BFF Mode:     {args.bff_mode}")
        print(f"BFF c-factor: {getattr(args, 'bff_c_factor', 5.0)}")
        print(f"Max lib peaks: {getattr(args, 'max_lib_peaks', 20)}")
        print(f"RI extrapolation: {getattr(args, 'ri_extrapolation', 'spline')}")
        print(f"Allow no blanks: {'yes' if getattr(args, 'allow_no_blanks', False) else 'no'}")

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

    total_steps = len(stages)
    current_step = 0
    exit_code = 0

    # ========================================================================
    # Stage 1: Conversion
    # ========================================================================
    if 'convert' in stages:
        current_step += 1
        print_step(current_step, total_steps, "Converting raw data to mzML")
        
        result = run_conversion(
            input_folder,
            converted_dir,
            stage_locally=not getattr(args, 'no_stage_locally', False),
        )
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
        
        result = run_mzmine(
            mzml_input, mzmine_dir, run_name, args.threads,
            mzmine_temp=Path(args.mzmine_temp) if getattr(args, 'mzmine_temp', None) else None,
            memory_mode=getattr(args, 'mzmine_memory', 'none'),
            import_threads=getattr(args, 'mzmine_import_threads', None),
            log_file=results_dir / "mzmine_log.txt",  # v3.1.0
        )
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

        # v3.1.0: --api-key on the CLI still works, but the environment
        # variable is the preferred (non-leaking) channel.
        api_key = args.api_key or os.environ.get(API_KEY_ENV) or None

        result = run_library_matching(
            mzmine_folder=mzmine_output,
            output_folder=results_dir,
            project_name=project_name,
            library_file=library_file,
            blank_id=args.blank_id,
            ri_cal=ri_cal,
            api_key=api_key,
            grouping=args.grouping,
            is_config=args.is_config if hasattr(args, 'is_config') else None,
            surrogate_library=args.surrogate_library if hasattr(args, 'surrogate_library') else None,
            surrogate_config=args.surrogate_config if hasattr(args, 'surrogate_config') else None,
            reference_samples=args.reference_samples if hasattr(args, 'reference_samples') else None,
            bff_mode=getattr(args, 'bff_mode', 'standard'),
            bff_c_factor=getattr(args, 'bff_c_factor', 5.0),
            max_lib_peaks=getattr(args, 'max_lib_peaks', 20),  # v3.0.19
            ri_extrapolation=getattr(args, 'ri_extrapolation', 'spline'),  # v3.1.0
            allow_no_blanks=getattr(args, 'allow_no_blanks', False),  # v3.1.0
        )
        if result is None:
            return 1
        _, match_rc = result
        if match_rc == EXIT_NO_MATCHES:
            exit_code = EXIT_NO_MATCHES

    # ========================================================================
    # Complete
    # ========================================================================
    if exit_code == EXIT_NO_MATCHES:
        print_header("Pipeline Complete (WARNING: no Level-2 matches found)")
    else:
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

    # 0 = success, EXIT_NO_MATCHES (2) = completed with warning (no matches)
    return exit_code


def build_parser():
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
        help='EPA CompTox API key for toxicity data (optional). Prefer '
             f'setting the {API_KEY_ENV} environment variable instead so '
             'the key never appears on a command line.'
    )

    # v3.1.0: forwarded verbatim to cli.py
    parser.add_argument(
        '--ri-extrapolation',
        choices=['spline', 'linear'],
        default='spline',
        help='How retention indices are computed for features whose RT '
             'lies outside the alkane calibration range: "spline" '
             '(default, cubic-spline extrapolation) or "linear" (van den '
             'Dool linear extrapolation from the terminal alkane pair). '
             'Forwarded to cli.py.'
    )

    parser.add_argument(
        '--allow-no-blanks',
        action='store_true',
        help='Permit a run in which no blank samples are identified '
             '(blank feature filtering is then skipped). By default a '
             'zero-blank run is refused. Forwarded to cli.py.'
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

    # v3.0.19: peak-trim libraries to top-N peaks by intensity to
    # equalise HR vs LR peak-count asymmetry in dot/rev-dot scoring.
    # Forwarded verbatim to cli.py.
    parser.add_argument(
        '--max-lib-peaks',
        type=int,
        default=20,
        metavar='N',
        help='Trim every library compound to the top N peaks by '
             'intensity at load (default: 20). Equalises HR vs LR '
             'peak counts so reverse-dot is not biased against '
             'peak-dense HR entries. Pass 0 to disable trimming.'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--no-stage-locally',
        action='store_true',
        help='Write MSConvert output directly to the final output '
             'folder instead of staging through local temp disk. '
             'Faster when the output folder is already on a fast '
             'local drive; much slower when the output folder is a '
             'network share (Z:, SMB, VPN-mounted) — leave this OFF '
             'unless you know your output is local.'
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
    parser.add_argument(
        '--mzmine-temp',
        type=str,
        default=None,
        metavar='PATH',
        help='Scratch directory MZmine uses for memory-mapped '
             'intermediate files. Default: a per-run subdirectory of '
             'the system temp dir (%%TEMP%%). DO NOT point this at a '
             'cloud-synced path (OneDrive, Dropbox) — Java NIO memory '
             'mapping fails on cloud-mounted files.'
    )
    parser.add_argument(
        '--mzmine-memory',
        choices=['none', 'all', 'features', 'centroids', 'raw',
                 'masses_features'],
        default='none',
        help='MZmine `-memory` mode (MZmine 4.x KeepInMemory enum). '
             '"none" (default, matches MZmine\'s own fallback) keeps '
             'everything in the JVM heap. "all" memory-maps everything '
             'to disk — lowest heap pressure, best for large mzML on '
             'machines with small Windows page files. '
             '"masses_features" maps mass lists + features but keeps '
             'raw scans in heap. "features" / "centroids" / "raw" map '
             'only the named layer. NOTE: pre-v3.0.18 of this pipeline '
             'accepted "mass" here but that value is NOT valid in '
             'MZmine 4 — it triggers a non-fatal WARNING then a silent '
             'exit-1 a few steps later. If MZmine fails with "paging '
             'file is too small" / errno=1455, try "all" first.'
    )
    parser.add_argument(
        '--mzmine-import-threads',
        type=int,
        default=None,
        metavar='N',
        help='Optional cap on the MZmine thread count (applies to the '
             'whole MZmine run). Default: none, i.e. --threads is used as '
             'given. Pass 1 to serialise mzML import: MZmine import '
             'threads share a rotating scratch file and races between '
             'them are the most common cause of '
             '"java.lang.InternalError: a fault occurred in an unsafe '
             'memory access operation". (Before v3.1.0 this defaulted '
             'to 1, which silently overrode --threads.)'
    )

    return parser


def main(argv=None, output=None):
    """Pipeline entry point.

    `argv`: argument list (defaults to sys.argv[1:]); lets the frozen GUI
    call the pipeline in-process. `output`: optional callable receiving
    every chunk of text the pipeline prints (in addition to the current
    sys.stdout, which may be None in a windowed PyInstaller build), so
    the GUI console can stream log lines without a subprocess.

    Returns 0 on success, 2 when the run completed but found no Level-2
    matches (EXIT_NO_MATCHES), 1 on error.
    """
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        # argparse exits on --help / usage errors; when called in-process
        # we must not tear down the host (GUI) interpreter.
        if argv is None:
            raise
        return e.code if isinstance(e.code, int) else 1

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

    _reset_cancel()

    def _run():
        try:
            return run_pipeline(args)
        except KeyboardInterrupt:
            print("\n\nPipeline interrupted by user.")
            return 1
        except Exception as e:
            print(f"\n\nERROR: {e}")
            if args.verbose or output is not None:
                import traceback
                traceback.print_exc()
            return 1

    if output is None:
        return _run()
    with _StdoutRedirect(output):
        return _run()


if __name__ == "__main__":
    sys.exit(main())
