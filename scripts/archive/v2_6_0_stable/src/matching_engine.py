from src.universal_parser import UniversalParser
from src.library_parser import LibraryParser
from src.spectral_math import calculate_scores
from src.rhrmf import calculate_rhrmf, is_library_high_res, FormulaExplainer
from src.is_normalizer import InternalStandardNormalizer
import bisect
import time

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
                 sample_types=None, is_config=None):
        self.data_dir = data_dir
        self.quant_file = quant_file  # Changed from area_file to quant_file (more generic)
        self.msp_file = msp_file
        self.library_file = library_file
        self.ri_cal_file = ri_cal_file
        self.blank_identifier = blank_identifier
        self.sample_types = sample_types  # Optional: {sample_name: 'sample' or 'blank'}

        # Internal Standard Configuration (v2.6.0)
        self.is_config = is_config or {}  # Dict with IS normalization parameters

        self.parser = None  # Changed from msdial_parser to parser (universal)
        self.library_parser = None

        # Initialize the Formula Explainer once (it builds a cache)
        self.explainer = FormulaExplainer()

        self.results = {}

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
                target_ri = self.is_config.get('target_ri', 0)
                ri_tol = self.is_config.get('ri_tolerance', 50)
                success, feat_id = normalizer.normalize_auto_mz_ri(target_mz, mz_tol, target_ri, ri_tol)
                if not success:
                    print("[WARNING] Auto m/z+RI IS normalization failed")

            elif method == 'msp':
                msp_file = self.is_config.get('msp_file', '')
                ri_tol = self.is_config.get('ri_tolerance', 50)
                success, feat_id = normalizer.normalize_auto_msp(msp_file, ri_tol)
                if not success:
                    print("[WARNING] Auto MSP IS normalization failed")

            # Export normalization report if requested
            if self.is_config.get('export_report', False):
                output_path = self.is_config.get('report_path', 'is_normalization_report.csv')
                normalizer.export_factors_csv(output_path)

        # 5. Run BFF (Pre-requisite for matching) - Uses normalized abundances if IS was applied
        print("\nRunning BFF Filter...")
        for f in features:
            f.calculate_bff(self.parser.blank_columns, self.parser.sample_columns)

        # 6. Load Library
        print("Loading Library...")
        self.library_parser = LibraryParser(self.library_file)
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
                    continue
                    
                # 4. Spectral Matching (Unit Res)
                # Only run expensive math if RI passes
                dot, rev_dot = calculate_scores(feat.spectrum, lib_comp.spectrum)
                
                # 5. Thresholds (Level 2 Criteria)
                # Rev Dot > 600 AND Dot > 500
                if rev_dot > 600 and dot > 500:
                    cand = MatchCandidate(lib_comp, (dot, rev_dot), delta_ri)
                    
                    # --- Phase 4 Logic ---
                    # Check High Res status
                    is_hr = is_library_high_res(lib_comp.spectrum)
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
            
            # Store if we found valid candidates
            if candidates:
                # Sort by Reverse Dot Product (descending)
                candidates.sort(key=lambda x: x.reverse_dot_product, reverse=True)
                self.results[feat.id] = candidates
                matches_found += 1

        print(f"\nMatching Complete.")
        print(f"Features with Level 2 Matches (Post-RHRMF): {matches_found}")

    def get_results(self):
        return self.results