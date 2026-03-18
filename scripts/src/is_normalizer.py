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
        self.is_values = is_feature.abundances.copy()

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
        self.is_values = is_feature.abundances.copy()

        if self._apply_normalization():
            return True, is_feature.id
        else:
            return False, None

    def _parse_msp_file(self, msp_file_path, use_rt=False):
        """
        Parse MSP file to extract spectrum and RI or RT.

        Args:
            use_rt: If True, parse RT field instead of RI

        Returns:
            tuple: (spectrum: list of (mz, intensity), value: float)
        """
        spectrum = []
        ri = 0.0
        rt = 0.0

        try:
            with open(msp_file_path, 'r') as f:
                lines = f.readlines()

            in_peaks = False
            for line in lines:
                line = line.strip()

                if not line:
                    continue

                # Look for RI
                if line.upper().startswith('RETENTIONINDEX:') or line.upper().startswith('RI:') or line.upper().startswith('KOVATS:'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        try:
                            ri = float(parts[1].strip())
                        except:
                            pass

                # Look for RT (Retention Time)
                elif line.upper().startswith('RETENTIONTIME:') or line.upper().startswith('RT:') or line.upper().startswith('RETENTION TIME:'):
                    # Only parse RT if it's not RI/RETENTIONINDEX
                    if not line.upper().startswith('RTI') and not 'INDEX' in line.upper():
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            try:
                                rt = float(parts[1].strip())
                            except:
                                pass

                # Look for peak count
                elif line.upper().startswith('NUM PEAKS:') or line.upper().startswith('NUM_PEAKS:'):
                    in_peaks = True
                    continue

                # Parse peaks
                elif in_peaks:
                    # Peaks are in format: "m/z intensity" or "m/z intensity; comment"
                    parts = line.split(';')[0].strip().split()
                    if len(parts) >= 2:
                        try:
                            mz = float(parts[0])
                            intensity = float(parts[1])
                            spectrum.append((mz, intensity))
                        except:
                            pass

            # Return RT or RI based on user choice
            value = rt if use_rt else ri
            return spectrum, value

        except Exception as e:
            print(f"[IS Normalizer] Error parsing MSP file: {e}")
            return [], 0.0

    def _apply_normalization(self):
        """
        Apply normalization using self.is_values.
        Normalization factor = is_value / max(is_values)

        Returns:
            bool: True if successful
        """
        if not self.is_values:
            print("[IS Normalizer] No IS values to apply")
            return False

        # Find max IS value
        valid_is_values = {s: v for s, v in self.is_values.items() if v > 0}

        if not valid_is_values:
            print("[IS Normalizer] All IS values are zero or negative")
            return False

        self.max_is_value = max(valid_is_values.values())

        # Calculate normalization factors
        self.missing_samples = []

        for sample in self.sample_names:
            is_val = self.is_values.get(sample, 0)

            if is_val <= 0:
                # No IS value - do not normalize this sample
                self.normalization_factors[sample] = 1.0
                self.missing_samples.append(sample)
            else:
                # Calculate factor = is_value / max_is_value
                self.normalization_factors[sample] = is_val / self.max_is_value

        # Apply normalization to all features
        normalized_count = 0

        for feat in self.features:
            # Add normalization tracking attributes
            feat.is_normalized = True
            feat.normalization_factors = {}

            for sample in self.sample_names:
                if sample in feat.abundances:
                    factor = self.normalization_factors[sample]
                    original_abundance = feat.abundances[sample]

                    # Multiply abundance by normalization factor
                    feat.abundances[sample] = original_abundance * factor

                    # Store factor for this sample
                    feat.normalization_factors[sample] = factor

            normalized_count += 1

        print(f"[IS Normalizer] Normalized {normalized_count} features")
        print(f"[IS Normalizer] Max IS value: {self.max_is_value:.0f}")

        if self.missing_samples:
            print(f"[IS Normalizer] WARNING: {len(self.missing_samples)} samples without IS data (not normalized):")
            for s in self.missing_samples:
                print(f"  - {s}")

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
            with open(output_path, 'w') as f:
                f.write("Sample,IS_Value,Normalization_Factor,Status\n")

                for sample in self.sample_names:
                    is_val = self.is_values.get(sample, 0)
                    factor = self.normalization_factors.get(sample, 1.0)
                    status = "Normalized" if sample not in self.missing_samples else "Not Normalized"

                    f.write(f"{sample},{is_val:.2f},{factor:.4f},{status}\n")

            print(f"[IS Normalizer] Exported normalization factors to: {output_path}")
            return True

        except Exception as e:
            print(f"[IS Normalizer] Error exporting factors: {e}")
            return False
