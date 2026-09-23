"""
Feature-table and spectrum parsing for MZmine and MS-DIAL outputs.

v3.1.0 changes (review findings D-1, D-2, D-3, D-10, S-BFF-1, S-RI-1):
  * every "zero of something" condition is an error, not a print
    (no quant columns, no features, no samples, no blanks unless
    `allow_no_blanks`, unknown names in `sample_types`);
  * sample names are normalised (`normalise_sample_name`) so that GUI file
    stems, `--reference-samples` and MZmine column headers with extensions
    or ``datafile:X.mzML:area`` layouts all refer to the same column;
  * MSP spectra are read through `src.msp_reader` (BOM, CRLF, any key case,
    ``;``-separated peaks, records without blank-line separators);
  * `Feature.raw_abundances` keeps the pre-normalisation abundances so IS
    normalisation is idempotent;
  * `Feature.ri_extrapolated` flags RIs derived outside the alkane range.
"""
import os
import re

import numpy as np
import pandas as pd

from src.ri_calibration import RICalibrator
from src.msp_reader import iter_msp, field


# 1.4826 makes MAD a consistent estimator of sigma under normality, so the
# adjusted-mode robust threshold reduces to mean + 3*SD when blanks truly are
# normal. MAD is preferred to SD because sparse high-magnitude blank
# detections inflate SD enough to mask real sample signal.
_MAD_TO_SIGMA = 1.4826
_SHAPIRO_ALPHA = 0.05

_SAMPLE_NAME_SUFFIXES = (' peak area', ' peak height', ':area', ':height')
_SAMPLE_NAME_EXTENSIONS = ('.mzml', '.mzxml', '.raw', '.d', '.cdf', '.wiff', '.lcd')


def normalise_sample_name(name):
    """Canonical sample name shared by the GUI, the CLI and the parsers.

    'Sample_A Peak area' -> 'Sample_A'; 'datafile:Sample_A.mzML:area' ->
    'Sample_A'; 'Sample_A.mzML' -> 'Sample_A'.  Case is preserved.
    """
    s = str(name).strip()
    if s.lower().startswith('datafile:'):
        s = s[len('datafile:'):]
    low = s.lower()
    for suf in _SAMPLE_NAME_SUFFIXES:
        if low.endswith(suf):
            s = s[:-len(suf)]
            low = s.lower()
            break
    for ext in _SAMPLE_NAME_EXTENSIONS:
        if low.endswith(ext):
            s = s[:-len(ext)]
            break
    return s.strip()


def _adjusted_bff_threshold(blank_vals):
    """
    Compute the adjusted-mode BFF threshold for a single feature.

    Returns (threshold, rule, shapiro_p, is_normal) where:
      - threshold:  float, the BFF cutoff
      - rule:       'mean_3sd' | 'median_3mad' | 'max_blank' | 'all_zero'
      - shapiro_p:  Shapiro-Wilk p-value, or None if the test couldn't run
      - is_normal:  True/False normality decision (False when test couldn't run)
    """
    arr = np.asarray(blank_vals, dtype=float) if blank_vals else np.array([], dtype=float)

    # No blanks at all -> no background to subtract.
    if arr.size == 0 or np.all(arr == 0.0):
        return 0.0, 'all_zero', None, False

    # Shapiro-Wilk needs n >= 3 and non-zero variance. When it can't run we
    # treat the feature as non-normal and fall through to MAD/fallback rules.
    can_test = arr.size >= 3 and float(np.std(arr, ddof=1)) > 0.0
    p_value = None
    is_normal = False
    if can_test:
        try:
            from scipy.stats import shapiro
            _, p_value = shapiro(arr)
            is_normal = p_value is not None and p_value >= _SHAPIRO_ALPHA
        except (ValueError, ImportError):
            p_value = None
            is_normal = False

    if is_normal:
        thr = float(np.mean(arr) + 3.0 * np.std(arr, ddof=1))
        return thr, 'mean_3sd', p_value, True

    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    if mad > 0.0:
        thr = median + 3.0 * _MAD_TO_SIGMA * mad
        return thr, 'median_3mad', p_value, False

    # MAD == 0: majority of blanks tied (typically at zero). A sample peak
    # should at minimum exceed the largest blank value ever observed.
    max_blank = float(np.max(arr))
    if max_blank > 0.0:
        return max_blank, 'max_blank', p_value, False
    return 0.0, 'all_zero', p_value, False


