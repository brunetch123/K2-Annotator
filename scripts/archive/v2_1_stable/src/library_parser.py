import csv
import sys
import json
import os

class LibraryCompound:
    """
    Represents a single compound from the Reference Library.
    """
    def __init__(self, name, formula, ri, spectrum, metadata):
        self.name = name
        self.formula = formula
        self.ri = float(ri)
        self.spectrum = spectrum  # List of [mz, intensity]
        self.metadata = metadata  # Dictionary of ALL other columns

    def __repr__(self):
        return f"<LibComp '{self.name}' RI={self.ri:.1f} Peaks={len(self.spectrum)}>"

class LibraryParser:
    def __init__(self, library_path):
        self.library_path = library_path
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

        csv.field_size_limit(sys.maxsize)

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

        return LibraryCompound(name, formula, ri, peaks, metadata_clean)

    def get_compounds(self):
        return self.compounds