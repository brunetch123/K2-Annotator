"""
Surrogate Standard Recovery Analyzer
v3.0.0 - Matches surrogate standards and calculates recoveries

This module provides functionality for:
- Loading and matching surrogate standard libraries
- Calculating % recovery relative to reference samples
- Generating abundance and recovery tables
"""

import statistics
import bisect
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from src.library_parser import LibraryParser, LibraryCompound
from src.spectral_math import calculate_scores
# v3.0.21: HR-aware dot product for surrogate matching against HR libraries.
from src.spectral_math import (calculate_scores_hr_aware,
                               HR_DOT_TOLERANCE_PPM_DEFAULT)
from src.rhrmf import (calculate_rhrmf, is_library_high_res,
                       FormulaExplainer)
# v3.0.20: surrogate analysis uses the same RHRMF variant as suspect
# screening (10 ppm + isotopologues + TIC-weighted). calculate_rhrmf
# stays imported for legacy back-compat; not currently called here.
from src.rhrmf import calculate_rhrmf_variant


@dataclass
class SurrogateMatch:
    """
    Represents a matched surrogate standard.
    """
    compound_name: str
    feature_id: int
    library_ri: float
    experimental_ri: float
    ri_error: float
    ri_error_percent: float
    forward_dot: int
    reverse_dot: int
    rhrmf_score: Optional[float]      # None for HR library entries (v3.1.0)
    is_high_res: bool
    library_compound: LibraryCompound = field(repr=False)
    hr_dot: Optional[int] = None       # HR-aware dot products (HR entries only)
    hr_rev_dot: Optional[int] = None


