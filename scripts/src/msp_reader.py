"""
One tolerant MSP reader for every MSP consumer in K2 Annotator (v3.1.0,
review finding D-3).

Before v3.1.0 there were five separate MSP parsers (library, MZmine spectra,
MS-DIAL spectra, internal-standard MSP, legacy MS-DIAL parser), each accepting
a different subset of the format.  A NIST export with ``41 59; 43 999;`` peak
lines loaded zero compounds, a UTF-8 BOM hid the first key, ``NAME:`` in upper
case gave every MZmine feature an empty spectrum, and entries not separated by
a blank line were merged.

`iter_msp(path)` yields one ``(fields, peaks)`` tuple per record:

* ``fields``  - dict of header lines, keys as written (stripped), values
                stripped; use `field(fields, *aliases)` to look a key up
                case-insensitively and independent of ``_`` / space spelling.
* ``peaks``   - list of ``(mz, intensity)`` floats in file order.

Accepted syntax:
  - BOM, CRLF, any encoding errors replaced;
  - header ``Key: value`` lines in any case, ``Retention_index`` == ``RETENTIONINDEX``;
  - ``Num Peaks``, ``NUM_PEAKS``, ``Num Features`` start the peak block;
    the declared count is checked but never used to truncate;
  - peak lines ``128 999``, ``128\t999``, ``128 999;``, ``41 59; 43 999; 57 891;``,
    ``(41 59)(43 999)``, ``128 999 "C10H8+"``;
  - records end at a blank line OR at the next ``NAME:`` line.
"""
import re

_NUM = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'
_PEAK_PAIR = re.compile(r'(' + _NUM + r')[\s,]+(' + _NUM + r')')
_PEAK_BLOCK_KEYS = {'NUM PEAKS', 'NUM FEATURES', 'NUMPEAKS', 'PEAKS'}
_NAME_KEYS = {'NAME', 'COMPOUND NAME'}


def normalise_key(key):
    """'Retention_index' -> 'RETENTION INDEX'; 'Num Peaks' -> 'NUM PEAKS'."""
    return re.sub(r'\s+', ' ', str(key).replace('_', ' ')).strip().upper()


def field(fields, *aliases, default=None):
    """Case/spelling-insensitive lookup: field(f, 'RI', 'RetentionIndex')."""
    wanted = {normalise_key(a) for a in aliases}
    for k, v in fields.items():
        if normalise_key(k) in wanted:
            return v
    return default


def parse_peak_line(line):
    """Return all (mz, intensity) pairs found on one peak line."""
    text = line.replace(';', ' ').replace('(', ' ').replace(')', ' ')
    pairs = []
    for chunk in re.split(r'\s{2,}|\t|(?<=\d)\s+(?=\d)', text):
        pass  # placeholder: simple regex scan below handles all layouts
    for m in _PEAK_PAIR.finditer(text):
        try:
            pairs.append((float(m.group(1)), float(m.group(2))))
        except ValueError:
            continue
    return pairs


_RI_ALIASES = ('RI', 'RETENTIONINDEX', 'RETENTION INDEX', 'KOVATS', 'KOVATS RI',
               'KOVATSRI', 'RETENTION_INDEX', 'RETENTIONINDEX (SEMISTDNP)')


def parse_ri(fields):
    """Retention index as float, or None.  Accepts '1181', '1181.3' and
    MassBank/NIST forms such as 'SemiStdNP=1000/8/25' (first number wins)."""
    raw = field(fields, *_RI_ALIASES)
    if raw is None:
        return None
    m = re.search(r'[-+]?\d+(?:\.\d+)?', str(raw))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def parse_rt(fields):
    raw = field(fields, 'RT', 'RETENTIONTIME', 'RETENTION TIME', 'RETENTION_TIME')
    if raw is None:
        return None
    m = re.search(r'[-+]?\d+(?:\.\d+)?', str(raw))
    return float(m.group(0)) if m else None


def iter_msp(path, warn=print):
    """Yield (fields, peaks) for each record in an MSP file.

    `warn` receives one message per anomaly class (peak-count mismatches are
    aggregated and reported once at the end).
    """
    fields = {}
    peaks = []
    in_peaks = False
    declared = None
    open_record = False
    mismatches = 0
    junk_lines = 0

    def flush():
        nonlocal fields, peaks, in_peaks, declared, open_record, mismatches
        if open_record:
            if declared is not None and declared != len(peaks):
                mismatches += 1
            yield_val = (fields, peaks)
            fields, peaks, in_peaks, declared, open_record = {}, [], False, None, False
            return yield_val
        return None

    with open(path, 'r', encoding='utf-8-sig', errors='replace') as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                rec = flush()
                if rec is not None:
                    yield rec
                continue

            # A header line?  (key: value, key must not start with a digit)
            if ':' in line and not line[0].isdigit() and not line[0] in '+-.(':
                key, value = line.split(':', 1)
                nkey = normalise_key(key)
                if nkey in _NAME_KEYS and open_record and (peaks or in_peaks or
                                                            field(fields, *_NAME_KEYS) is not None):
                    rec = flush()
                    if rec is not None:
                        yield rec
                open_record = True
                fields[key.strip()] = value.strip()
                if nkey in _PEAK_BLOCK_KEYS:
                    in_peaks = True
                    m = re.search(r'\d+', value)
                    declared = int(m.group(0)) if m else None
                continue

            # Otherwise a peak line (with or without a preceding Num Peaks)
            if open_record:
                found = parse_peak_line(line)
                if found:
                    peaks.extend(found)
                    in_peaks = True
                else:
                    junk_lines += 1
            else:
                junk_lines += 1

    rec = flush()
    if rec is not None:
        yield rec

    if mismatches and warn:
        warn(f"[MSP] {mismatches} record(s) in {path} declare a 'Num Peaks' that differs "
             f"from the number of peak lines found; the peak lines were kept.")
    if junk_lines and warn:
        warn(f"[MSP] {junk_lines} unparseable line(s) ignored in {path}.")


def read_msp(path, warn=print):
    """Convenience: list of (fields, peaks)."""
    return list(iter_msp(path, warn=warn))
