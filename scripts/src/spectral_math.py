import math

import numpy as np

# Mass of the electron (CODATA 2018), Da.  EI fragment ions are singly
# charged cations, so the measured m/z is this much below the neutral
# fragment mass.  Used by the RHRMF (rhrmf.py) since v3.1.0.
ELECTRON_MASS = 0.000548579909


def nominal_mass(mz):
    """Unit-mass bin for an m/z value: round half UP (76.5 -> 77, 77.5 -> 78).

    v3.1.0 (review finding S-DOT-2): the previous `int(round(mz))` used
    Python's banker's rounding, so 76.5 -> 76 but 77.5 -> 78 — inconsistent
    for the half-integer z=2 artefacts present in some NIST entries.
    """
    return int(math.floor(float(mz) + 0.5))


# v3.0.21: default ppm tolerance for HR-aware peak pairing.
# Matches Kwiecien 2015 (Anal. Chem. 87, 8328) — explicitly determined
# in their SI Fig 6 as the optimum tradeoff between low-S/N fragment
# acceptance and formula discrimination. Same value as v3.0.20's RHRMF
# tolerance, so a peak that's "in" for RHRMF is also "in" for
# HR-aware dot scoring.
HR_DOT_TOLERANCE_PPM_DEFAULT = 10.0


def bin_spectrum(peaks):
    """
    Converts a raw spectrum [(mz, int), ...] to a unit-resolution dictionary.
    Example: 145.4 -> 145. 
    Sum intensities if multiple peaks fall in same bin.
    """
    if not peaks:
        return {}
    binned = {}
    for peak in peaks:
        if not isinstance(peak, (list, tuple)) or len(peak) < 2:
            continue
        try:
            mz = float(peak[0])
            intensity = float(peak[1])
            if mz < 0 or intensity < 0:
                continue
            mass_bin = nominal_mass(mz)
            if mass_bin not in binned:
                binned[mass_bin] = 0.0
            binned[mass_bin] += intensity
        except (ValueError, TypeError):
            continue
    return binned

def calculate_scores(feat_peaks, lib_peaks):
    """
    Calculates Forward Dot Product and Reverse Dot Product.
    
    Logic:
    1. Bin both spectra to unit resolution.
    2. Weights: Mass^1 * Intensity^0.5 (Standard NIST-like weighting)
       OR Simple Cosine: Intensity^1. 
       
    Paper implies "Dot product EI spectra match", which usually refers to 
    standard cosine or Stein-Scott. We will use weighted cosine (Mass * Sqrt(Int)).
    
    Returns: (dot_product, reverse_dot_product)
    Range: 0 - 1000
    """
    # 1. Binning
    feat_dict = bin_spectrum(feat_peaks)
    lib_dict = bin_spectrum(lib_peaks)
    
    # 2. Identify all relevant masses
    all_masses = set(feat_dict.keys()) | set(lib_dict.keys())
    
    # 3. Create Vectors
    # Weighting: w = Intensity^0.5 * Mass^1 (Stein-Scott optimization)
    # This emphasizes higher masses and suppresses noise.
    
    dot_prod_num = 0.0
    feat_norm_sq = 0.0
    lib_norm_sq = 0.0
    
    rev_prod_num = 0.0
    rev_feat_norm_sq = 0.0
    
    for m in all_masses:
        f_int = feat_dict.get(m, 0.0)
        l_int = lib_dict.get(m, 0.0)
        
        # Apply Weights
        # Using Sqrt(Intensity) scaling is standard for MS matching to reduce dynamic range dominance
        w_f = (f_int ** 0.5) * (m ** 1.0)
        w_l = (l_int ** 0.5) * (m ** 1.0)
        
        # Forward Dot Product Components
        dot_prod_num += w_f * w_l
        feat_norm_sq += w_f ** 2
        lib_norm_sq += w_l ** 2
        
        # Reverse Dot Product Components
        # Reverse only considers peaks present in the LIBRARY
        if l_int > 0:
            rev_prod_num += w_f * w_l
            rev_feat_norm_sq += w_f ** 2
            
    # 4. Calculate Final Scores
    # Forward Dot
    if feat_norm_sq * lib_norm_sq > 0:
        dot = 1000 * (dot_prod_num**2) / (feat_norm_sq * lib_norm_sq)
    else:
        dot = 0.0
        
    # Reverse Dot
    # Note: Rev Dot denominator uses the norm of library (fixed) and
    # the norm of feature peaks THAT MATCHED library peaks.
    if rev_feat_norm_sq * lib_norm_sq > 0:
        rev_dot = 1000 * (rev_prod_num**2) / (rev_feat_norm_sq * lib_norm_sq)
    else:
        rev_dot = 0.0

    return int(dot), int(rev_dot)


