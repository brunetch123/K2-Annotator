"""
Internal Standard Normalizer Module
Handles normalization of feature abundances by internal standard (IS) peak areas.
This module provides three methods for IS normalization:
1. Manual entry of IS values
2. Auto-detection by m/z and RI
3. Auto-detection by MSP spectrum matching
"""

import numpy as np
from pathlib import Path
from src.spectral_math import calculate_scores


class InternalStandardNormalizer:
    """
    Normalizes feature abundances using internal standard peak areas.
    Normalization is performed BEFORE BFF calculation.
    """

    def __init__(self, features, sample_names):
        """
        Initialize the normalizer.

        Args:
            features: List of Feature objects from universal_parser
            sample_names: List of all sample names (blanks + samples)
        """
        self.features = features
        self.sample_names = sample_names
        self.is_values = {}  # {sample_name: float}
        self.normalization_factors = {}  # {sample_name: float}
        self.max_is_value = 0.0
        self.missing_samples = []  # Samples without IS values
        self.is_feature_id = None  # feature used as IS (auto methods), v3.1.0

    def normalize_manual(self, is_values_dict):
        """
        Apply manual IS normalization using user-provided values.

        Args:
            is_values_dict: {sample_name: is_peak_area}

        Returns:
            bool: True if successful, False if errors
        """
        self.is_values = is_values_dict.copy()
        return self._apply_normalization()

    def normalize_auto_mz_ri(self, target_mz, mz_tolerance, target_value, value_tolerance, use_rt=False):
        """
        Auto-detect IS feature by m/z and RI (or RT), then normalize.

        Args:
            target_mz: Target m/z value
            mz_tolerance: m/z tolerance (absolute)
            target_value: Target RI or RT value
            value_tolerance: RI or RT tolerance (absolute)
            use_rt: If True, match by RT instead of RI (default: False)

        Returns:
            tuple: (success: bool, feature_id: int or None)
        """
        # Find features matching m/z and RI/RT criteria
        candidates = []
        search_param = "RT" if use_rt else "RI"

        for feat in self.features:
            # Check if feature has m/z attribute (some parsers might not set it)
            feat_mz = getattr(feat, 'mz', None)
            if feat_mz is None:
                # Try to infer from spectrum base peak
                if feat.spectrum:
                    feat_mz = max(feat.spectrum, key=lambda x: x[1])[0]
                else:
                    continue

            # Check m/z match
            if abs(feat_mz - target_mz) <= mz_tolerance:
                # Check RI or RT match
                feat_value = feat.rt if use_rt else feat.ri
                if abs(feat_value - target_value) <= value_tolerance:
                    # Calculate total abundance across all samples
                    total_abundance = sum(feat.abundances.values())
                    candidates.append((feat, total_abundance))

        if not candidates:
            print(f"[IS Normalizer] No features found matching m/z={target_mz}±{mz_tolerance}, {search_param}={target_value}±{value_tolerance}")
            return False, None

        # Select feature with highest total abundance
        candidates.sort(key=lambda x: x[1], reverse=True)
        is_feature = candidates[0][0]

        print(f"[IS Normalizer] Found IS feature: ID={is_feature.id}, Total Abundance={candidates[0][1]:.0f}")

        # Use this feature's abundances as IS values
        self.is_feature_id = is_feature.id
        self.is_values = dict(getattr(is_feature, 'raw_abundances', None) or is_feature.abundances)

        if self._apply_normalization():
            return True, is_feature.id
        else:
            return False, None

    def normalize_auto_msp(self, msp_file_path, value_tolerance=50, use_rt=False):
        """
        Auto-detect IS feature by matching MSP spectrum, then normalize.

        Args:
            msp_file_path: Path to MSP file containing IS spectrum
            value_tolerance: RI or RT tolerance for matching (default: 50)
            use_rt: If True, match by RT instead of RI (default: False)

        Returns:
            tuple: (success: bool, feature_id: int or None)
        """
        # Parse MSP file to get spectrum and RI/RT
        is_spectrum, is_value = self._parse_msp_file(msp_file_path, use_rt=use_rt)

        if not is_spectrum:
            print(f"[IS Normalizer] Failed to parse MSP file: {msp_file_path}")
            return False, None

        search_param = "RT" if use_rt else "RI"
        print(f"[IS Normalizer] Loaded IS spectrum: {len(is_spectrum)} peaks, {search_param}={is_value}")

        # Find best matching feature
        candidates = []

        for feat in self.features:
            # Skip features without spectrum
            if not feat.spectrum:
                continue

            # Check RI/RT window (if value available in MSP)
            if is_value > 0:
                feat_value = feat.rt if use_rt else feat.ri
                if abs(feat_value - is_value) > value_tolerance:
                    continue

            # Calculate spectral similarity
            scores = calculate_scores(feat.spectrum, is_spectrum)
            dot_product = scores[0]
            reverse_dot_product = scores[1]

            # Use reverse dot product as primary score (better for matching library to query)
            candidates.append((feat, reverse_dot_product, dot_product))

        if not candidates:
            print(f"[IS Normalizer] No features found matching IS spectrum")
            return False, None

        # Select feature with highest reverse dot product
        candidates.sort(key=lambda x: x[1], reverse=True)
        is_feature, rdp, dp = candidates[0]

        print(f"[IS Normalizer] Found IS feature: ID={is_feature.id}, RDP={rdp:.1f}, DP={dp:.1f}")

        # Use this feature's abundances as IS values
        self.is_feature_id = is_feature.id
        self.is_values = dict(getattr(is_feature, 'raw_abundances', None) or is_feature.abundances)

        if self._apply_normalization():
            return True, is_feature.id
        else:
            return False, None

    def _parse_msp_file(self, msp_file_path, use_rt=False):
        """
        Parse the internal-standard MSP file (first record) and return
        (spectrum, RI or RT).  Uses the shared tolerant reader (v3.1.0, D-3):
        BOM, any key case, 'Retention_index:', ';'-separated peaks.  A file
        with several records triggers a warning and the first is used.
        """
        from src.msp_reader import read_msp, parse_ri, parse_rt
        try:
            records = read_msp(msp_file_path)
        except OSError as e:
            print(f"[IS Normalizer] Error parsing MSP file: {e}")
            return [], 0.0
        if not records:
            print(f"[IS Normalizer] No records found in {msp_file_path}")
            return [], 0.0
        if len(records) > 1:
            print(f"[IS Normalizer] WARNING: {len(records)} records in {msp_file_path}; "
                  f"using the first one as the internal standard")
        fields, peaks = records[0]
        value = parse_rt(fields) if use_rt else parse_ri(fields)
        if value is None:
            print(f"[IS Normalizer] WARNING: no {'RT' if use_rt else 'RI'} field in the IS MSP; "
                  f"the retention window check is skipped")
            value = 0.0
        return [(mz, i) for mz, i in peaks], float(value)

    def _apply_normalization(self):
        """
        Apply normalization using self.is_values.

        Normalization factor = max(is_values) / is_value (NOT the median, as
        an older user guide stated), applied
        multiplicatively to feature abundances. Samples whose IS
        response is below the maximum had reduced injection efficiency
        (or matrix suppression) and so receive a factor > 1, which
        scales their feature abundances UP to the level they would
        have shown under the reference (max-IS) injection. The sample
        carrying the maximum IS keeps factor = 1.

        Prior to v3.0.7 this method computed factor = is_value /
        max(is_values), which scaled DOWN samples with lower IS
        response — the inverse of the intended correction. Reanalyses
        produced before v3.0.7 should be re-run if IS normalization
        was used.

        Returns:
            bool: True if successful
        """
        if not self.is_values:
            print("[IS Normalizer] No IS values to apply")
            return False

        # v3.1.0 (D-10): coerce and validate IS values up front so a string
        # from a hand-edited config fails with a clear message instead of a
        # TypeError deep inside the loop.
        coerced = {}
        bad = []
        for sample, v in self.is_values.items():
            try:
                coerced[sample] = float(v)
            except (TypeError, ValueError):
                bad.append((sample, v))
        if bad:
            raise ValueError(f"[IS Normalizer] non-numeric IS value(s): {bad}")
        self.is_values = coerced

        valid_is_values = {s: v for s, v in self.is_values.items() if v > 0}
        if not valid_is_values:
            print("[IS Normalizer] All IS values are zero or negative")
            return False

        self.max_is_value = max(valid_is_values.values())

        # Calculate normalization factors
        self.normalization_factors = {}
        self.missing_samples = []
        for sample in self.sample_names:
            is_val = self.is_values.get(sample, 0)
            if is_val <= 0:
                # No IS value - do not normalize this sample
                self.normalization_factors[sample] = 1.0
                self.missing_samples.append(sample)
            else:
                # factor = max(IS) / sample_IS  (>= 1 for all but the max-IS
                # sample, which keeps factor = 1).
                self.normalization_factors[sample] = self.max_is_value / is_val

        # Apply normalization to all features.  v3.1.0 (D-10): always compute
        # from the parsed (raw) abundances so calling this twice, or after an
        # earlier normalisation in the same session, gives the same result
        # instead of scaling twice.
        normalized_count = 0
        for feat in self.features:
            raw = getattr(feat, 'raw_abundances', None)
            if not raw:
                raw = dict(feat.abundances)
                feat.raw_abundances = raw
            feat.is_normalized = True
            feat.normalization_factors = {}
            for sample in self.sample_names:
                if sample in raw:
                    factor = self.normalization_factors[sample]
                    feat.abundances[sample] = raw[sample] * factor
                    feat.normalization_factors[sample] = factor
            normalized_count += 1

        print(f"[IS Normalizer] Normalized {normalized_count} features")
        print(f"[IS Normalizer] Max IS value: {self.max_is_value:.0f}")

        if self.missing_samples:
            print(f"[IS Normalizer] WARNING: {len(self.missing_samples)} samples without IS data (not normalized):")
            for smp in self.missing_samples:
                print(f"  - {smp}")

        return True

    def get_normalization_report(self):
        """
        Generate a summary report of normalization.

        Returns:
            dict: Report with IS values, factors, and missing samples
        """
        return {
            'is_values': self.is_values.copy(),
            'normalization_factors': self.normalization_factors.copy(),
            'max_is_value': self.max_is_value,
            'missing_samples': self.missing_samples.copy(),
            'total_samples': len(self.sample_names),
            'normalized_samples': len(self.sample_names) - len(self.missing_samples)
        }

    def export_factors_csv(self, output_path):
        """
        Export normalization factors to CSV for record-keeping.

        Args:
            output_path: Path to save CSV file
        """
        try:
            import csv
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(["Sample", "IS_Value", "Normalization_Factor", "Status"])
                for sample in self.sample_names:
                    is_val = self.is_values.get(sample, 0)
                    factor = self.normalization_factors.get(sample, 1.0)
                    status = "Normalized" if sample not in self.missing_samples else "Not Normalized"
                    w.writerow([sample, f"{is_val:.2f}", f"{factor:.4f}", status])

            print(f"[IS Normalizer] Exported normalization factors to: {output_path}")
            return True

        except Exception as e:
            print(f"[IS Normalizer] Error exporting factors: {e}")
            return False
