import re
import warnings
from molmass import Formula, ELEMENTS

from src.spectral_math import ELECTRON_MASS, nominal_mass

# ---------------------------------------------------------------------------
# Monoisotopic atom masses (v3.1.0).
#
# Before v3.1.0 this was a hand-typed table rounded to 5 decimals (H = 1.00783
# instead of 1.0078250) with no entries for isotopically labelled atoms, so
# deuterated / 13C-labelled formulas silently lost those atoms (review finding
# S-RHRMF-2) and hydrogen-rich fragments carried a ~0.8 ppm bias (S-DOC-1).
# Masses now come from molmass' isotope table.  `atom_mass()` understands the
# symbols molmass itself emits from Formula.composition(): 'C', 'H', '2H',
# '13C', ... plus the common aliases 'D', 'T', '[2H]', '[13C]'.
# ---------------------------------------------------------------------------
_ALIASES = {'D': '2H', 'T': '3H'}
_ATOM_MASS_CACHE = {}
_WARNED_ATOMS = set()


def atom_mass(symbol):
    """Monoisotopic mass of an atom symbol as molmass writes it, or None if
    the symbol is not a known element/isotope.  Most-abundant isotope for a
    bare element ('Cl' -> 35Cl); explicit isotope for '37Cl', '2H', '13C'."""
    if symbol in _ATOM_MASS_CACHE:
        return _ATOM_MASS_CACHE[symbol]
    sym = _ALIASES.get(symbol, symbol).strip('[]')
    m = re.match(r'^(\d+)?([A-Z][a-z]?)$', sym)
    mass = None
    if m:
        try:
            el = ELEMENTS[m.group(2)]
            a = int(m.group(1)) if m.group(1) else el.nominalmass
            mass = el.isotopes[a].mass
        except (KeyError, AttributeError):
            mass = None
    _ATOM_MASS_CACHE[symbol] = mass
    return mass


# Static view kept for callers/tests that import ATOM_MASSES directly.
ATOM_MASSES = {sym: atom_mass(sym) for sym in
               ['C', 'H', 'N', 'O', 'P', 'S', 'F', 'Cl', 'Br', 'I', 'Si', 'B',
                'Na', 'K', 'Se', 'Sn', 'As', 'Hg', 'Ge', 'Al', 'Ti',
                '2H', '13C', '15N', '18O', '34S', '37Cl', '81Br', 'D']}

