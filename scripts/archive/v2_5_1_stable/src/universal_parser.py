import pandas as pd
import numpy as np
import re
import os
from src.ri_calibration import RICalibrator

class Feature:
    """
    Represents a single MS alignment feature (from MS-DIAL or MZmine).
    """
    def __init__(self, alignment_id, retention_time, retention_index):
        self.id = int(alignment_id)
        self.rt = float(retention_time) if retention_time else 0.0
        self.ri = float(retention_index) if retention_index else 0.0

        # Data
        self.abundances = {} # {sample_name: float}
        self.spectrum = []   # List of (mz, intensity) tuples

        # Filtering Results
        self.bff_threshold = 0.0
        self.passed_bff = False
        self.max_sample_abundance = 0.0

    def calculate_bff(self, blank_cols, sample_cols, c_factor=5.0):
        """
        Calculates Blank Feature Filtering (BFF) threshold.
        Threshold = c * (Mean_Blanks + 3 * Std_Blanks)
        Passes if Max_Sample_Abundance > Threshold
        """
        # 1. Get Blank Statistics
        blank_vals = [self.abundances.get(b, 0.0) for b in blank_cols]

        if not blank_vals:
            # No blanks? Assume 0 background
            mean_b = 0.0
            std_b = 0.0
        else:
            mean_b = np.mean(blank_vals)
            # ddof=1 for Sample Std Dev (requires at least 2 blanks)
            std_b = np.std(blank_vals, ddof=1) if len(blank_vals) > 1 else 0.0

        # 2. Calculate Threshold
        self.bff_threshold = c_factor * (mean_b + (3 * std_b))

        # 3. Check Samples
        sample_vals = [self.abundances.get(s, 0.0) for s in sample_cols]
        self.max_sample_abundance = max(sample_vals) if sample_vals else 0.0

        # 4. Result
        if self.max_sample_abundance > self.bff_threshold:
            self.passed_bff = True
        else:
            self.passed_bff = False

    def __repr__(self):
        return f"<Feature ID={self.id} RT={self.rt:.2f} RI={self.ri:.1f} Peaks={len(self.spectrum)}>"


