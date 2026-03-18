import numpy as np

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
            mass_bin = int(round(mz))
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