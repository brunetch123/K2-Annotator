import csv
import sys
import json
import os

from src.msp_reader import iter_msp, field, parse_ri


# v3.0.19: Trim library spectra to this many peaks (by intensity) at
# load time. NIST/Wiley LR entries average ~70 peaks; HR Orbitrap-
# derived entries average ~125+ with many low-intensity ions that
# carry no matching value but inflate the dot-product denominator.
# The diagnostic on the May 2026 unified library showed HR entries
# losing ~4x reverse-dot vs the LR version of the same compound
# (e.g. 9-fluorenone: LR 27 peaks → rev_dot 735 (PASS); HR 79 peaks
# → rev_dot 167 (FAIL)) purely because of this asymmetry.
# 20 was chosen to roughly match the feature-peak-count median
# coming out of MZmine deconvolution; tune via --max-lib-peaks.
# NOTE (v3.1.0, S-TRIM-1): this trim changes dot products and the RHRMF
# reverse-filter set for any entry with more than N peaks; the value used
# is recorded in the run manifest and must be reported with results.
MAX_LIB_PEAKS_DEFAULT = 20


def _trim_spectrum(peaks, max_peaks):
    """Return the top `max_peaks` peaks by intensity, restored to
    m/z-ascending order. No-op when `max_peaks` is None, ≤0, or
    when the spectrum already has ≤ max_peaks peaks.

    Trimming happens once per library compound at load time, so the
    cost is paid only on library import (not on every feature
    comparison) and downstream consumers (matching_engine,
    spectral_math, rhrmf) see the already-trimmed spectrum.
    """
    if max_peaks is None or max_peaks <= 0:
        return peaks
    if len(peaks) <= max_peaks:
        return peaks
    try:
        top = sorted(peaks, key=lambda p: -float(p[1]))[:max_peaks]
    except (TypeError, ValueError, IndexError):
        return peaks
    try:
        top.sort(key=lambda p: float(p[0]))
    except (TypeError, ValueError, IndexError):
        pass
    return top


class LibraryCompound:
    """
    Represents a single compound from the Reference Library.
    """
    def __init__(self, name, formula, ri, spectrum, metadata, library_index=None):
        self.name = name
        self.formula = formula
        self.ri = float(ri)
        self.spectrum = spectrum  # List of [mz, intensity]
        self.metadata = metadata  # Dictionary of ALL other columns (keys lower-cased)
        self.library_index = library_index  # v3.0.1: Unique ID within loaded library

    def __repr__(self):
        return f"<LibComp '{self.name}' RI={self.ri:.1f} Peaks={len(self.spectrum)} LibIdx={self.library_index}>"