def is_library_high_res(spectrum):
    """
    Classify a library spectrum as truly high-resolution.

    v3.0.21 rule: require at least 2 "real-HR" peaks (fractional m/z > 0.05,
    excluding half-integer z=2 artifacts and 1-decimal-rounded m/z values)
    AND require at least one such peak to be among the top 3 most intense
    peaks. This forces HR classification to depend on the high-information
    peaks of the spectrum, not on stray artifacts further down the
    intensity ranking.

    A "real-HR" peak is one where:
      - frac(mz) > 0.05            (not integer)
      - frac(mz) NOT in [0.40, 0.60] (excludes 76.5, 160.5 z=2 artifacts)
      - mz != round(mz, 1)         (excludes 93.1, 174.8 1-dp rounded m/z)

    Background (May 2026 library audit on 97k-entry unified library):
      Pre-v3.0.21 rule ("any peak with frac > 0.05") flagged 989 entries
      as HR. Of those:
        213 contained ONLY half-integer artifacts (Biphenyl, Naphthalene
              etc. — bulk-LR with one or two z=2 doubly-charged peaks)
        69  were 1-decimal-rounded (Sabinene "93.1, 91.1, ..." — clearly
              not exact mass)
        707 had at least one real-HR peak; 323 had real-HR in top-3 by
              intensity.
      The current 38 HR auto-passes in production v3.0.20 are ALL against
      the 213 half-integer subset (37) plus 1 1-decimal-rounded entry
      (Sabinene); zero against the 707 truly-HR entries. Tightening the
      rule eliminates the misclassification source.

    Returns True if the entry is genuinely HR for the purposes of
    accurate-mass matching; False otherwise.
    """
    if not spectrum:
        return False
    # Sort by intensity descending so we can check "real-HR in top-3".
    try:
        sorted_by_intensity = sorted(
            spectrum, key=lambda p: -float(p[1]))
    except (TypeError, ValueError, IndexError):
        return False

    n_real_hr = 0
    top3_has_real_hr = False
    for i, peak in enumerate(sorted_by_intensity):
        try:
            mz = float(peak[0])
        except (TypeError, ValueError, IndexError):
            continue
        frac = abs(mz - round(mz))
        if frac <= 0.05:
            continue  # near-integer — treat as LR
        if 0.40 <= frac <= 0.60:
            continue  # half-integer (z=2 doubly-charged ion artifact)
        if abs(mz - round(mz, 1)) < 1e-6:
            continue  # m/z stored at 1-decimal precision (rounded LR)
        # Survived all the artifact filters — this is a real-HR peak.
        n_real_hr += 1
        if i < 3:
            top3_has_real_hr = True

    return n_real_hr >= 2 and top3_has_real_hr

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
                if atom_mass(symbol) is None and symbol not in _WARNED_ATOMS:
                    _WARNED_ATOMS.add(symbol)
                    warnings.warn(
                        f"RHRMF: atom '{symbol}' in formula {formula_str!r} has no "
                        f"known monoisotopic mass and will be ignored when "
                        f"explaining fragments", RuntimeWarning)

            self.cache[formula_str] = clean_comp
            return clean_comp
        except Exception:
            return {}

    def explain_peak(self, target_mass, parent_counts, tolerance=0.01):
        """
        Determines whether the measured ion m/z `target_mass` can be formed by
        a sub-combination of the atoms in `parent_counts` (within `tolerance`
        Da).

        v3.1.0 (review finding S-RHRMF-1): EI fragment ions are radical
        cations, so the measured m/z is one electron mass (0.000549 Da)
        *below* the neutral sub-formula mass.  Kwiecien 2015 (SI, "Theoretical
        Fragment/Peak Matching") subtracts the electron mass from every
        theoretical fragment before matching; we do the equivalent by adding
        it to the measured m/z once.  Without this the +-10 ppm window was
        centred 6 ppm (m/z 91) to 14 ppm (m/z 39) off, which rejected
        perfectly measured light fragments and made the effective tolerance
        asymmetric.
        """
        target_mass = float(target_mass) + ELECTRON_MASS
        elements = tuple(sorted([e for e in parent_counts.keys()
                                 if atom_mass(e) is not None]))
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
            mass_el = atom_mass(el)
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

    lib_bins = set(nominal_mass(mz) for mz, _ in lib_compound.spectrum)

    matched_peaks = 0
    explained_peaks = 0

    for mz_exp, int_exp in feat_spectrum:
        mz_unit = nominal_mass(mz_exp)

        if mz_unit in lib_bins:
            matched_peaks += 1
            # We use a tolerance of 0.015 Da for High Res matching
            if explainer.explain_peak(mz_exp, parent_counts, tolerance=0.015):
                explained_peaks += 1

    if matched_peaks == 0:
        return 0.0

    score = (explained_peaks / matched_peaks) * 100
    return score


# ========================================================================
# v3.0.20: Kwiecien 2015 HRF / Koelmel 2022 RHRMF implementation.
#
# calculate_rhrmf_variant(...) below is the parametric RHRMF used by
# the production matching engine. With its default-ish "Option 3"
# call site parameters (tolerance_ppm=10, include_isotopologues=True,
# score_mode='tic') it follows Kwiecien (Anal. Chem. 87, 8328) closely:
#   * 10 ppm mass tolerance per peak (was 0.015 Da fixed in v3.0.19)
#   * on-the-fly heavy-isotope variant matching for C/Cl/Br/S/Si
#   * TIC-weighted scoring: sum(mz * intensity)_annotated /
#                            sum(mz * intensity)_observed
#
# The original calculate_rhrmf() function above (fixed-Da tolerance,
# no isotopologues, count-based score) is kept for the diagnostic
# rhrmf_opt0 column — when K2_DIAG_MATCHING_CSV is set, the matching
# engine still computes that legacy variant side-by-side so the user
# can audit the v3.0.20 transition against historical baselines. It
# is otherwise unused.
#
# The parametric form admits four named option settings used during
# the May 2026 review; they remain available for diagnostic re-runs:
#   Option 0 = legacy (use calculate_rhrmf, not this function)
#   Option 1 = tolerance_ppm=10, include_isotopologues=False, count
#   Option 2 = tolerance_ppm=10, include_isotopologues=True,  count
#   Option 3 = tolerance_ppm=10, include_isotopologues=True,  tic
#              ← production call-site configuration
#
# Reverse direction is preserved across all configurations: peaks
# whose integer m/z is not in the library spectrum are skipped.
# ========================================================================

# Heavy-isotope mass deltas (heavy_mass - light_mass), AME 2020 values.
# Used to test whether a peak that fails monoisotopic matching could be
# explained as a +k heavy-isotope variant. We restrict to atoms whose
# heavy isotope has significant natural abundance and whose presence in
# the parent formula is plausible: C (13C, ubiquitous), Cl (37Cl,
# halogens), Br (81Br, halogens), S (34S, sulfurs), Si (30Si, silicons).
HEAVY_ISOTOPE_DELTAS = {
    'C':  1.00336,   # 13C - 12C
    'Cl': 1.99705,   # 37Cl - 35Cl
    'Br': 1.99795,   # 81Br - 79Br
    'S':  1.99580,   # 34S - 32S
    'Si': 1.99684,   # 30Si - 28Si
}


