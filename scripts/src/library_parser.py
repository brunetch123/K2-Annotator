import csv
import sys
import json
import os


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
    # Pick top-N by intensity. Defensive cast in case peaks are
    # lists vs tuples or carry strange types (library JSON is
    # user-supplied and we've seen the occasional surprise).
    try:
        top = sorted(peaks, key=lambda p: -float(p[1]))[:max_peaks]
    except (TypeError, ValueError, IndexError):
        return peaks
    # Re-sort to m/z asc so PDF mirror plots, CSV dumps, etc. still
    # see a conventionally-ordered spectrum.
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
        self.metadata = metadata  # Dictionary of ALL other columns
        self.library_index = library_index  # v3.0.1: Unique ID within loaded library

    def __repr__(self):
        return f"<LibComp '{self.name}' RI={self.ri:.1f} Peaks={len(self.spectrum)} LibIdx={self.library_index}>"

class LibraryParser:
    def __init__(self, library_path, max_peaks=MAX_LIB_PEAKS_DEFAULT):
        self.library_path = library_path
        self.max_peaks = max_peaks  # v3.0.19: per-compound spectrum trim
        self.compounds = []

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

        # Detect format
        ext = os.path.splitext(self.library_path)[1].lower()

        if ext == '.msp':
            self._load_msp()
        elif ext == '.csv':
            self._load_csv()
        else:
            raise ValueError(f"Unsupported library format: {ext}. Expected .csv or .msp")

    def _load_csv(self):
        """
        Stream reads the CSV library.
        """

        # Bump CSV field size cap to handle very long peaks_json columns.
        # sys.maxsize is 2**63-1 on 64-bit Python, but csv.field_size_limit
        # takes a C long, which is 32-bit on Windows even in 64-bit builds.
        # Halve until it fits.
        max_int = sys.maxsize
        while True:
            try:
                csv.field_size_limit(max_int)
                break
            except OverflowError:
                max_int = int(max_int / 10)


        valid_count = 0
        skipped_count = 0

        with open(self.library_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            # Map columns
            col_map = {name: i for i, name in enumerate(header)}
            
            # Critical Indices
            try:
                idx_name = col_map.get('name')
                idx_formula = col_map.get('formula')
                idx_ri = col_map.get('ri')
                idx_peaks = col_map.get('peaks_json')
                
                if any(idx is None for idx in [idx_name, idx_formula, idx_ri, idx_peaks]):
                    missing = [k for k in ['name', 'formula', 'ri', 'peaks_json'] if col_map.get(k) is None]
                    raise ValueError(f"Library CSV is missing required columns: {missing}")
            except Exception as e:
                raise ValueError(f"Error parsing library header: {e}")

            for row_idx, row in enumerate(reader):
                if not row: continue # Skip empty rows
                
                # 1. Check RI
                try:
                    ri_str = row[idx_ri] if len(row) > idx_ri else ""
                    if not ri_str or ri_str.strip() == "":
                        skipped_count += 1
                        continue
                    ri_val = float(ri_str)
                except (ValueError, IndexError):
                    skipped_count += 1
                    continue

                # 2. Check Spectrum
                try:
                    peaks_str = row[idx_peaks] if len(row) > idx_peaks else "[]"
                    spectrum = json.loads(peaks_str)
                    if not spectrum or not isinstance(spectrum, list):
                        skipped_count += 1
                        continue
                except (json.JSONDecodeError, IndexError):
                    skipped_count += 1
                    continue

                # v3.0.19: trim to top-N peaks by intensity before
                # the compound is stored. See _trim_spectrum docstring.
                spectrum = _trim_spectrum(spectrum, self.max_peaks)

                # 3. Capture Metadata (Everything in the row)
                # We store it as a dictionary {ColumnName: Value}
                metadata = {}
                for col_name, idx in col_map.items():
                    if idx < len(row):
                        metadata[col_name] = row[idx]
                    else:
                        metadata[col_name] = ""

                # 4. Create Object
                name = row[idx_name] if len(row) > idx_name else "Unknown"
                formula = row[idx_formula] if len(row) > idx_formula else ""

                comp = LibraryCompound(name, formula, ri_val, spectrum, metadata)
                self.compounds.append(comp)
                valid_count += 1
                
                if valid_count % 5000 == 0:
                    print(f"Loaded {valid_count} valid compounds...", end='\r')

        # SORT the library by RI immediately for binary search optimization
        self.compounds.sort(key=lambda x: x.ri)
        
        # v3.0.1: Assign unique library indices after sorting
        self._assign_library_indices()

        print(f"\nLibrary Loading Complete (CSV).")
        print(f"Valid Compounds (Sorted by RI): {valid_count}")
        print(f"Skipped (No RI/Spectra):        {skipped_count}")

    def _load_msp(self):
        """
        Load library from MSP format (NIST/MassBank style).

        Required fields in MSP:
        - NAME: Compound name
        - RI: or RetentionIndex: Retention Index value
        - FORMULA: Molecular formula (optional but recommended)
        - Num Peaks: Number of spectral peaks
        - Peak list: m/z intensity pairs

        Optional fields become metadata.
        """
        valid_count = 0
        skipped_count = 0

        with open(self.library_path, 'r', encoding='utf-8', errors='replace') as f:
            current_compound = {}
            current_peaks = []
            reading_peaks = False
            num_peaks = 0

            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines between compounds
                if not line:
                    # Save compound if we have one
                    if current_compound:
                        comp = self._parse_msp_compound(current_compound, current_peaks)
                        if comp:
                            self.compounds.append(comp)
                            valid_count += 1
                        else:
                            skipped_count += 1

                        # Reset for next compound
                        current_compound = {}
                        current_peaks = []
                        reading_peaks = False
                        num_peaks = 0
                    continue

                # Reading spectral peaks
                if reading_peaks:
                    try:
                        parts = line.split()
                        if len(parts) >= 2:
                            mz = float(parts[0])
                            intensity = float(parts[1])
                            current_peaks.append([mz, intensity])

                            # Check if we've read all peaks
                            if len(current_peaks) >= num_peaks:
                                reading_peaks = False
                    except ValueError:
                        pass  # Skip malformed peak lines
                    continue

                # Parse metadata fields
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().upper()
                    value = value.strip()

                    # Store all fields
                    current_compound[key] = value

                    # Check for Num Peaks to start reading spectrum
                    if key == 'NUM PEAKS':
                        try:
                            num_peaks = int(value)
                            if num_peaks > 0:
                                reading_peaks = True
                        except ValueError:
                            pass

            # Don't forget last compound
            if current_compound:
                comp = self._parse_msp_compound(current_compound, current_peaks)
                if comp:
                    self.compounds.append(comp)
                    valid_count += 1
                else:
                    skipped_count += 1

        # SORT the library by RI immediately
        self.compounds.sort(key=lambda x: x.ri)
        
        # v3.0.1: Assign unique library indices after sorting
        self._assign_library_indices()

        print(f"\nLibrary Loading Complete (MSP).")
        print(f"Valid Compounds (Sorted by RI): {valid_count}")
        print(f"Skipped (No RI/Spectra):        {skipped_count}")

    def _parse_msp_compound(self, metadata, peaks):
        """
        Convert MSP metadata and peaks into LibraryCompound object.
        Returns None if required fields are missing.
        """
        # Required: NAME
        name = metadata.get('NAME') or metadata.get('COMPOUND NAME')
        if not name:
            return None

        # Required: RI (check multiple possible field names)
        ri_str = (metadata.get('RI') or
                  metadata.get('RETENTIONINDEX') or
                  metadata.get('RETENTION INDEX') or
                  metadata.get('KOVATS'))
        if not ri_str:
            return None

        try:
            ri = float(ri_str)
        except ValueError:
            return None

        # Required: Valid spectrum
        if not peaks or len(peaks) == 0:
            return None

        # Optional: Formula
        formula = metadata.get('FORMULA') or metadata.get('MOLECULAR FORMULA') or ""

        # Convert metadata keys to lowercase for consistency
        metadata_clean = {k.lower(): v for k, v in metadata.items()}

        # v3.0.19: trim to top-N peaks by intensity before stash.
        peaks = _trim_spectrum(peaks, self.max_peaks)

        return LibraryCompound(name, formula, ri, peaks, metadata_clean)

    def _assign_library_indices(self):
        """
        v3.0.1: Assign unique library indices to all compounds after sorting.
        This ensures each library entry has a unique ID for tracking through
        the matching pipeline, even when the same compound appears multiple times.
        """
        for idx, comp in enumerate(self.compounds, start=1):
            comp.library_index = idx

    def get_compounds(self):
        return self.compounds