class Feature:
    """
    Represents a single MS alignment feature (from MS-DIAL or MZmine).
    """
    def __init__(self, alignment_id, retention_time, retention_index, mz=None):
        self.id = int(alignment_id)
        self.rt = float(retention_time) if retention_time else 0.0
        self.ri = float(retention_index) if retention_index else 0.0
        self.mz = float(mz) if mz else None  # Base m/z (v2.6.0)
        # v3.1.0 (S-RI-1): True when the RI came from outside the calibrated
        # alkane RT range (cubic-spline or linear extrapolation).
        self.ri_extrapolated = False

        # Data
        self.abundances = {}      # {sample_name: float}  (IS-normalised if IS is on)
        self.raw_abundances = {}  # {sample_name: float}  as parsed (v3.1.0, D-10)
        self.spectrum = []        # List of (mz, intensity) tuples

        # Internal Standard Normalization (v2.6.0)
        self.is_normalized = False  # Whether IS normalization was applied
        self.normalization_factors = {}  # {sample_name: factor}

        # Filtering Results
        self.bff_threshold = 0.0
        self.passed_bff = False
        self.max_sample_abundance = 0.0

        # BFF audit fields (v3.0.4): mode used, which rule produced the threshold,
        # and (adjusted mode only) the Shapiro-Wilk p-value and normality decision.
        self.bff_mode = 'standard'
        self.bff_rule = 'mean_3sd'
        self.bff_shapiro_p = None
        self.bff_normal_decision = None
        # v3.0.5: multiplier applied to the rule's raw threshold (legacy 5.0).
        self.bff_c_factor = 5.0

    def calculate_bff(self, blank_cols, sample_cols, c_factor=5.0, mode='standard'):
        """
        Calculates Blank Feature Filtering (BFF) threshold.

        mode='standard' (default; Koelmel et al. 2022, NYCSS SI S3):
            Threshold = c_factor * (Mean_Blanks + 3 * Std_Blanks)

        mode='adjusted' (NOT part of the Koelmel framework; opt-in):
            Per-feature Shapiro-Wilk normality test (alpha=0.05) on field blanks.
            - Normal blanks:  Threshold = c_factor * (Mean + 3*SD)
            - Non-normal:     Threshold = c_factor * (Median + 3 * 1.4826 * MAD)
            Fallbacks when MAD == 0:
                - any blank > 0  -> Threshold = c_factor * max(blanks)
                - all zero       -> Threshold = 0
            Shapiro can't run when all blanks are identical (zero variance) or
            when n < 3; those features are routed through the fallback rules
            as non-normal.

        Passes if max_sample_abundance > threshold (strict).
        """
        if c_factor <= 0:
            raise ValueError(f"c_factor must be > 0, got {c_factor!r}")

        blank_vals = [float(np.nan_to_num(self.abundances.get(b, 0.0))) for b in blank_cols]
        self.bff_mode = mode
        self.bff_c_factor = float(c_factor)

        if mode == 'adjusted':
            thr, rule, p, is_normal = _adjusted_bff_threshold(blank_vals)
            # Apply the same c_factor multiplier the standard rule uses, so the
            # two modes are on the same scale.
            self.bff_threshold = c_factor * thr
            self.bff_rule = rule
            self.bff_shapiro_p = p
            self.bff_normal_decision = is_normal
        else:
            # Standard mode: existing behavior, unchanged.
            if not blank_vals:
                mean_b = 0.0
                std_b = 0.0
            else:
                mean_b = np.mean(blank_vals)
                # ddof=1 for Sample Std Dev (requires at least 2 blanks)
                std_b = np.std(blank_vals, ddof=1) if len(blank_vals) > 1 else 0.0
            self.bff_threshold = c_factor * (mean_b + (3 * std_b))
            self.bff_rule = 'mean_3sd'
            self.bff_shapiro_p = None
            self.bff_normal_decision = None

        sample_vals = [float(np.nan_to_num(self.abundances.get(s, 0.0))) for s in sample_cols]
        self.max_sample_abundance = max(sample_vals) if sample_vals else 0.0

        # bool(...) so passed_bff is a Python True/False (legacy callers may
        # rely on identity checks); np.float64 > np.float64 returns np.bool_.
        self.passed_bff = bool(self.max_sample_abundance > self.bff_threshold)

    def __repr__(self):
        return f"<Feature ID={self.id} RT={self.rt:.2f} RI={self.ri:.1f} Peaks={len(self.spectrum)}>"