# ============================================================================
# v3.0.21: HR-aware dot product
# ============================================================================
def calculate_scores_hr_aware(feat_peaks, lib_peaks,
                               tolerance_ppm=HR_DOT_TOLERANCE_PPM_DEFAULT):
    """Forward and reverse dot products using ppm-based peak pairing
    rather than unit-resolution binning.

    Used by the production matching engine for library entries
    classified as truly high-resolution (`is_library_high_res()`).
    The unit-resolution `calculate_scores()` is still used for all
    other library entries.

    Algorithm
    ---------
    1. Filter peaks: drop entries with non-positive intensity or m/z.
    2. Sort feature and library peak lists by m/z ascending.
    3. Greedy ppm pairing: for each library peak (in m/z order), find
       the closest unmatched feature peak whose m/z is within
       `tolerance_ppm` ppm. If multiple feature peaks fit, pick the
       one with the smallest absolute m/z distance. Library peaks
       with no partner remain as "library-only" (contribute to
       lib_norm in both forward and reverse dot).
    4. Unmatched feature peaks contribute to `feat_norm` for the
       forward dot only — they're NOT counted in the reverse dot
       denominator (consistent with `calculate_scores`'s reverse
       semantics: "what fraction of LIBRARY peaks were matched").
    5. NIST-style Stein-Scott weighting: w = sqrt(intensity) * mz.
    6. Score formula identical to `calculate_scores`: squared cosine
       scaled to 0–1000. Same 600/500 thresholds apply.

    Tolerance choice
    ----------------
    Default 10 ppm = Kwiecien 2015 empirical optimum. Lower values
    (5 ppm) are defensible on well-calibrated Q Exactive data;
    higher values (15–20 ppm) drift into noise territory.

    Returns
    -------
    (forward_dot, reverse_dot) — ints in [0, 1000].
    """
    # Filter to (mz, intensity) tuples with positive values.
    def _clean(peaks):
        out = []
        for p in peaks:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                continue
            try:
                mz = float(p[0])
                intensity = float(p[1])
            except (TypeError, ValueError):
                continue
            if mz <= 0 or intensity <= 0:
                continue
            out.append((mz, intensity))
        return out

    feat = _clean(feat_peaks)
    lib = _clean(lib_peaks)
    if not feat or not lib:
        return 0, 0

    # Sort by m/z for the linear-scan pairing.
    feat.sort()
    lib.sort()

    n_feat = len(feat)
    feat_matched = [False] * n_feat

    # Greedy pairing in lib order. For each library peak, find the
    # closest unmatched feat peak within ±ppm. Linear advance because
    # both lists are sorted.
    # pairs[i] = (lib_mz, lib_int, f_int_or_zero)
    pairs = []
    scan_start = 0  # we can advance this as lib peaks increase in m/z
    for lib_mz, lib_int in lib:
        tol_abs = lib_mz * tolerance_ppm / 1e6
        lo = lib_mz - tol_abs
        hi = lib_mz + tol_abs
        # Advance scan_start past any feat peaks now below the window
        # (works because lib peaks are sorted ascending too).
        while scan_start < n_feat and feat[scan_start][0] < lo:
            scan_start += 1
        # Find closest unmatched feat peak within window.
        best_i = -1
        best_dist = tol_abs + 1.0
        i = scan_start
        while i < n_feat and feat[i][0] <= hi:
            if not feat_matched[i]:
                dist = abs(feat[i][0] - lib_mz)
                if dist < best_dist:
                    best_dist = dist
                    best_i = i
            i += 1
        if best_i >= 0:
            feat_matched[best_i] = True
            pairs.append((lib_mz, lib_int, feat[best_i][1]))
        else:
            pairs.append((lib_mz, lib_int, 0.0))

    # NIST-style weighted dot product. Use lib_mz as the m/z for
    # weighting (consistent across the matched pair).
    dot_prod_num = 0.0
    feat_norm_sq = 0.0
    lib_norm_sq = 0.0
    rev_feat_norm_sq = 0.0
    for lib_mz, lib_int, f_int in pairs:
        w_l = (lib_int ** 0.5) * lib_mz
        w_f = (f_int ** 0.5) * lib_mz
        dot_prod_num += w_l * w_f
        lib_norm_sq += w_l ** 2
        feat_norm_sq += w_f ** 2
        if f_int > 0:
            rev_feat_norm_sq += w_f ** 2

    # Unmatched feat peaks add to feat_norm (forward only).
    for i in range(n_feat):
        if feat_matched[i]:
            continue
        f_mz, f_int = feat[i]
        w_f = (f_int ** 0.5) * f_mz
        feat_norm_sq += w_f ** 2

    if feat_norm_sq * lib_norm_sq > 0:
        dot = 1000 * (dot_prod_num ** 2) / (feat_norm_sq * lib_norm_sq)
    else:
        dot = 0.0
    if rev_feat_norm_sq * lib_norm_sq > 0:
        rev_dot = 1000 * (dot_prod_num ** 2) / (rev_feat_norm_sq * lib_norm_sq)
    else:
        rev_dot = 0.0

    return int(dot), int(rev_dot)