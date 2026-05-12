from src.universal_parser import UniversalParser
from src.library_parser import LibraryParser, MAX_LIB_PEAKS_DEFAULT
from src.spectral_math import calculate_scores
from src.rhrmf import (calculate_rhrmf, is_library_high_res,
                       FormulaExplainer)
# K2_DIAG_VARIANT: side-by-side RHRMF variant scoring for Options 1/2/3.
# Only imported (and called) when the diagnostic env var is set; production
# matching uses calculate_rhrmf exclusively.
from src.rhrmf import calculate_rhrmf_variant
from src.is_normalizer import InternalStandardNormalizer
import bisect
import time
# K2_DIAG: temporary diagnostic — see _diag_* methods. Remove with the
# rest of the K2_DIAG-tagged blocks when the HR-matching investigation
# is done.
import csv
import os

class MatchCandidate:
    def __init__(self, library_compound, scores, error_ri):
        self.compound = library_compound
        self.dot_product = scores[0]
        self.reverse_dot_product = scores[1]
        self.ri_error = error_ri
        
        # New attributes for Phase 4
        self.rhrmf_score = 0.0
        self.is_high_res_match = False
        self.final_pass = False

class MatchingEngine:
    def __init__(self, data_dir, quant_file, msp_file, library_file, ri_cal_file=None, blank_identifier="fieldblank",
                 sample_types=None, is_config=None, reference_samples=None, bff_mode='standard',
                 bff_c_factor=5.0, max_lib_peaks=MAX_LIB_PEAKS_DEFAULT):
        self.data_dir = data_dir
        self.quant_file = quant_file  # Changed from area_file to quant_file (more generic)
        self.msp_file = msp_file
        self.library_file = library_file
        self.ri_cal_file = ri_cal_file
        self.blank_identifier = blank_identifier
        self.sample_types = sample_types  # Optional: {sample_name: 'sample' or 'blank'}

        # Internal Standard Configuration (v2.6.0)
        self.is_config = is_config or {}  # Dict with IS normalization parameters

        # v3.0.0: Reference samples to exclude from suspect screening
        self.reference_samples = set(reference_samples) if reference_samples else set()

        # v3.0.4: BFF rule selector — 'standard' (legacy mean+3SD) or 'adjusted'
        # (Shapiro-gated MAD-based rule). Default preserves existing outputs.
        if bff_mode not in ('standard', 'adjusted'):
            raise ValueError(f"bff_mode must be 'standard' or 'adjusted', got {bff_mode!r}")
        self.bff_mode = bff_mode

        # v3.0.5: multiplier applied to the per-feature raw threshold. Legacy
        # default is 5.0; users may set 1, 2, etc. to relax the filter.
        try:
            self.bff_c_factor = float(bff_c_factor)
        except (TypeError, ValueError):
            raise ValueError(f"bff_c_factor must be a number, got {bff_c_factor!r}")
        if self.bff_c_factor <= 0:
            raise ValueError(f"bff_c_factor must be > 0, got {self.bff_c_factor}")

        # v3.0.19: top-N peak trim applied at library load.
        try:
            self.max_lib_peaks = int(max_lib_peaks) if max_lib_peaks else 0
        except (TypeError, ValueError):
            raise ValueError(
                f"max_lib_peaks must be an integer (or 0/None to disable "
                f"trimming), got {max_lib_peaks!r}")
        if self.max_lib_peaks < 0:
            raise ValueError(
                f"max_lib_peaks must be >= 0 (0 disables trimming), "
                f"got {self.max_lib_peaks}")

        self.parser = None  # Changed from msdial_parser to parser (universal)
        self.library_parser = None

        # Initialize the Formula Explainer once (it builds a cache)
        self.explainer = FormulaExplainer()

        self.results = {}

        # K2_DIAG: per-candidate scoring trace, gated on env var. Used
        # to investigate why high-res libraries produce fewer Level-2
        # matches than low-res. When K2_DIAG_MATCHING_CSV is set, every
        # candidate that survives the RI bisect window is recorded —
        # whether it passed/failed the RI %-error, dot-product, and
        # RHRMF gates — and the CSV is written after run_matching().
        # When unset, _diag_path is None and the diag captures are
        # no-ops. Remove ALL K2_DIAG-tagged blocks to revert.
        self._diag_path = os.environ.get('K2_DIAG_MATCHING_CSV') or None
        self._diag_rows = []

    def load_data(self):
        print("--- Loading Data ---")
        # 1. Initialize Universal Parser
        self.parser = UniversalParser(self.data_dir, blank_identifier=self.blank_identifier)

        # 2. Set RI Calibrator if provided (for MZmine)
        if self.ri_cal_file:
            print(f"Loading RI calibration from: {self.ri_cal_file}")
            self.parser.set_ri_calibrator(self.ri_cal_file)

        # 3. Parse Files (auto-detects format)
        print("Parsing quantification and spectral files...")
        self.parser.parse_files(self.quant_file, self.msp_file, sample_types=self.sample_types)

        # 4. Internal Standard Normalization (v2.6.0) - BEFORE BFF
        features = self.parser.get_feature_list()
        if self.is_config.get('enabled', False):
            print("\n--- Applying Internal Standard Normalization ---")
            all_samples = self.parser.blank_columns + self.parser.sample_columns
            normalizer = InternalStandardNormalizer(features, all_samples)

            method = self.is_config.get('method', 'manual')

            if method == 'manual':
                is_values = self.is_config.get('is_values', {})
                success = normalizer.normalize_manual(is_values)
                if not success:
                    print("[WARNING] Manual IS normalization failed")

            elif method == 'mz_ri':
                target_mz = self.is_config.get('target_mz', 0)
                mz_tol = self.is_config.get('mz_tolerance', 0.5)
                target_value = self.is_config.get('target_value', self.is_config.get('target_ri', 0))  # v2.7.0: renamed
                value_tol = self.is_config.get('value_tolerance', self.is_config.get('ri_tolerance', 50))  # v2.7.0: renamed
                use_rt = self.is_config.get('use_rt', False)  # v2.7.0: RT or RI selection
                success, feat_id = normalizer.normalize_auto_mz_ri(target_mz, mz_tol, target_value, value_tol, use_rt)
                if not success:
                    param_name = "RT" if use_rt else "RI"
                    print(f"[WARNING] Auto m/z+{param_name} IS normalization failed")

            elif method == 'msp':
                msp_file = self.is_config.get('msp_file', '')
                value_tol = self.is_config.get('value_tolerance', self.is_config.get('ri_tolerance', 50))  # v2.7.0: renamed
                use_rt = self.is_config.get('use_rt', False)  # v2.7.0: RT or RI selection
                success, feat_id = normalizer.normalize_auto_msp(msp_file, value_tol, use_rt)
                if not success:
                    print("[WARNING] Auto MSP IS normalization failed")

            # Export normalization report if requested
            if self.is_config.get('export_report', False):
                output_path = self.is_config.get('report_path', 'is_normalization_report.csv')
                normalizer.export_factors_csv(output_path)

        # 5. Run BFF (Pre-requisite for matching) - Uses normalized abundances if IS was applied
        # v3.0.0: Exclude reference samples from BFF calculation for suspect screening
        # v3.0.4: BFF mode (standard|adjusted) is plumbed in from caller.
        print(f"\nRunning BFF Filter (mode={self.bff_mode}, c_factor={self.bff_c_factor})...")
        sample_cols_for_bff = [s for s in self.parser.sample_columns if s not in self.reference_samples]

        if self.reference_samples:
            print(f"  Excluding {len(self.reference_samples)} reference samples from BFF calculation")

        for f in features:
            f.calculate_bff(self.parser.blank_columns, sample_cols_for_bff,
                            c_factor=self.bff_c_factor, mode=self.bff_mode)

        # 6. Load Library
        print(f"Loading Library (top-{self.max_lib_peaks or 'all'} peaks "
              f"per compound)...")
        self.library_parser = LibraryParser(self.library_file,
                                            max_peaks=self.max_lib_peaks)
        self.library_parser.load_library()
        
    def run_matching(self):
        print("\n--- Starting Level 2 Matching Engine (w/ RHRMF) ---")

        features = self.parser.get_feature_list()
        library = self.library_parser.get_compounds()
        
        # Pre-calculate library RI list for binary searching
        lib_ris = [c.ri for c in library]
        
        matches_found = 0
        
        # For progress tracking
        total_feats = len(features)
        
        for idx, feat in enumerate(features):
            if idx % 100 == 0:
                print(f"Processed {idx}/{total_feats} features...", end='\r')
            
            # 1. Filter: BFF
            if not feat.passed_bff:
                continue
                
            # 2. Filter: RI Window (Binary Search)
            # We want library items where RI is within feat.ri +/- 50
            ri_min = feat.ri - 50
            ri_max = feat.ri + 50
            
            # Find indices in sorted library
            start_idx = bisect.bisect_left(lib_ris, ri_min)
            end_idx = bisect.bisect_right(lib_ris, ri_max)
            
            # 3. Iterate Candidates in Window
            candidates = []
            
            for i in range(start_idx, end_idx):
                lib_comp = library[i]

                # Double Check: RI % Error (< 1.5%)
                delta_ri = abs(feat.ri - lib_comp.ri)
                percent_error = (delta_ri / feat.ri) * 100 if feat.ri > 0 else 100

                if percent_error > 1.5:
                    # K2_DIAG: record candidate as failing RI %-error gate
                    self._diag_capture(
                        feat=feat, lib_comp=lib_comp,
                        delta_ri=delta_ri, ri_pct_error=percent_error,
                        passed_ri=False, gate_failed='ri_pct',
                    )
                    continue

                # 4. Spectral Matching (Unit Res)
                # Only run expensive math if RI passes
                dot, rev_dot = calculate_scores(feat.spectrum, lib_comp.spectrum)

                # K2_DIAG: classify HR up-front so the diagnostic can see
                # is_hr for every candidate, not just those that pass dots.
                is_hr = is_library_high_res(lib_comp.spectrum)

                # 5. Thresholds (Level 2 Criteria)
                # Rev Dot > 600 AND Dot > 500
                if rev_dot > 600 and dot > 500:
                    cand = MatchCandidate(lib_comp, (dot, rev_dot), delta_ri)
                    cand.is_high_res_match = is_hr

                    if is_hr:
                        # High Res Library Match: Pass automatically (assuming spectral score holds)
                        cand.rhrmf_score = 100.0 # Placeholder
                        cand.final_pass = True
                    else:
                        # Low Res Library Match: Must pass RHRMF > 75
                        score = calculate_rhrmf(feat.spectrum, lib_comp, self.explainer)
                        cand.rhrmf_score = score

                        if score > 75:
                            cand.final_pass = True
                        else:
                            cand.final_pass = False

                    # Only add if it passed the final High Res / RHRMF check
                    if cand.final_pass:
                        candidates.append(cand)

                    # K2_DIAG_VARIANT: compute all four RHRMF variants
                    # side-by-side for the comparison investigation. Only
                    # done when the diagnostic CSV is enabled, since each
                    # candidate now costs 4× the RHRMF compute. Bounded
                    # by the dot-product gate so total compute is small.
                    opt0 = opt1 = opt2 = opt3 = None
                    if self._diag_path is not None:
                        # Option 0: explicit production-equivalent score,
                        # computed even for HR (production uses 100.0
                        # sentinel for HR; here we always run the real
                        # algorithm so the diagnostic columns are
                        # comparable across is_hr=True and is_hr=False).
                        opt0 = calculate_rhrmf(
                            feat.spectrum, lib_comp, self.explainer)
                        opt1 = calculate_rhrmf_variant(
                            feat.spectrum, lib_comp, self.explainer,
                            tolerance_ppm=10,
                            include_isotopologues=False,
                            score_mode='count')
                        opt2 = calculate_rhrmf_variant(
                            feat.spectrum, lib_comp, self.explainer,
                            tolerance_ppm=10,
                            include_isotopologues=True,
                            score_mode='count')
                        opt3 = calculate_rhrmf_variant(
                            feat.spectrum, lib_comp, self.explainer,
                            tolerance_ppm=10,
                            include_isotopologues=True,
                            score_mode='tic')

                    # K2_DIAG: record candidate after dot+RHRMF evaluation
                    self._diag_capture(
                        feat=feat, lib_comp=lib_comp,
                        delta_ri=delta_ri, ri_pct_error=percent_error,
                        passed_ri=True,
                        dot=dot, rev_dot=rev_dot,
                        passed_dot_thresholds=True,
                        is_hr=is_hr,
                        rhrmf_score=cand.rhrmf_score,
                        final_pass=cand.final_pass,
                        gate_failed=(None if cand.final_pass else 'rhrmf'),
                        # K2_DIAG_VARIANT: side-by-side scores
                        rhrmf_opt0=opt0,
                        rhrmf_opt1=opt1,
                        rhrmf_opt2=opt2,
                        rhrmf_opt3=opt3,
                    )
                else:
                    # K2_DIAG: record candidate as failing dot-product gate
                    self._diag_capture(
                        feat=feat, lib_comp=lib_comp,
                        delta_ri=delta_ri, ri_pct_error=percent_error,
                        passed_ri=True,
                        dot=dot, rev_dot=rev_dot,
                        passed_dot_thresholds=False,
                        is_hr=is_hr,
                        rhrmf_score=None, final_pass=False,
                        gate_failed='dot_product',
                    )
            
            # Store if we found valid candidates
            if candidates:
                # Sort by Reverse Dot Product (descending)
                candidates.sort(key=lambda x: x.reverse_dot_product, reverse=True)
                self.results[feat.id] = candidates
                matches_found += 1

        print(f"\nMatching Complete.")
        print(f"Features with Level 2 Matches (Post-RHRMF): {matches_found}")

        # K2_DIAG: flush per-candidate trace to CSV if enabled
        self._diag_flush_csv()

    def get_results(self):
        return self.results

    # ====================================================================
    # K2_DIAG: temporary diagnostic — investigate why HR libraries produce
    # fewer Level 2 matches than LR. Enable by setting environment variable
    # `K2_DIAG_MATCHING_CSV` to a writable CSV path before running the
    # pipeline. No-op when the env var is unset. Remove this block AND
    # all other K2_DIAG-tagged blocks above to revert.
    # ====================================================================
    _DIAG_FIELDNAMES = [
        'feat_id', 'feat_ri', 'feat_peak_count',
        'lib_index', 'lib_name', 'lib_ri', 'lib_formula',
        'lib_peak_count', 'is_hr',
        'delta_ri', 'ri_pct_error', 'passed_ri',
        'dot', 'rev_dot', 'passed_dot_thresholds',
        'rhrmf_score', 'final_pass',
        'gate_failed',
        # K2_DIAG_VARIANT: side-by-side scoring for RHRMF Options 1/2/3.
        # rhrmf_opt0 = explicit Option 0 score (same algorithm as the
        # production rhrmf_score column, but computed for HR candidates
        # too — production uses the 100.0 sentinel for HR while we
        # always run the real algorithm here for comparison).
        # rhrmf_opt1 = 10 ppm tolerance, no isotopologues, count-based.
        # rhrmf_opt2 = 10 ppm + isotopologues for C/Cl/Br/S/Si, count-based.
        # rhrmf_opt3 = 10 ppm + isotopologues + TIC-weighted (Kwiecien).
        'rhrmf_opt0', 'rhrmf_opt1', 'rhrmf_opt2', 'rhrmf_opt3',
    ]

    def _diag_capture(self, feat, lib_comp, **fields):
        """Append one candidate-evaluation record to the in-memory trace.
        No-op when the K2_DIAG_MATCHING_CSV env var is unset.

        `feat` and `lib_comp` provide the always-present context columns;
        `**fields` carries the gate-dependent columns (dot scores etc.)
        with empties for gates that weren't reached on this candidate.
        """
        if self._diag_path is None:
            return
        row = {
            'feat_id': feat.id,
            'feat_ri': feat.ri,
            'feat_peak_count': len(feat.spectrum),
            'lib_index': getattr(lib_comp, 'library_index', None),
            'lib_name': lib_comp.name,
            'lib_ri': lib_comp.ri,
            'lib_formula': lib_comp.formula,
            'lib_peak_count': len(lib_comp.spectrum),
        }
        row.update(fields)
        self._diag_rows.append(row)

    def _diag_flush_csv(self):
        """Write the captured candidate trace to K2_DIAG_MATCHING_CSV.
        No-op when the env var is unset or when nothing was captured."""
        if self._diag_path is None:
            return
        if not self._diag_rows:
            print(f"[K2_DIAG] No candidates captured "
                  f"(no features survived BFF + RI window?)")
            return
        try:
            with open(self._diag_path, 'w', newline='',
                      encoding='utf-8') as f:
                writer = csv.DictWriter(
                    f, fieldnames=self._DIAG_FIELDNAMES,
                    extrasaction='ignore')
                writer.writeheader()
                writer.writerows(self._diag_rows)
            print(f"[K2_DIAG] Wrote {len(self._diag_rows)} candidate "
                  f"row(s) to {self._diag_path}")
        except OSError as e:
            print(f"[K2_DIAG] Failed to write diagnostic CSV at "
                  f"{self._diag_path}: {e}")
    # ====================================================================
    # K2_DIAG: end of diagnostic block
    # ====================================================================