def _peak_explained_variant(mz_exp, parent_counts, explainer,
                            tolerance_ppm, include_isotopologues):
    """K2_DIAG_VARIANT: per-peak explainability check used by Options 1/2/3.

    Computes per-peak Da tolerance from `tolerance_ppm`, then asks the
    existing FormulaExplainer.explain_peak whether the mass is reachable
    by some sub-combination of `parent_counts`. If that fails AND
    `include_isotopologues` is True, retry with residual = mz_exp -
    k * Δ_heavy for k ∈ [1, parent_count[element]] over each element in
    HEAVY_ISOTOPE_DELTAS. (This approximates Kwiecien's on-the-fly
    isotopologue handling: we don't enforce that the matched subformula
    actually contains the heavy atom, so a few false positives are
    possible when the residual mass happens to monoisotopically match a
    subformula that doesn't include that element. With tight ppm
    tolerance these collisions are rare in practice.)
    """
    abs_tol = max(mz_exp * tolerance_ppm / 1e6, 1e-6)
    if explainer.explain_peak(mz_exp, parent_counts, tolerance=abs_tol):
        return True

    if not include_isotopologues:
        return False

    for element, delta in HEAVY_ISOTOPE_DELTAS.items():
        max_k = parent_counts.get(element, 0)
        if max_k <= 0:
            continue
        for k in range(1, int(max_k) + 1):
            residual = mz_exp - k * delta
            if residual <= 0:
                break
            abs_tol_resid = max(residual * tolerance_ppm / 1e6, 1e-6)
            if explainer.explain_peak(residual, parent_counts,
                                       tolerance=abs_tol_resid):
                return True
    return False


def calculate_rhrmf_variant(feat_spectrum, lib_compound, explainer=None,
                            tolerance_ppm=10,
                            include_isotopologues=False,
                            score_mode='count'):
    """K2_DIAG_VARIANT: parametric RHRMF for Options 1/2/3 comparison.

    Parameters mirror the May 2026 review's option list:
      - tolerance_ppm: per-peak mass tolerance in parts per million.
        Kwiecien specifies 10 ppm. K2 production uses 0.015 Da fixed,
        which is 30–200 ppm at typical GC-MS m/z.
      - include_isotopologues: when True, retry failed monoisotopic
        matches with k heavy-isotope substitutions (13C / 37Cl / 81Br /
        34S / 30Si). Kwiecien's algorithm does this on-the-fly.
      - score_mode: 'count' (explained_peaks / matched_peaks) matches
        Koelmel's prose description; 'tic' (∑(mz*int)_annotated /
        ∑(mz*int)_observed) matches Kwiecien's published formula
        exactly. Both expressed as 0-100.

    Reverse direction is preserved: peaks whose integer m/z is not in
    the library spectrum are skipped entirely (same as
    calculate_rhrmf).

    Returns float in [0.0, 100.0]. Returns 0.0 if no library formula,
    no parseable parent, or no peaks in the reverse-filtered set.
    """
    if not lib_compound.formula:
        return 0.0
    if explainer is None:
        explainer = FormulaExplainer()
    parent_counts = explainer.parse_formula(lib_compound.formula)
    if not parent_counts:
        return 0.0

    lib_bins = set(nominal_mass(mz) for mz, _ in lib_compound.spectrum)

    if score_mode == 'count':
        matched = 0
        explained = 0
        for mz_exp, _int_exp in feat_spectrum:
            mz_unit = nominal_mass(mz_exp)
            if mz_unit not in lib_bins:
                continue
            matched += 1
            if _peak_explained_variant(mz_exp, parent_counts, explainer,
                                       tolerance_ppm,
                                       include_isotopologues):
                explained += 1
        if matched == 0:
            return 0.0
        return (explained / matched) * 100.0

    elif score_mode == 'tic':
        observed_tic = 0.0
        annotated_tic = 0.0
        for mz_exp, int_exp in feat_spectrum:
            mz_unit = nominal_mass(mz_exp)
            if mz_unit not in lib_bins:
                continue
            try:
                weight = float(mz_exp) * float(int_exp)
            except (TypeError, ValueError):
                continue
            if weight <= 0:
                continue
            observed_tic += weight
            if _peak_explained_variant(mz_exp, parent_counts, explainer,
                                       tolerance_ppm,
                                       include_isotopologues):
                annotated_tic += weight
        if observed_tic == 0:
            return 0.0
        return (annotated_tic / observed_tic) * 100.0

    else:
        raise ValueError(
            f"calculate_rhrmf_variant: unknown score_mode {score_mode!r} "
            f"(expected 'count' or 'tic')")
# ========================================================================
# end of v3.0.20 RHRMF implementation
# ========================================================================