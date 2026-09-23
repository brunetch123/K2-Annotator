"""
Run manifest (v3.1.0, review finding D-6).

A results folder produced before v3.1.0 could not tell you which library,
calibration file, sample classification, trimming parameter or software
versions produced it.  `write_manifest()` records all of that, plus SHA-256
hashes of every input file, as `run_manifest.json` next to the reports.
"""
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone

from src.version import __version__


def _sha256(path, block=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(block), b''):
            h.update(chunk)
    return h.hexdigest()


def describe_input(path):
    """{'path', 'abspath', 'size', 'sha256', 'mtime'} for an input file, or
    {'path': path, 'missing': True} when it does not exist."""
    if not path:
        return None
    if not os.path.exists(path):
        return {'path': str(path), 'missing': True}
    st = os.stat(path)
    return {
        'path': str(path),
        'abspath': os.path.abspath(path),
        'size': st.st_size,
        'sha256': _sha256(path),
        'mtime': datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
    }


def package_versions(names=('numpy', 'scipy', 'pandas', 'molmass', 'reportlab',
                            'matplotlib', 'requests', 'ctxpy')):
    out = {}
    try:
        from importlib import metadata
    except ImportError:  # pragma: no cover
        return out
    for n in names:
        try:
            out[n] = metadata.version(n)
        except metadata.PackageNotFoundError:
            out[n] = None
    return out


def build_manifest(args, inputs, extra=None):
    """Assemble the manifest dict.

    args:   argparse Namespace (or dict) of resolved command-line options;
            any value containing 'key' or 'token' in its name is redacted.
    inputs: {label: path} of input files to hash.
    extra:  free-form dict merged at top level (sample classification,
            library stats, calibration info, match counts...).
    """
    resolved = dict(vars(args)) if hasattr(args, '__dict__') else dict(args)
    for k in list(resolved):
        if any(w in k.lower() for w in ('key', 'token', 'password', 'secret')):
            resolved[k] = '<redacted>' if resolved[k] else None
    manifest = {
        'k2_version': __version__,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'python': sys.version.split()[0],
        'platform': platform.platform(),
        'packages': package_versions(),
        'command': [os.path.basename(sys.argv[0])] + sys.argv[1:] if sys.argv else [],
        'args': resolved,
        'inputs': {label: describe_input(p) for label, p in inputs.items() if p},
    }
    for k in list(manifest['command']):
        pass
    if extra:
        manifest.update(extra)
    return manifest


def write_manifest(output_dir, args, inputs, extra=None, filename='run_manifest.json'):
    manifest = build_manifest(args, inputs, extra)
    # redact an API key that may have been given on the command line
    cmd = manifest['command']
    for i, tok in enumerate(cmd):
        if tok in ('--api-key', '-k') and i + 1 < len(cmd):
            cmd[i + 1] = '<redacted>'
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=2, default=str)
    return path