class LibraryParser:
    def __init__(self, library_path, max_peaks=MAX_LIB_PEAKS_DEFAULT):
        self.library_path = library_path
        self.max_peaks = max_peaks  # v3.0.19: per-compound spectrum trim
        self.compounds = []
        self.stats = {}  # v3.1.0: load statistics for the run manifest

    def load_library(self):
        """
        Load library from either CSV or MSP format.
        Auto-detects format based on file extension.

        Filters:
        1. Must have a valid RI.
        2. Must have a valid Spectrum.
        """
        if not os.path.exists(self.library_path):
            raise FileNotFoundError(f"Library not found at {self.library_path}")

        ext = os.path.splitext(self.library_path)[1].lower()
        if ext == '.msp':
            self._load_msp()
        elif ext == '.csv':
            self._load_csv()
        else:
            raise ValueError(f"Unsupported library format: {ext}. Expected .csv or .msp")

        if not self.compounds:
            raise ValueError(
                f"Library {self.library_path} yielded no usable entries (every entry lacked an "
                f"RI or a spectrum, or the file format was not recognised).")
        self._report_unknown_atoms()

    def _report_unknown_atoms(self):
        """v3.1.0 (S-RHRMF-2): warn about formulas with atoms the RHRMF cannot use."""
        try:
            from src.rhrmf import FormulaExplainer, atom_mass
        except ImportError:
            return
        ex = FormulaExplainer()
        bad = []
        for c in self.compounds:
            if not c.formula:
                continue
            comp = ex.parse_formula(c.formula)
            if any(atom_mass(sym) is None for sym in comp):
                bad.append(c.name)
        self.stats['formulas_with_unknown_atoms'] = len(bad)
        if bad:
            print(f"[WARNING] {len(bad)} library entries contain atoms with no known mass "
                  f"(RHRMF will ignore them), e.g. {bad[:5]}")

    def _load_csv(self):
        """
        Stream reads the CSV library.
        """
        # csv.field_size_limit takes a C long (32-bit on Windows); shrink until accepted.
        max_int = sys.maxsize
        while True:
            try:
                csv.field_size_limit(max_int)
                break
            except OverflowError:
                max_int = int(max_int / 10)

        valid_count = 0
        skipped_count = 0

        with open(self.library_path, 'r', newline='', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                raise ValueError(f"Library CSV {self.library_path} is empty")

            col_map = {name.strip(): i for i, name in enumerate(header)}
            lower_map = {name.strip().lower(): i for i, name in enumerate(header)}
            idx_name = lower_map.get('name')
            idx_formula = lower_map.get('formula')
            idx_ri = lower_map.get('ri')
            idx_peaks = lower_map.get('peaks_json')
            missing = [k for k, v in (('name', idx_name), ('formula', idx_formula),
                                      ('ri', idx_ri), ('peaks_json', idx_peaks)) if v is None]
            if missing:
                raise ValueError(f"Library CSV is missing required columns: {missing}")

            for row in reader:
                if not row:
                    continue
                # 1. RI
                ri_str = row[idx_ri] if len(row) > idx_ri else ""
                try:
                    ri_val = float(ri_str)
                except (ValueError, TypeError):
                    skipped_count += 1
                    continue
                # 2. Spectrum
                try:
                    peaks_str = row[idx_peaks] if len(row) > idx_peaks else "[]"
                    spectrum = json.loads(peaks_str)
                    if not spectrum or not isinstance(spectrum, list):
                        skipped_count += 1
                        continue
                except (json.JSONDecodeError, IndexError):
                    skipped_count += 1
                    continue
                spectrum = _trim_spectrum(spectrum, self.max_peaks)

                metadata = {}
                for col_name, idx in col_map.items():
                    metadata[col_name.lower()] = row[idx] if idx < len(row) else ""

                name = row[idx_name] if len(row) > idx_name else "Unknown"
                formula = row[idx_formula] if len(row) > idx_formula else ""
                self.compounds.append(LibraryCompound(name, formula, ri_val, spectrum, metadata))
                valid_count += 1
                if valid_count % 5000 == 0:
                    print(f"Loaded {valid_count} valid compounds...", end='\r')

        self.compounds.sort(key=lambda x: x.ri)
        self._assign_library_indices()
        self.stats.update(format='csv', valid=valid_count, skipped=skipped_count,
                          max_peaks=self.max_peaks)
        print(f"\nLibrary Loading Complete (CSV).")
        print(f"Valid Compounds (Sorted by RI): {valid_count}")
        print(f"Skipped (No RI/Spectra):        {skipped_count}")

    def _load_msp(self):
        """
        Load library from MSP format (NIST/MassBank style) through the shared
        tolerant reader (v3.1.0, D-3).

        Required fields: NAME (or Compound Name), a retention index
        (RI / RetentionIndex / Retention_index / Kovats, first number used),
        and at least one peak.  FORMULA is optional but required for RHRMF.
        All header fields become lower-cased metadata keys.
        """
        valid_count = 0
        skipped_count = 0
        for fields, peaks in iter_msp(self.library_path):
            comp = self._parse_msp_compound(fields, peaks)
            if comp:
                self.compounds.append(comp)
                valid_count += 1
                if valid_count % 5000 == 0:
                    print(f"Loaded {valid_count} valid compounds...", end='\r')
            else:
                skipped_count += 1

        self.compounds.sort(key=lambda x: x.ri)
        self._assign_library_indices()
        self.stats.update(format='msp', valid=valid_count, skipped=skipped_count,
                          max_peaks=self.max_peaks)
        print(f"\nLibrary Loading Complete (MSP).")
        print(f"Valid Compounds (Sorted by RI): {valid_count}")
        print(f"Skipped (No RI/Spectra):        {skipped_count}")

    def _parse_msp_compound(self, fields, peaks):
        """
        Convert MSP fields and peaks into a LibraryCompound.
        Returns None if required fields are missing.
        """
        name = field(fields, 'NAME', 'COMPOUND NAME')
        if not name:
            return None
        ri = parse_ri(fields)
        if ri is None:
            return None
        if not peaks:
            return None
        formula = field(fields, 'FORMULA', 'MOLECULAR FORMULA', default='') or ''
        metadata_clean = {k.lower(): v for k, v in fields.items()}
        peaks = _trim_spectrum([[mz, i] for mz, i in peaks], self.max_peaks)
        return LibraryCompound(name, formula, ri, peaks, metadata_clean)

    def _assign_library_indices(self):
        """
        v3.0.1: Assign unique library indices to all compounds after sorting.
        """
        for idx, comp in enumerate(self.compounds, start=1):
            comp.library_index = idx

    def get_compounds(self):
        return self.compounds
