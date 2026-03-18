import re
from molmass import Formula

# Exact masses for common isotopes
ATOM_MASSES = {
    'C': 12.00000, 'H': 1.00783, 'N': 14.00307, 'O': 15.99491, 
    'P': 30.97376, 'S': 31.97207, 'F': 18.99840, 'Cl': 34.96885, 
    'Br': 78.91834, 'I': 126.90447, 'Si': 27.97693
}

def is_library_high_res(spectrum):
    """
    Checks if the library spectrum is High Res.
    Criteria: Check if masses have significant decimal precision.
    """
    if not spectrum:
        return False
    
    # Check first 5 peaks
    decimals = 0
    for mz, _ in spectrum[:5]:
        frac = abs(mz - round(mz))
        if frac > 0.05: # Threshold for "non-integer-like"
            decimals += 1
            
    return decimals >= (len(spectrum[:5]) / 2)

class FormulaExplainer:
    def __init__(self):
        self.cache = {}

    def parse_formula(self, formula_str):
        """
        Parses "C6H12O6" into {'C':6, 'H':12, 'O':6}
        """
        if not formula_str: return {}
        if formula_str in self.cache:
            return self.cache[formula_str]
        
        try:
            f = Formula(formula_str)
            raw_comp = dict(f.composition())
            clean_comp = {}
            
            for symbol, item in raw_comp.items():
                clean_comp[symbol] = item.count
                
            self.cache[formula_str] = clean_comp
            return clean_comp
        except Exception:
            return {}

    def explain_peak(self, target_mass, parent_counts, tolerance=0.01):
        """
        Determines if 'target_mass' can be formed by a sub-combination of 'parent_counts'.
        """
        elements = tuple(sorted([e for e in parent_counts.keys() if e in ATOM_MASSES]))
        if not elements: return False
        
        # Using a local memoization for the recursive solver to avoid redundant calculations per peak
        memo = {}
        
        def _solve(target, idx, current_mass):
            state = (idx, round(current_mass, 4))
            if state in memo:
                return memo[state]
            
            # Base cases
            if abs(target - current_mass) <= tolerance:
                return True
            if current_mass > target + tolerance:
                return False
            if idx >= len(elements):
                return False
                
            el = elements[idx]
            mass_el = ATOM_MASSES[el]
            max_count = parent_counts[el]
            
            # Theoretical max based on remaining mass
            theoretical_max = int((target - current_mass + tolerance) // mass_el)
            limit = min(max_count, theoretical_max)
            
            for n in range(limit, -1, -1):
                if _solve(target, idx + 1, current_mass + (n * mass_el)):
                    memo[state] = True
                    return True
            
            memo[state] = False
            return False

        return _solve(target_mass, 0, 0.0)

def calculate_rhrmf(feat_spectrum, lib_compound, explainer=None):
    """
    Calculates RHRMF Score (0-100).
    """
    if not lib_compound.formula:
        return 0.0 
    
    if explainer is None:
        explainer = FormulaExplainer()
        
    parent_counts = explainer.parse_formula(lib_compound.formula)
    if not parent_counts:
        return 0.0 
        
    lib_bins = set(int(round(mz)) for mz, _ in lib_compound.spectrum)
    
    matched_peaks = 0
    explained_peaks = 0
    
    for mz_exp, int_exp in feat_spectrum:
        mz_unit = int(round(mz_exp))
        
        if mz_unit in lib_bins:
            matched_peaks += 1
            # We use a tolerance of 0.015 Da for High Res matching
            if explainer.explain_peak(mz_exp, parent_counts, tolerance=0.015):
                explained_peaks += 1
                
    if matched_peaks == 0:
        return 0.0
        
    score = (explained_peaks / matched_peaks) * 100
    return score