class UniversalParser:
    """
    Universal parser that handles both MS-DIAL and MZmine output formats.
    Automatically detects format and parses accordingly.
    """
    def __init__(self, data_dir="", blank_identifier="fieldblank"):
        self.data_dir = data_dir
        self.features = {}
        self.sample_columns = []
        self.blank_columns = []
        self.format_type = None  # Will be 'msdial' or 'mzmine'
        self.blank_identifier = blank_identifier.lower()

        # RI Calibration (for MZmine)
        self.ri_calibrator = None

    def set_ri_calibrator(self, calibration_file):
        """
        Sets up RI calibration for MZmine data (which only has RT).
        """
        self.ri_calibrator = RICalibrator(calibration_file)

    def detect_format(self, quant_file, msp_file):
        """
        Detects whether files are from MS-DIAL or MZmine by examining headers.

        Returns: 'msdial' or 'mzmine'
        """
        # Check MSP file first
        msp_path = os.path.join(self.data_dir, msp_file) if self.data_dir else msp_file

        if not os.path.exists(msp_path):
            raise FileNotFoundError(f"MSP file not found: {msp_path}")

        with open(msp_path, 'r') as f:
            first_lines = [f.readline() for _ in range(10)]

        msp_text = "".join(first_lines)

        # MZmine MSP format uses: "Name: #1 m/z X.XX (Y.YY min)"
        # MS-DIAL MSP format uses: "NAME: Unknown ID=123"
        if re.search(r'Name:\s+#\d+\s+m/z', msp_text, re.IGNORECASE):
            self.format_type = 'mzmine'
            print("Detected format: MZmine")
        elif re.search(r'NAME:.*ID=\d+', msp_text, re.IGNORECASE):
            self.format_type = 'msdial'
            print("Detected format: MS-DIAL")
        else:
            raise ValueError("Cannot determine file format. MSP file does not match MS-DIAL or MZmine patterns.")

        return self.format_type

    def parse_files(self, quant_file, msp_file, sample_types=None):
        """
        Main entry point: detects format and parses both quantification and spectral files.

        Args:
            quant_file: Path to quantification file (.txt for MS-DIAL, .csv for MZmine)
            msp_file: Path to MSP spectral file
            sample_types: Optional dict {sample_name: 'sample' or 'blank'} to override auto-detection
        """
        # Detect format
        self.detect_format(quant_file, msp_file)

        # Parse based on format
        if self.format_type == 'msdial':
            self.parse_msdial_area_file(quant_file, sample_types)
            self.parse_msdial_msp_file(msp_file)
        elif self.format_type == 'mzmine':
            self.parse_mzmine_quant_file(quant_file, sample_types)
            self.parse_mzmine_msp_file(msp_file)

    def auto_detect_blanks(self, column_names):
        """
        Automatically detects blank columns based on configurable identifier string.
        """
        blanks = []
        samples = []

        for col in column_names:
            if self.blank_identifier in col.lower():
                blanks.append(col)
            else:
                samples.append(col)

        return blanks, samples

    # ===== MS-DIAL PARSING =====
    def parse_msdial_area_file(self, filename, sample_types=None):
        """Parses MS-DIAL Area file format."""
        filepath = os.path.join(self.data_dir, filename) if self.data_dir else filename
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, 'r') as f:
            lines = f.readlines()

        if len(lines) < 5:
            print(f"Warning: {filename} has fewer than 5 lines. Skipping.")
            return

        # Row 1 (Index 1) is File Type (Blank vs Sample)
        file_type_row = lines[1].rstrip('\n').split('\t')
        # Row 4 (Index 4) is Headers
        header_row = lines[4].rstrip('\n').split('\t')

        # Metadata columns to ignore
        ignore_cols = {
            "Alignment ID", "Average Rt(min)", "Average RI", "Quant mass",
            "Metabolite name", "Compound name", "Fill %", "Reference RT", "Reference RI",
            "Formula", "Ontology", "INCHIKEY", "SMILES", "Annotation tag (VS1.0)",
            "RT/RI matched", "EI-MS matched", "Comment", "Manually modified for quantification",
            "Manually modified for annotation", "Total score", "RT similarity", "RI similarity",
            "Total spectrum similarity", "Dot product", "Reverse dot product", "Fragment presence %",
            "S/N average", "Spectrum reference file name", "EI spectrum", "Class", "File type",
            "Injection order", "Batch ID"
        }

        self.blank_columns = []
        self.sample_columns = []

        # Map columns
        for i, col_name in enumerate(header_row):
            if col_name in ignore_cols: continue

            # Use provided sample_types if available
            if sample_types and col_name in sample_types:
                if sample_types[col_name] == 'blank':
                    self.blank_columns.append(col_name)
                elif sample_types[col_name] == 'sample':
                    self.sample_columns.append(col_name)
            # Otherwise use file type row
            elif i < len(file_type_row):
                f_type = file_type_row[i]
                if f_type == 'Blank':
                    self.blank_columns.append(col_name)
                elif f_type == 'Sample':
                    self.sample_columns.append(col_name)

        print(f"Parsed MS-DIAL Structure: Found {len(self.blank_columns)} Blanks and {len(self.sample_columns)} Samples.")

        # Load Data
        try:
            df = pd.read_csv(filepath, sep='\t', header=4)
        except Exception as e:
            print(f"Error reading {filename} with pandas: {e}")
            return

        for _, row in df.iterrows():
            # ID
            try:
                if 'Alignment ID' not in row or pd.isna(row['Alignment ID']):
                    continue
                align_id = int(row['Alignment ID'])
            except (ValueError, TypeError):
                continue

            # RT/RI
            rt = row.get('Average Rt(min)', 0.0)
            ri_raw = row.get('Average RI', 0.0)
            ri = 0.0
            try:
                if not pd.isna(ri_raw) and ri_raw != 'null':
                    ri = float(ri_raw)
            except ValueError:
                ri = 0.0

            feat = Feature(align_id, rt, ri)

            # Extract abundances
            all_cols = self.blank_columns + self.sample_columns
            for col in all_cols:
                if col in row:
                    val = row[col]
                    try:
                        if pd.isna(val) or val == 'null' or val == '':
                            feat.abundances[col] = 0.0
                        else:
                            feat.abundances[col] = float(val)
                    except (ValueError, TypeError):
                        feat.abundances[col] = 0.0

            self.features[feat.id] = feat

        print(f"Initialized {len(self.features)} features from MS-DIAL Area file.")

    def parse_msdial_msp_file(self, filename):
        """Parses MS-DIAL MSP format."""
        filepath = os.path.join(self.data_dir, filename) if self.data_dir else filename
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        current_id = None
        current_spectrum = []

        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line: continue

                if line.startswith('NAME:'):
                    if current_id is not None and current_id in self.features:
                        self.features[current_id].spectrum = current_spectrum
                    current_spectrum = []

                    match = re.search(r'ID=(\d+)', line)
                    if match:
                        current_id = int(match.group(1))
                    else:
                        current_id = None

                elif line[0].isdigit():
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            mz = float(parts[0])
                            intent = float(parts[1])
                            current_spectrum.append((mz, intent))
                        except ValueError:
                            pass

        if current_id is not None and current_id in self.features:
            self.features[current_id].spectrum = current_spectrum

        print("MS-DIAL spectra parsing complete.")

    # ===== MZMINE PARSING =====
    def parse_mzmine_quant_file(self, filename, sample_types=None):
        """Parses MZmine quantification CSV format."""
        filepath = os.path.join(self.data_dir, filename) if self.data_dir else filename
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            print(f"Error reading MZmine CSV file: {e}")
            return

        # Identify quantification columns (end with "Peak area")
        metadata_cols = ['row ID', 'row m/z', 'row retention time', 'row ion mobility',
                        'row ion mobility unit', 'row CCS', 'correlation group ID',
                        'annotation network number', 'best ion', 'auto MS2 verify',
                        'identified by n=', 'partners', 'neutral M mass']

        raw_quant_cols = [col for col in df.columns if col not in metadata_cols and 'Peak area' in col]
        
        # Strip " Peak area" for internal tracking and matching with sample_grouping
        quant_cols = [col.replace(' Peak area', '') for col in raw_quant_cols]
        col_map = {col.replace(' Peak area', ''): col for col in raw_quant_cols}

        # Auto-detect or use provided sample types
        if sample_types:
            self.blank_columns = [col for col in quant_cols if sample_types.get(col) == 'blank']
            self.sample_columns = [col for col in quant_cols if sample_types.get(col) == 'sample']
        else:
            self.blank_columns, self.sample_columns = self.auto_detect_blanks(quant_cols)

        print(f"Parsed MZmine Structure: Found {len(self.blank_columns)} Blanks and {len(self.sample_columns)} Samples.")

        # Parse each row
        for _, row in df.iterrows():
            try:
                feat_id = int(row['row ID'])
                rt = float(row['row retention time'])

                # Calculate RI from RT using calibration
                if self.ri_calibrator and self.ri_calibrator.is_calibrated():
                    ri = self.ri_calibrator.rt_to_ri(rt)
                else:
                    ri = 0.0  # No RI available

                feat = Feature(feat_id, rt, ri)

                # Extract abundances
                all_cols = self.blank_columns + self.sample_columns
                for col in all_cols:
                    raw_col = col_map.get(col, col)
                    if raw_col in row:
                        val = row[raw_col]
                        try:
                            if pd.isna(val) or val == '':
                                feat.abundances[col] = 0.0
                            else:
                                feat.abundances[col] = float(val)
                        except (ValueError, TypeError):
                            feat.abundances[col] = 0.0

                self.features[feat.id] = feat

            except (ValueError, KeyError, TypeError) as e:
                continue  # Skip invalid rows

        print(f"Initialized {len(self.features)} features from MZmine quant file.")

    def parse_mzmine_msp_file(self, filename):
        """Parses MZmine MSP format."""
        filepath = os.path.join(self.data_dir, filename) if self.data_dir else filename
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        current_id = None
        current_spectrum = []
        reading_peaks = False

        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    # Empty line signals end of entry
                    if current_id is not None and current_id in self.features:
                        self.features[current_id].spectrum = current_spectrum
                    current_id = None
                    current_spectrum = []
                    reading_peaks = False
                    continue

                # Parse header lines
                if line.startswith('Name:'):
                    # Format: "Name: #1 m/z 85.1010 (3.02 min)"
                    match = re.search(r'#(\d+)', line)
                    if match:
                        current_id = int(match.group(1))

                elif line.startswith('DB#:'):
                    # Alternative ID parsing
                    match = re.search(r'DB#:\s*(\d+)', line)
                    if match and current_id is None:
                        current_id = int(match.group(1))

                elif line.startswith('RT:'):
                    # RT is already parsed from quant file, skip
                    pass

                elif line.startswith('Num Features:') or line.startswith('Num Peaks:'):
                    # Start reading peaks after this line
                    reading_peaks = True

                elif reading_peaks and line[0].isdigit():
                    # Peak data: "m/z intensity"
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            mz = float(parts[0])
                            intensity = float(parts[1])
                            current_spectrum.append((mz, intensity))
                        except ValueError:
                            pass

        # Handle last entry
        if current_id is not None and current_id in self.features:
            self.features[current_id].spectrum = current_spectrum

        print("MZmine spectra parsing complete.")

    def get_feature_list(self):
        """Returns list of all features."""
        return list(self.features.values())

    def get_sample_columns_for_assignment(self):
        """
        Returns all sample columns (blanks + samples) for manual assignment in GUI.
        Returns dict: {column_name: auto_detected_type}
        """
        result = {}
        for col in self.blank_columns:
            result[col] = 'blank'
        for col in self.sample_columns:
            result[col] = 'sample'
        return result

    def set_sample_types(self, sample_types_dict):
        """
        Manually sets sample types after auto-detection.
        Args:
            sample_types_dict: {sample_name: 'sample' or 'blank'}
        """
        self.blank_columns = [k for k, v in sample_types_dict.items() if v == 'blank']
        self.sample_columns = [k for k, v in sample_types_dict.items() if v == 'sample']

        print(f"Sample types updated: {len(self.blank_columns)} Blanks, {len(self.sample_columns)} Samples")