class UniversalParser:
    """
    Universal parser that handles both MS-DIAL and MZmine output formats.
    Automatically detects format and parses accordingly.
    """
    def __init__(self, data_dir="", blank_identifier="fieldblank", allow_no_blanks=False):
        self.data_dir = data_dir
        self.features = {}
        self.sample_columns = []
        self.blank_columns = []
        self.format_type = None  # Will be 'msdial' or 'mzmine'
        if blank_identifier is None or not str(blank_identifier).strip():
            raise ValueError("blank_identifier must be a non-empty string (e.g. 'fieldblank'); "
                             "an empty identifier would classify every column as a blank")
        self.blank_identifier = str(blank_identifier).strip().lower()
        # v3.1.0 (S-BFF-1 / D-2): blank filtering is mandatory in the Koelmel
        # framework; a run with zero blank columns is refused unless the user
        # explicitly opts out.
        self.allow_no_blanks = bool(allow_no_blanks)
        self.n_features_without_spectrum = 0

        # RI Calibration (for MZmine)
        self.ri_calibrator = None

    def set_ri_calibrator(self, calibration_file, extrapolation='spline'):
        """
        Sets up RI calibration for MZmine data (which only has RT).
        `extrapolation`: 'spline' (v3.0.x behaviour) or 'linear' outside the
        alkane range; see ri_calibration.py.
        """
        self.ri_calibrator = RICalibrator(calibration_file, extrapolation=extrapolation)

    def _path(self, filename):
        return os.path.join(self.data_dir, filename) if self.data_dir else filename

    def detect_format(self, quant_file, msp_file):
        """
        Detects whether files are from MS-DIAL or MZmine by examining headers.

        Returns: 'msdial' or 'mzmine'
        """
        msp_path = self._path(msp_file)
        if not os.path.exists(msp_path):
            raise FileNotFoundError(f"MSP file not found: {msp_path}")

        with open(msp_path, 'r', encoding='utf-8-sig', errors='replace') as f:
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
            sample_types: Optional dict {sample_name: 'sample' or 'blank'} overriding
                          auto-detection for the listed columns (others are auto-detected)
        """
        self.detect_format(quant_file, msp_file)

        if self.format_type == 'msdial':
            self.parse_msdial_area_file(quant_file, sample_types)
            self.parse_msdial_msp_file(msp_file)
        elif self.format_type == 'mzmine':
            self.parse_mzmine_quant_file(quant_file, sample_types)
            self.parse_mzmine_msp_file(msp_file)

        self._finalise_features()

    # ------------------------------------------------------------------
    # Column classification
    # ------------------------------------------------------------------
    def auto_detect_blanks(self, column_names):
        """
        Automatically detects blank columns based on configurable identifier string.
        """
        blanks, samples = [], []
        for col in column_names:
            (blanks if self.blank_identifier in col.lower() else samples).append(col)
        return blanks, samples

    def _classify_columns(self, columns, sample_types=None, file_types=None):
        """Assign every quant column to blanks or samples.

        Priority: explicit `sample_types` (names normalised) > MS-DIAL file-type
        row (`file_types`, {col: 'Blank'|'Sample'}) > blank-identifier substring.
        Raises on unknown names in `sample_types`, zero samples, and zero blanks
        (unless allow_no_blanks).  Prints the final classification.
        """
        norm_to_col = {normalise_sample_name(c): c for c in columns}
        overrides = {}
        if sample_types:
            unknown = []
            for name, typ in sample_types.items():
                key = normalise_sample_name(name)
                if key in norm_to_col:
                    overrides[norm_to_col[key]] = str(typ).strip().lower()
                elif name in columns:
                    overrides[name] = str(typ).strip().lower()
                else:
                    unknown.append(name)
            if unknown:
                raise ValueError(
                    f"sample classification names not found among the quantification "
                    f"columns: {unknown}. Available columns: {list(columns)}")

        auto_blanks, _ = self.auto_detect_blanks(columns)
        blanks, samples = [], []
        for col in columns:
            typ = overrides.get(col)
            if typ is None and file_types and col in file_types:
                typ = file_types[col].lower()
            if typ is None:
                typ = 'blank' if col in auto_blanks else 'sample'
            if typ == 'blank':
                blanks.append(col)
            elif typ in ('sample', 'reference'):
                samples.append(col)
            else:
                raise ValueError(f"unknown sample type {typ!r} for column {col!r} "
                                 f"(expected 'blank' or 'sample')")

        if not samples:
            raise ValueError(
                "No sample columns remain after classification (every column was classified "
                "as a blank). Check --blank-id / the sample grouping.")
        if not blanks:
            msg = (f"No blank columns were identified (blank identifier {self.blank_identifier!r}, "
                   f"columns: {list(columns)}). Blank feature filtering is a mandatory Level-2 "
                   f"criterion (Koelmel et al. 2022).")
            if not self.allow_no_blanks:
                raise ValueError(msg + " Fix the identifier / grouping, or pass --allow-no-blanks "
                                 "to run with an unfiltered feature list.")
            print("[WARNING] " + msg + " Continuing WITHOUT blank filtering (--allow-no-blanks).")

        self.blank_columns, self.sample_columns = blanks, samples
        print(f"Sample classification: {len(blanks)} blank(s), {len(samples)} sample(s)")
        for c in blanks:
            print(f"    BLANK   {c}")
        for c in samples:
            print(f"    SAMPLE  {c}")

    def _finalise_features(self):
        if not self.features:
            raise ValueError("No features were parsed from the quantification file.")
        missing = [f.id for f in self.features.values() if not f.spectrum]
        self.n_features_without_spectrum = len(missing)
        for f in self.features.values():
            f.raw_abundances = dict(f.abundances)
        if missing:
            print(f"[WARNING] {len(missing)} of {len(self.features)} features have no spectrum "
                  f"in the MSP file (e.g. IDs {missing[:5]}); they cannot be matched.")

    # ===== MS-DIAL PARSING =====
    def parse_msdial_area_file(self, filename, sample_types=None):
        """Parses MS-DIAL Area file format."""
        filepath = self._path(filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            lines = f.readlines()
        if len(lines) < 5:
            raise ValueError(f"{filename} has fewer than 5 lines; not an MS-DIAL area export")

        # Row 1 (Index 1) is File Type (Blank vs Sample); Row 4 (Index 4) is Headers
        file_type_row = lines[1].rstrip('\r\n').split('\t')
        header_row = lines[4].rstrip('\r\n').split('\t')

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
        columns, file_types = [], {}
        for i, col_name in enumerate(header_row):
            if not col_name or col_name in ignore_cols:
                continue
            columns.append(col_name)
            if i < len(file_type_row) and file_type_row[i] in ('Blank', 'Sample'):
                file_types[col_name] = file_type_row[i]
        if not columns:
            raise ValueError("No sample columns found in the MS-DIAL area file header (row 5)")
        self._classify_columns(columns, sample_types, file_types)

        df = pd.read_csv(filepath, sep='\t', header=4, encoding='utf-8-sig')
        if 'Alignment ID' not in df.columns:
            raise ValueError("MS-DIAL area file has no 'Alignment ID' column")

        dupes = 0
        for _, row in df.iterrows():
            if pd.isna(row['Alignment ID']):
                continue
            align_id = int(row['Alignment ID'])
            rt = self._to_float(row.get('Average Rt(min)', 0.0))
            ri = self._to_float(row.get('Average RI', 0.0))
            mz = self._to_float(row.get('Average Mz', row.get('Quant mass', None)))
            feat = Feature(align_id, rt, ri, mz or None)
            for col in self.blank_columns + self.sample_columns:
                feat.abundances[col] = self._to_float(row.get(col)) if col in row else 0.0
            if feat.id in self.features:
                dupes += 1
            self.features[feat.id] = feat
        if dupes:
            print(f"[WARNING] {dupes} duplicate Alignment ID(s) in {filename}; last occurrence kept.")
        print(f"Initialized {len(self.features)} features from MS-DIAL Area file.")

    @staticmethod
    def _to_float(val):
        try:
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return 0.0
            if isinstance(val, str) and val.strip().lower() in ('', 'null', 'nan', 'na'):
                return 0.0
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def parse_msdial_msp_file(self, filename):
        """Parses MS-DIAL MSP format (NAME: ... ID=123)."""
        self._assign_spectra(filename, r'ID=(\d+)')
        print("MS-DIAL spectra parsing complete.")

    # ===== MZMINE PARSING =====
    _MZMINE_META = {'row id', 'row m/z', 'row retention time', 'row ion mobility',
                    'row ion mobility unit', 'row ccs', 'correlation group id',
                    'annotation network number', 'best ion', 'auto ms2 verify',
                    'identified by n=', 'partners', 'neutral m mass'}

    def _mzmine_quant_columns(self, df_columns):
        """Return {sample_name: raw_column} for the quantification columns.

        Accepts '<name> Peak area', '<name> Peak height',
        'datafile:<name>:area' and 'datafile:<name>:height'; area is preferred
        when both exist for the same sample.
        """
        area, height = {}, {}
        for col in df_columns:
            c = str(col)
            low = c.lower()
            if low in self._MZMINE_META:
                continue
            if low.endswith(' peak area') or (low.startswith('datafile:') and low.endswith(':area')):
                area[normalise_sample_name(c)] = c
            elif low.endswith(' peak height') or (low.startswith('datafile:') and low.endswith(':height')):
                height[normalise_sample_name(c)] = c
        col_map = dict(height)
        col_map.update(area)
        if height and not area:
            print("[INFO] No 'Peak area' columns found; using 'Peak height' columns.")
        return col_map

    def parse_mzmine_quant_file(self, filename, sample_types=None):
        """Parses MZmine quantification CSV format."""
        filepath = self._path(filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        df = pd.read_csv(filepath, encoding='utf-8-sig')
        cols_lower = {str(c).lower(): c for c in df.columns}
        for required in ('row id', 'row retention time'):
            if required not in cols_lower:
                raise ValueError(f"MZmine quant file is missing the required column "
                                 f"'{required}'; columns present: {list(df.columns)}")
        id_col, rt_col = cols_lower['row id'], cols_lower['row retention time']
        mz_col = cols_lower.get('row m/z')

        col_map = self._mzmine_quant_columns(df.columns)
        if not col_map:
            raise ValueError(
                "No quantification columns found in the MZmine CSV (expected '<sample> Peak area', "
                "'<sample> Peak height' or 'datafile:<sample>:area'); columns present: "
                f"{list(df.columns)}")
        self._classify_columns(list(col_map.keys()), sample_types)

        dupes = 0
        for line_no, (_, row) in enumerate(df.iterrows(), 2):
            try:
                feat_id = int(row[id_col])
            except (ValueError, TypeError):
                raise ValueError(f"{filename} line {line_no}: 'row ID' is not an integer "
                                 f"({row[id_col]!r})")
            rt = self._to_float(row[rt_col])

            ri_extrapolated = False
            if self.ri_calibrator and self.ri_calibrator.is_calibrated():
                ri = self.ri_calibrator.rt_to_ri(rt)
                ri_extrapolated = not self.ri_calibrator.is_in_range(rt)
            else:
                ri = 0.0  # No RI available

            mz = self._to_float(row[mz_col]) if mz_col else None
            feat = Feature(feat_id, rt, ri, mz or None)
            feat.ri_extrapolated = ri_extrapolated
            for col in self.blank_columns + self.sample_columns:
                feat.abundances[col] = self._to_float(row[col_map[col]])
            if feat.id in self.features:
                dupes += 1
            self.features[feat.id] = feat

        if dupes:
            print(f"[WARNING] {dupes} duplicate 'row ID'(s) in {filename}; last occurrence kept.")
        print(f"Initialized {len(self.features)} features from MZmine quant file.")

    def parse_mzmine_msp_file(self, filename):
        """Parses MZmine MSP format (Name: #<id> m/z ... / DB#: <id>)."""
        self._assign_spectra(filename, r'#\s*(\d+)', alt_key='DB#')
        print("MZmine spectra parsing complete.")

    def _assign_spectra(self, filename, id_pattern, alt_key=None):
        filepath = self._path(filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        unknown_ids = 0
        for fields, peaks in iter_msp(filepath):
            name = field(fields, 'NAME', 'COMPOUND NAME', default='')
            m = re.search(id_pattern, name)
            fid = None
            if m:
                fid = int(m.group(1))
            elif alt_key is not None:
                alt = field(fields, alt_key)
                if alt and re.search(r'\d+', alt):
                    fid = int(re.search(r'\d+', alt).group(0))
            if fid is None:
                continue
            if fid in self.features:
                self.features[fid].spectrum = [(mz, i) for mz, i in peaks]
            else:
                unknown_ids += 1
        if unknown_ids:
            print(f"[WARNING] {unknown_ids} spectrum record(s) in {filename} refer to feature IDs "
                  f"absent from the quantification table.")

    # ------------------------------------------------------------------
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