class SurrogateAnalyzer:
    """
    Matches surrogate standards and calculates recoveries.
    
    Uses same spectral matching criteria as suspect screening but:
    - Skips BFF filtering (we don't care about blank levels for surrogates)
    - Selects best match (highest reverse dot) if multiple features match
    - Calculates recovery relative to reference samples
    """
    
    # Matching thresholds (same as Level 2 suspect screening)
    RI_WINDOW = 50  # ±50 RI units
    RI_ERROR_PERCENT_MAX = 1.5  # Maximum 1.5% RI error
    REVERSE_DOT_MIN = 600  # Minimum reverse dot product
    FORWARD_DOT_MIN = 500  # Minimum forward dot product
    RHRMF_MIN = 75  # Minimum RHRMF score for low-res libraries
    
    def __init__(self, features: List, surrogate_config: Dict, 
                 sample_columns: List[str], blank_columns: List[str],
                 is_config: Optional[Dict] = None):
        """
        Initialize the surrogate analyzer.
        
        Args:
            features: List of Feature objects from UniversalParser
            surrogate_config: Configuration dict with:
                - enabled: bool
                - library_path: str
                - selected_compounds: list of compound names to include (None = all)
                - groups: dict mapping group names to {'samples': [], 'references': []}
                - spike_ratios: dict mapping sample names to ratios
                - spiked_samples: list of all spiked sample names
                - reference_samples: list of reference sample names
            sample_columns: List of sample column names
            blank_columns: List of blank column names
            is_config: Internal standard normalization config (optional)
        """
        self.features = features
        self.feature_map = {f.id: f for f in features}
        self.config = surrogate_config
        self.sample_columns = sample_columns
        self.blank_columns = blank_columns
        self.is_config = is_config or {}
        
        # Results storage
        self.matches: Dict[str, Optional[SurrogateMatch]] = {}  # compound_name -> match
        self.abundances: Dict[str, Dict[str, float]] = {}  # compound_name -> {sample: abundance}
        self.recoveries: Dict[str, Dict[str, Any]] = {}  # compound_name -> {sample: recovery%}
        
        # Library
        self.library_compounds: List[LibraryCompound] = []
        self.explainer = FormulaExplainer()
        
    def load_surrogate_library(self) -> bool:
        """
        Load the surrogate standard library.
        
        Returns:
            True if library loaded successfully, False otherwise
        """
        library_path = self.config.get('library_path', '')
        if not library_path:
            print("[WARNING] No surrogate library path specified")
            return False
        
        try:
            parser = LibraryParser(library_path)
            parser.load_library()
            all_compounds = parser.get_compounds()
            
            # Filter to selected compounds if specified
            selected = self.config.get('selected_compounds')
            if selected:
                selected_lower = [s.lower() for s in selected]
                self.library_compounds = [
                    c for c in all_compounds 
                    if c.name.lower() in selected_lower
                ]
            else:
                self.library_compounds = all_compounds
            
            print(f"[Surrogate] Loaded {len(self.library_compounds)} surrogate compounds")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to load surrogate library: {e}")
            return False
    
    def match_surrogates(self) -> Dict[str, Optional[SurrogateMatch]]:
        """
        Match each surrogate compound to features.
        
        Unlike suspect screening:
        - We don't apply BFF filter
        - We select the single best match per compound
        
        Returns:
            Dictionary mapping compound names to their best match (or None)
        """
        if not self.library_compounds:
            print("[WARNING] No surrogate compounds loaded")
            return {}
        
        print(f"\n--- Matching Surrogate Standards ---")
        print(f"Compounds to match: {len(self.library_compounds)}")
        print(f"Features available: {len(self.features)}")
        
        # Pre-calculate feature RI list for binary searching
        sorted_features = sorted(self.features, key=lambda f: f.ri)
        feature_ris = [f.ri for f in sorted_features]
        
        matched_count = 0
        
        for compound in self.library_compounds:
            match = self._match_single_compound(compound, sorted_features, feature_ris)
            self.matches[compound.name] = match
            
            if match:
                matched_count += 1
                print(f"  [OK] {compound.name}: Feature {match.feature_id} "
                      f"(RevDot={match.reverse_dot}, RI Err={match.ri_error:.1f})")
            else:
                print(f"  [--] {compound.name}: No matching feature found")
        
        print(f"\nSurrogate Matching Complete: {matched_count}/{len(self.library_compounds)} matched")
        return self.matches
    
    def _match_single_compound(self, compound: LibraryCompound, 
                                sorted_features: List, 
                                feature_ris: List[float]) -> Optional[SurrogateMatch]:
        """
        Find best matching feature for a single surrogate compound.
        
        Criteria (same as Level 2 but without BFF):
        - RI window ±50
        - RI error ≤1.5%
        - Reverse Dot > 600
        - Forward Dot > 500
        - RHRMF > 75 (for low-res libraries)
        
        Returns:
            SurrogateMatch for best candidate, or None if no match
        """
        # RI Window search
        ri_min = compound.ri - self.RI_WINDOW
        ri_max = compound.ri + self.RI_WINDOW
        
        start_idx = bisect.bisect_left(feature_ris, ri_min)
        end_idx = bisect.bisect_right(feature_ris, ri_max)
        
        candidates = []
        
        for i in range(start_idx, end_idx):
            feat = sorted_features[i]
            
            # NOTE: We skip BFF check for surrogate matching
            # (We want to find the surrogate regardless of blank levels)
            
            # RI percent error check
            delta_ri = abs(feat.ri - compound.ri)
            # v3.1.0 (S-SUR-2): relative to the FEATURE RI, as in the suspect-
            # screening engine and the NYCSS SI ("+-1.5 % from the query feature").
            percent_error = (delta_ri / feat.ri) * 100 if feat.ri > 0 else 100
            
            if percent_error > self.RI_ERROR_PERCENT_MAX:
                continue
            
            # Spectral matching
            dot, rev_dot = calculate_scores(feat.spectrum, compound.spectrum)
            
            if rev_dot <= self.REVERSE_DOT_MIN or dot <= self.FORWARD_DOT_MIN:
                continue
            
            # RHRMF check
            is_hr = is_library_high_res(compound.spectrum, compound.metadata)
            
            if is_hr:
                # v3.0.21: HR library — re-score with HR-aware dot
                # product at 10 ppm and gate on the same >600/>500
                # thresholds. RHRMF is skipped (the HR-aware dot is
                # the exact-mass discrimination). Match suspect-
                # screening logic in MatchingEngine.run_matching().
                hr_dot, hr_rev_dot = calculate_scores_hr_aware(
                    feat.spectrum, compound.spectrum,
                    tolerance_ppm=HR_DOT_TOLERANCE_PPM_DEFAULT)
                rhrmf_score = None   # RHRMF not run for HR entries (v3.1.0)
                passed_rhrmf = (hr_rev_dot > self.REVERSE_DOT_MIN
                                 and hr_dot > self.FORWARD_DOT_MIN)
            else:
                hr_dot = hr_rev_dot = None
                # v3.0.20: same Kwiecien-style RHRMF as suspect screening
                # — 10 ppm tolerance, isotopologues, TIC-weighted scoring.
                rhrmf_score = calculate_rhrmf_variant(
                    feat.spectrum, compound, self.explainer,
                    tolerance_ppm=10,
                    include_isotopologues=True,
                    score_mode='tic')
                passed_rhrmf = rhrmf_score > self.RHRMF_MIN
            
            if not passed_rhrmf:
                continue
            
            # This feature passes all criteria
            match = SurrogateMatch(
                compound_name=compound.name,
                feature_id=feat.id,
                library_ri=compound.ri,
                experimental_ri=feat.ri,
                ri_error=delta_ri,
                ri_error_percent=percent_error,
                forward_dot=dot,
                reverse_dot=rev_dot,
                rhrmf_score=rhrmf_score,
                is_high_res=is_hr,
                library_compound=compound,
                hr_dot=hr_dot,
                hr_rev_dot=hr_rev_dot,
            )
            candidates.append(match)
        
        if not candidates:
            return None
        
        # Select best candidate (highest reverse dot product)
        best = max(candidates, key=lambda m: m.reverse_dot)
        return best
    
    def extract_abundances(self) -> Dict[str, Dict[str, float]]:
        """
        Extract normalized abundances for matched surrogates.
        
        For each matched surrogate, extracts the abundance in each
        spiked sample and reference, applying IS normalization if enabled.
        
        Returns:
            Dictionary: {compound_name: {sample_name: normalized_abundance}}
        """
        spiked_samples = self.config.get('spiked_samples', [])
        reference_samples = self.config.get('reference_samples', [])
        all_relevant = set(spiked_samples) | set(reference_samples)
        
        for compound_name, match in self.matches.items():
            if match is None:
                self.abundances[compound_name] = {s: None for s in all_relevant}
                continue
            
            feature = self.feature_map.get(match.feature_id)
            if not feature:
                self.abundances[compound_name] = {s: None for s in all_relevant}
                continue
            
            compound_abundances = {}
            for sample in all_relevant:
                abundance = self._get_normalized_abundance(feature, sample)
                compound_abundances[sample] = abundance
            
            self.abundances[compound_name] = compound_abundances
        
        return self.abundances
    
    def _get_normalized_abundance(self, feature, sample_name: str) -> Optional[float]:
        """
        Get the abundance for a feature in a sample, applying IS normalization if enabled.
        
        Args:
            feature: Feature object
            sample_name: Name of the sample
            
        Returns:
            Normalized abundance or None if not available
        """
        abundance = feature.abundances.get(sample_name)
        if abundance is None or abundance == 0:
            return None
        # v3.1.0 (S-SUR-1): Feature.abundances are ALREADY IS-normalised in
        # place by InternalStandardNormalizer when IS normalisation is on.
        # Before v3.1.0 the factor was applied a second time here, so
        # recoveries scaled with factor**2 (a true 100 % recovery in a sample
        # with factor 2 was reported as 200 %).
        return abundance

    def calculate_recoveries(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate % recovery for each surrogate in each spiked sample.
        
        Recovery formula:
        % Recovery = (sample_abundance / sample_ratio) / 
                     avg(reference_abundances / reference_ratios) * 100
        
        Returns:
            Dictionary: {compound_name: {sample_name: recovery_percent or "No Match"}}
        """
        if not self.abundances:
            self.extract_abundances()
        
        groups = self.config.get('groups', {'Default': {
            'samples': self.config.get('spiked_samples', []),
            'references': self.config.get('reference_samples', [])
        }})
        spike_ratios = self.config.get('spike_ratios', {})
        reference_samples = set(self.config.get('reference_samples', []))
        
        for compound_name, match in self.matches.items():
            self.recoveries[compound_name] = {}
            
            if match is None:
                # No match - mark all samples as "No Match"
                for group_name, group_data in groups.items():
                    for sample in group_data.get('samples', []):
                        if sample not in reference_samples:
                            self.recoveries[compound_name][sample] = "No Match"
                continue
            
            abundances = self.abundances.get(compound_name, {})
            
            # Calculate recovery for each group
            for group_name, group_data in groups.items():
                group_samples = group_data.get('samples', [])
                group_references = group_data.get('references', [])
                
                # Calculate average reference abundance (ratio-adjusted)
                ref_abundances_adjusted = []
                for ref in group_references:
                    ref_abundance = abundances.get(ref)
                    if ref_abundance is not None and ref_abundance > 0:
                        ref_ratio = spike_ratios.get(ref, 1.0)
                        ref_abundances_adjusted.append(ref_abundance / ref_ratio)
                
                if not ref_abundances_adjusted:
                    # No valid reference abundances
                    for sample in group_samples:
                        if sample not in reference_samples:
                            self.recoveries[compound_name][sample] = "No Ref"
                    continue
                
                avg_ref = statistics.mean(ref_abundances_adjusted)
                
                # Calculate recovery for each sample in this group
                for sample in group_samples:
                    if sample in reference_samples:
                        continue  # Skip references
                    
                    sample_abundance = abundances.get(sample)
                    if sample_abundance is None or sample_abundance == 0:
                        self.recoveries[compound_name][sample] = "No Data"
                        continue
                    
                    sample_ratio = spike_ratios.get(sample, 1.0)
                    recovery = (sample_abundance / sample_ratio) / avg_ref * 100
                    self.recoveries[compound_name][sample] = round(recovery, 1)
        
        return self.recoveries
    
    def get_abundance_table(self) -> Dict[str, Any]:
        """
        Generate the abundance table data.
        
        Returns:
            Dictionary with:
            - 'headers': List of column headers [Compound, Group, Sample1, Sample2, ...]
            - 'rows': List of rows, each a dict {compound, abundances...}
        """
        if not self.abundances:
            self.extract_abundances()
        
        groups = self.config.get('groups', {})
        spiked_samples = self.config.get('spiked_samples', [])
        reference_samples = self.config.get('reference_samples', [])
        
        # Build sample-to-group mapping
        sample_to_group = {}
        for group_name, group_data in groups.items():
            for sample in group_data.get('samples', []) + group_data.get('references', []):
                sample_to_group[sample] = group_name
        
        # Order: references first, then samples
        ordered_samples = reference_samples + [s for s in spiked_samples if s not in reference_samples]
        
        headers = ['Compound'] + ordered_samples
        group_row = ['Group'] + [sample_to_group.get(s, 'Default') for s in ordered_samples]
        
        rows = []
        for compound_name in sorted(self.abundances.keys()):
            row = {'Compound': compound_name}
            abundances = self.abundances[compound_name]
            
            for sample in ordered_samples:
                val = abundances.get(sample)
                if val is None:
                    row[sample] = "No Match" if self.matches.get(compound_name) is None else "N/A"
                else:
                    row[sample] = round(val, 1)
            
            rows.append(row)
        
        return {
            'headers': headers,
            'group_row': group_row,
            'rows': rows
        }
    
    def get_recovery_table(self) -> Dict[str, Any]:
        """
        Generate the recovery table data.
        
        Returns:
            Dictionary with:
            - 'headers': [Compound, Average, StdDev, Sample1, Sample2, ...]
            - 'rows': List of rows with recovery data
        """
        if not self.recoveries:
            self.calculate_recoveries()
        
        reference_samples = set(self.config.get('reference_samples', []))
        spiked_samples = [s for s in self.config.get('spiked_samples', []) 
                         if s not in reference_samples]
        
        headers = ['Compound', 'Average', 'StdDev'] + spiked_samples
        
        rows = []
        for compound_name in sorted(self.recoveries.keys()):
            compound_recoveries = self.recoveries[compound_name]
            
            row = {'Compound': compound_name}
            
            # Collect numeric recoveries for stats
            numeric_recoveries = []
            for sample in spiked_samples:
                val = compound_recoveries.get(sample)
                row[sample] = val
                if isinstance(val, (int, float)):
                    numeric_recoveries.append(val)
            
            # Calculate average and std dev
            if numeric_recoveries:
                row['Average'] = round(statistics.mean(numeric_recoveries), 1)
                row['StdDev'] = round(statistics.stdev(numeric_recoveries), 1) if len(numeric_recoveries) > 1 else 0.0
            else:
                row['Average'] = "N/A"
                row['StdDev'] = "N/A"
            
            rows.append(row)
        
        return {
            'headers': headers,
            'rows': rows
        }
    
    def get_match_info_table(self) -> Dict[str, Any]:
        """
        Generate the match information table data.
        
        Returns:
            Dictionary with:
            - 'headers': [Compound, Feature_ID, RI_Library, RI_Exp, RI_Error, ...]
            - 'rows': List of rows with match details
        """
        headers = [
            'Compound', 'Feature_ID', 'RI_Library', 'RI_Experimental', 
            'RI_Error', 'RI_Error%', 'RevDot', 'FwdDot', 'HighRes', 'RHRMF',
            'HR_RevDot', 'HR_FwdDot'
        ]
        
        rows = []
        for compound_name in sorted(self.matches.keys()):
            match = self.matches[compound_name]
            
            if match is None:
                row = {
                    'Compound': compound_name,
                    'Feature_ID': 'No Match',
                    'RI_Library': '-',
                    'RI_Experimental': '-',
                    'RI_Error': '-',
                    'RI_Error%': '-',
                    'RevDot': '-',
                    'FwdDot': '-',
                    'HighRes': '-',
                    'RHRMF': '-',
                    'HR_RevDot': '-',
                    'HR_FwdDot': '-',
                }
            else:
                row = {
                    'Compound': compound_name,
                    'Feature_ID': match.feature_id,
                    'RI_Library': round(match.library_ri, 1),
                    'RI_Experimental': round(match.experimental_ri, 1),
                    'RI_Error': round(match.ri_error, 2),
                    'RI_Error%': round(match.ri_error_percent, 2),
                    'RevDot': match.reverse_dot,
                    'FwdDot': match.forward_dot,
                    'HighRes': 'Yes' if match.is_high_res else 'No',
                    'RHRMF': 'N/A' if match.rhrmf_score is None else round(match.rhrmf_score, 1),
                    'HR_RevDot': 'N/A' if match.hr_rev_dot is None else match.hr_rev_dot,
                    'HR_FwdDot': 'N/A' if match.hr_dot is None else match.hr_dot,
                }
            
            rows.append(row)
        
        return {
            'headers': headers,
            'rows': rows
        }
    
    def run_full_analysis(self) -> bool:
        """
        Run the complete surrogate analysis workflow.
        
        Returns:
            True if analysis completed successfully
        """
        # 1. Load library
        if not self.load_surrogate_library():
            return False
        
        # 2. Match surrogates
        self.match_surrogates()
        
        # 3. Extract abundances
        self.extract_abundances()
        
        # 4. Calculate recoveries
        self.calculate_recoveries()
        
        return True
