"""
Synthetic test-dataset generator for the K2 Annotator review.

Builds an MZmine-style feature table + MSP spectra, an alkane RI calibration
table, and CSV / MSP spectral libraries whose entries are designed to exercise
each Level-2 criterion of Koelmel et al. (2022) as implemented in the NYCSS
manuscript (Table 1 / SI S3):

    BFF      : max sample abundance > c * (mean_blank + 3 * SD_blank), c = 5
    RI       : |dRI| <= 50 AND |dRI| / RI_feature <= 1.5 %
    Spectra  : reverse dot > 600 AND forward dot > 500
    Exact m  : RHRMF > 75 for low-res library entries, OR dot products computed
               against an exact-mass (high-res) library entry

Every feature spectrum is built from explicit fragment *formulas*, so the exact
m/z values are the true cation masses (monoisotopic mass minus one electron),
which is what a mass spectrometer reports.  A JSON file with the expected
outcome of every (feature, library entry) pair is written alongside the data.

Run:  python make_dataset.py [out_dir]
"""
import csv
import json
import os
import sys

# ---------------------------------------------------------------------------
# Exact masses (AME2020 / NIST) — deliberately independent of the code under
# test so the generator cannot share a bug with it.
# ---------------------------------------------------------------------------
MASS = {
    'C': 12.0, 'H': 1.00782503, 'D': 2.01410178, 'N': 14.00307401,
    'O': 15.99491462, 'Cl': 34.96885268, 'Cl37': 36.96590260,
    'Br': 78.91833760, 'S': 31.97207117, 'Si': 27.97692653, 'F': 18.99840316,
    'C13': 13.00335484,
}
ELECTRON = 0.000548579909

CN_CAL = list(range(10, 27))


def alkane_rt(n):
    """Retention time (min) of the n-alkane on the synthetic method.

    Smooth, monotonic and mildly convex (spacing grows slowly with carbon
    number, as after an initial oven hold).  C10 = 15.3 min, C26 ~ 88 min.
    """
    return round(4.0 + 0.7 * (n - 4) ** 1.55, 3)


_SPLINE = None


def _spline():
    """The same interpolant K2 builds (scipy CubicSpline, not-a-knot,
    extrapolate=True) so feature RTs can be inverted through it exactly."""
    global _SPLINE
    if _SPLINE is None:
        import numpy as np
        from scipy.interpolate import CubicSpline
        rts = [alkane_rt(n) for n in CN_CAL]
        _SPLINE = CubicSpline(rts, CN_CAL, extrapolate=True)
    return _SPLINE


def cation_mz(comp):
    """comp: dict element->count. Returns m/z of the singly charged cation."""
    return sum(MASS[e] * n for e, n in comp.items()) - ELECTRON


def nominal(mz):
    return int(round(mz))


def ri_to_rt(ri):
    """Invert K2's own cubic-spline calibration numerically so that a feature
    placed at this RT gets *exactly* the designed RI back from RICalibrator
    (isolates the matching tests from extrapolation behaviour, which is
    tested separately)."""
    from scipy.optimize import brentq
    sp = _spline()
    return brentq(lambda t: sp(t) * 100.0 - ri, 0.5, 400.0, xtol=1e-9)


# ---------------------------------------------------------------------------
# Compound definitions: (formula string, RI, [(fragment composition, intensity)])
# Intensities on the NIST 999 scale.  Fragments chosen to be chemically
# sensible sub-formulas of the parent.
# ---------------------------------------------------------------------------
COMPOUNDS = {
    'Toluene': dict(formula='C7H8', ri=763, frags=[
        ({'C': 7, 'H': 7}, 999), ({'C': 7, 'H': 8}, 700), ({'C': 5, 'H': 5}, 120),
        ({'C': 5, 'H': 3}, 40), ({'C': 3, 'H': 3}, 60)]),
    'Benzene': dict(formula='C6H6', ri=652, frags=[
        ({'C': 6, 'H': 6}, 999), ({'C': 6, 'H': 5}, 352), ({'C': 4, 'H': 4}, 575),
        ({'C': 4, 'H': 3}, 242), ({'C': 4, 'H': 2}, 160), ({'C': 3, 'H': 3}, 91)]),
    'Naphthalene': dict(formula='C10H8', ri=1181, frags=[
        ({'C': 10, 'H': 8}, 999), ({'C': 10, 'H': 7}, 150), ({'C': 10, 'H': 6}, 80),
        ({'C': 8, 'H': 6}, 90), ({'C': 5, 'H': 4}, 60)]),
    'Chlorobenzene': dict(formula='C6H5Cl', ri=841, frags=[
        ({'C': 6, 'H': 5, 'Cl': 1}, 999), ({'C': 6, 'H': 5, 'Cl37': 1}, 320),
        ({'C': 6, 'H': 5}, 480), ({'C': 4, 'H': 3}, 110), ({'C': 3, 'H': 3}, 60)]),
    'Dibenzofuran': dict(formula='C12H8O', ri=1509, frags=[
        ({'C': 12, 'H': 8, 'O': 1}, 999), ({'C': 11, 'H': 7}, 250),
        ({'C': 12, 'H': 7, 'O': 1}, 150), ({'C': 10, 'H': 6}, 60)]),
    'Limonene': dict(formula='C10H16', ri=1030, frags=[
        ({'C': 5, 'H': 8}, 999), ({'C': 7, 'H': 9}, 800), ({'C': 6, 'H': 7}, 400),
        ({'C': 10, 'H': 16}, 250), ({'C': 8, 'H': 11}, 300), ({'C': 3, 'H': 5}, 350)]),
    'Diethyl phthalate': dict(formula='C12H14O4', ri=1590, frags=[
        ({'C': 8, 'H': 5, 'O': 3}, 999), ({'C': 10, 'H': 9, 'O': 3}, 300),
        ({'C': 7, 'H': 5, 'O': 2}, 100), ({'C': 7, 'H': 5, 'O': 1}, 80),
        ({'C': 12, 'H': 14, 'O': 4}, 50), ({'C': 6, 'H': 4}, 60)]),
    # deuterated surrogate (naphthalene-d8)
    'Naphthalene-d8': dict(formula='C10D8', ri=1175, frags=[
        ({'C': 10, 'D': 8}, 999), ({'C': 10, 'D': 7}, 120), ({'C': 10, 'D': 6}, 80),
        ({'C': 8, 'D': 6}, 90), ({'C': 5, 'D': 4}, 60)]),
    # 13C-labelled surrogate (PCB-like, 13C12 biphenyl)
    'Biphenyl-13C12': dict(formula='[13C]12H10', ri=1380, frags=[
        ({'C13': 12, 'H': 10}, 999), ({'C13': 12, 'H': 9}, 300), ({'C13': 12, 'H': 8}, 150),
        ({'C13': 6, 'H': 5}, 80)]),
}


def exact_spectrum(name, ppm_shift=0.0):
    c = COMPOUNDS[name]
    out = []
    for comp, inten in c['frags']:
        mz = cation_mz(comp) * (1 + ppm_shift * 1e-6)
        out.append((round(mz, 4), inten))
    return sorted(out)


def lowres_spectrum(name):
    binned = {}
    for comp, inten in COMPOUNDS[name]['frags']:
        m = nominal(cation_mz(comp))
        binned[m] = binned.get(m, 0) + inten
    return sorted(binned.items())


# ---------------------------------------------------------------------------
# Library entries.  Each: name, formula, ri, peaks, kind (LR/HR), expected
# outcome vs its target feature, and a note explaining the design.
# ---------------------------------------------------------------------------
def build_library():
    lib = []

    def add(name, formula, ri, peaks, note, target, expect, criterion):
        lib.append(dict(name=name, formula=formula, ri=ri, peaks=peaks, note=note,
                        target_feature=target, expected_pass=expect, criterion=criterion))

    # ---- Easy wins: LR (integer m/z) entries, exact RI, correct formula ----
    for nm in ['Toluene', 'Benzene', 'Naphthalene', 'Chlorobenzene',
               'Dibenzofuran', 'Limonene', 'Diethyl phthalate']:
        c = COMPOUNDS[nm]
        add(f'{nm} [LR]', c['formula'], c['ri'], lowres_spectrum(nm),
            'Low-res NIST-style entry; perfect spectrum, exact RI.  Must pass every criterion.',
            nm, True, 'all')

    # ---- Easy wins: HR (exact-mass) entries ----
    for nm in ['Toluene', 'Benzene', 'Naphthalene', 'Chlorobenzene',
               'Dibenzofuran', 'Limonene', 'Diethyl phthalate']:
        c = COMPOUNDS[nm]
        add(f'{nm} [HR]', c['formula'], c['ri'], exact_spectrum(nm),
            'Exact-mass (4-decimal) entry; identical to the feature.  Must pass.',
            nm, True, 'all')

    # ---- RI edge cases against Toluene (feature RI 763) ----
    t = COMPOUNDS['Toluene']
    add('Toluene RI+11 (1.44%) [LR]', t['formula'], t['ri'] + 11, lowres_spectrum('Toluene'),
        'dRI 11 (1.44 %): inside both windows -> should pass.', 'Toluene', True, 'RI')
    add('Toluene RI+12 (1.57%) [LR]', t['formula'], t['ri'] + 12, lowres_spectrum('Toluene'),
        'dRI 12 (1.57 %): inside +-50 but outside 1.5 % -> must fail on the percent rule.',
        'Toluene', False, 'RI')
    add('Toluene RI-60 [LR]', t['formula'], t['ri'] - 60, lowres_spectrum('Toluene'),
        'dRI 60: outside +-50 -> must fail.', 'Toluene', False, 'RI')
    # high-RI compound where the 50-unit rule is the binding one (1.5 % of 4000 = 60)
    add('Diethyl phthalate RI-shift+45 [LR]', 'C12H14O4', 1590 + 45, lowres_spectrum('Diethyl phthalate'),
        'dRI 45 = 2.8 % of 1590: inside +-50 but outside 1.5 % -> fail.', 'Diethyl phthalate', False, 'RI')

    # ---- Spectral decoys ----
    add('Reverse-dot decoy (Toluene + extra big peaks) [LR]', 'C7H8', t['ri'],
        lowres_spectrum('Toluene') + [(150, 900), (200, 800)],
        'Library carries two intense peaks absent from the feature -> reverse dot must fall below 600.',
        'Toluene', False, 'rev_dot')
    add('Isobaric-formula decoy (Toluene spectrum, formula C2H5NO4S) [LR]', 'C2H5NO4S', t['ri'],
        lowres_spectrum('Toluene'),
        'Same nominal peaks and RI as toluene, but a formula that cannot build C7H7+ (91.0542): '
        'dot products pass, RHRMF must fail.', 'Toluene', False, 'rhrmf')
    add('Toluene no-formula [LR]', '', t['ri'], lowres_spectrum('Toluene'),
        'Low-res entry with no formula: RHRMF cannot be computed -> cannot be a Level 2 match.',
        'Toluene', False, 'rhrmf')
    add('Toluene no-RI [LR]', 'C7H8', '', lowres_spectrum('Toluene'),
        'No RI: entry must be dropped at load.', 'Toluene', False, 'load')

    # ---- Labelled surrogates ----
    d8 = COMPOUNDS['Naphthalene-d8']
    add('Naphthalene-d8 [LR]', d8['formula'], d8['ri'], lowres_spectrum('Naphthalene-d8'),
        'Deuterated surrogate, low-res entry with formula C10D8.  Perfect spectrum -> should pass RHRMF.',
        'Naphthalene-d8', True, 'rhrmf')
    add('Naphthalene-d8 [HR]', d8['formula'], d8['ri'], exact_spectrum('Naphthalene-d8'),
        'Deuterated surrogate, exact-mass entry -> should pass.', 'Naphthalene-d8', True, 'all')
    c13 = COMPOUNDS['Biphenyl-13C12']
    add('Biphenyl-13C12 [LR]', c13['formula'], c13['ri'], lowres_spectrum('Biphenyl-13C12'),
        '13C-labelled surrogate, low-res entry.  Perfect spectrum -> should pass RHRMF.',
        'Biphenyl-13C12', True, 'rhrmf')
    return lib


# ---------------------------------------------------------------------------
# Features (MZmine feature table rows).  abundances: (blank1, blank2, s1..s4)
# ---------------------------------------------------------------------------
def build_features():
    feats = []

    def add(fid, name, ri, spectrum, blanks, samples, note, bff_pass, expected_matches):
        feats.append(dict(id=fid, name=name, ri=ri, rt=round(ri_to_rt(ri), 5),
                          spectrum=spectrum, blanks=blanks, samples=samples,
                          note=note, expected_bff_pass=bff_pass,
                          expected_matches=expected_matches))

    clean_bl = [150.0, 250.0]           # threshold = 5*(200 + 3*70.71) = 2060.7
    good_s = [5200.0, 6800.0, 7500.0, 0.0]

    add(1, 'Toluene', 763, exact_spectrum('Toluene'), clean_bl, good_s,
        'Clean toluene. RI 763 is BELOW the C10 alkane -> RI is extrapolated.',
        True, ['Toluene [LR]', 'Toluene [HR]', 'Toluene RI+11 (1.44%) [LR]'])
    add(2, 'Benzene', 652, exact_spectrum('Benzene'), clean_bl, good_s,
        'Clean benzene; all fragments below m/z 80 (electron-mass sensitive).',
        True, ['Benzene [LR]', 'Benzene [HR]'])
    add(3, 'Naphthalene', 1181, exact_spectrum('Naphthalene'), clean_bl, good_s,
        'Clean naphthalene inside the alkane range.', True,
        ['Naphthalene [LR]', 'Naphthalene [HR]'])
    add(4, 'Chlorobenzene', 841, exact_spectrum('Chlorobenzene'), clean_bl, good_s,
        'Clean chlorobenzene with a 37Cl isotopologue peak at 114.0045.', True,
        ['Chlorobenzene [LR]', 'Chlorobenzene [HR]'])
    add(5, 'Dibenzofuran', 1509, exact_spectrum('Dibenzofuran'), clean_bl, good_s,
        'Clean dibenzofuran.', True, ['Dibenzofuran [LR]', 'Dibenzofuran [HR]'])
    add(6, 'Limonene', 1030, exact_spectrum('Limonene'), clean_bl, good_s,
        'Clean limonene.', True, ['Limonene [LR]', 'Limonene [HR]'])
    add(7, 'Diethyl phthalate', 1590, exact_spectrum('Diethyl phthalate'), clean_bl, good_s,
        'Clean DEP.', True, ['Diethyl phthalate [LR]', 'Diethyl phthalate [HR]'])

    # BFF edge cases (toluene spectrum so spectral/RI criteria are satisfied)
    add(8, 'Toluene contaminant (blank-dominated)', 763, exact_spectrum('Toluene'),
        [8200.0, 7800.0], [900.0, 1100.0, 950.0, 0.0],
        'High in blanks, low in samples -> BFF fail -> no matches.', False, [])
    add(9, 'Toluene at BFF boundary (just above)', 763, exact_spectrum('Toluene'),
        [100.0, 100.0], [501.0, 0.0, 0.0, 0.0],
        'Blanks identical (SD 0): threshold = 5*100 = 500; max sample 501 -> pass (strict >).',
        True, ['Toluene [LR]', 'Toluene [HR]', 'Toluene RI+11 (1.44%) [LR]'])
    add(10, 'Toluene at BFF boundary (equal)', 763, exact_spectrum('Toluene'),
        [100.0, 100.0], [500.0, 0.0, 0.0, 0.0],
        'max sample == threshold (500) -> fail (strict >).', False, [])
    add(11, 'Toluene blank-only', 763, exact_spectrum('Toluene'),
        [3000.0, 3200.0], [0.0, 0.0, 0.0, 0.0],
        'Seen only in blanks -> BFF fail.', False, [])

    # co-elution: naphthalene + an intense alkane-like interferent
    coel = exact_spectrum('Naphthalene') + [
        (round(cation_mz({'C': 4, 'H': 7}), 4), 999), (round(cation_mz({'C': 5, 'H': 9}), 4), 950),
        (round(cation_mz({'C': 6, 'H': 11}), 4), 900), (round(cation_mz({'C': 7, 'H': 13}), 4), 800),
        (round(cation_mz({'C': 8, 'H': 15}), 4), 700), (round(cation_mz({'C': 9, 'H': 17}), 4), 600)]
    add(12, 'Naphthalene + co-eluting alkene', 1181, sorted(coel), clean_bl, good_s,
        'Naphthalene peaks intact but six intense foreign peaks added: reverse dot stays high, '
        'forward dot must drop below 500 -> no match by the Level 2 rules.', True, [])

    # mass-accuracy edge cases
    add(13, 'Toluene +5 ppm', 763, exact_spectrum('Toluene', ppm_shift=+5), clean_bl, good_s,
        'Realistic +5 ppm mass-axis error -> inside the 10 ppm RHRMF tolerance -> should pass.',
        True, ['Toluene [LR]', 'Toluene [HR]', 'Toluene RI+11 (1.44%) [LR]'])
    add(14, 'Toluene +30 ppm', 763, exact_spectrum('Toluene', ppm_shift=+30), clean_bl, good_s,
        'Gross +30 ppm mass error -> unit-res dot passes but RHRMF (10 ppm) and HR-aware dot must fail.',
        True, [])
    add(19, 'Toluene -5 ppm', 763, exact_spectrum('Toluene', ppm_shift=-5), clean_bl, good_s,
        'Realistic -5 ppm mass-axis error -> inside the 10 ppm RHRMF tolerance -> should pass '
        '(mirror image of feature 13; instrument error is symmetric).',
        True, ['Toluene [LR]', 'Toluene [HR]', 'Toluene RI+11 (1.44%) [LR]'])
    add(20, 'Toluene -30 ppm', 763, exact_spectrum('Toluene', ppm_shift=-30), clean_bl, good_s,
        'Gross -30 ppm mass error -> must fail exact-mass criteria.', True, [])

    # labelled surrogates
    add(15, 'Naphthalene-d8', 1175, exact_spectrum('Naphthalene-d8'), clean_bl, good_s,
        'Deuterated surrogate feature.', True, ['Naphthalene-d8 [LR]', 'Naphthalene-d8 [HR]'])
    add(16, 'Biphenyl-13C12', 1380, exact_spectrum('Biphenyl-13C12'), clean_bl, good_s,
        '13C-labelled surrogate feature.', True, ['Biphenyl-13C12 [LR]'])

    # parser edge cases
    add(17, 'No spectrum in MSP', 1000, [], clean_bl, good_s,
        'Present in the quant table but absent from the MSP file -> must not crash, no match.',
        True, [])
    add(18, 'Late eluter beyond C26', 2750, exact_spectrum('Dibenzofuran'), clean_bl, good_s,
        'RT beyond the last alkane -> RI extrapolated; no library entry near RI 2750 -> no match.',
        True, [])
    return feats


def write_dataset(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    lib = build_library()
    feats = build_features()
    blanks = ['FieldBlank_01', 'FieldBlank_02']
    samples = ['Sample_A', 'Sample_B', 'Sample_C', 'Sample_D']

    # RI calibration
    with open(os.path.join(out_dir, 'ri_cal.txt'), 'w', newline='') as f:
        f.write('Carbon number\tRT(min)\n')
        for n in CN_CAL:
            f.write(f'{n}\t{alkane_rt(n):.3f}\n')

    # MZmine quant CSV
    with open(os.path.join(out_dir, 'quant.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['row ID', 'row m/z', 'row retention time'] +
                   [f'{s} Peak area' for s in blanks + samples])
        for ft in feats:
            base_mz = max(ft['spectrum'], key=lambda p: p[1])[0] if ft['spectrum'] else 0.0
            w.writerow([ft['id'], base_mz, ft['rt']] + ft['blanks'] + ft['samples'])

    # MZmine MSP
    with open(os.path.join(out_dir, 'spectra.msp'), 'w', newline='\n') as f:
        for ft in feats:
            if not ft['spectrum']:
                continue
            base_mz = max(ft['spectrum'], key=lambda p: p[1])[0]
            f.write(f"Name: #{ft['id']} m/z {base_mz:.4f} ({ft['rt']:.2f} min)\n")
            f.write(f"RT: {ft['rt']}\n")
            f.write(f"Num Peaks: {len(ft['spectrum'])}\n")
            for mz, inten in ft['spectrum']:
                f.write(f'{mz} {inten}\n')
            f.write('\n')

    # Library CSV (no CAS so the reporter makes no network calls)
    with open(os.path.join(out_dir, 'library.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['name', 'formula', 'ri', 'cas', 'inchikey', 'peaks_json', 'source'])
        for e in lib:
            peaks = [[m, i] for m, i in e['peaks']]
            w.writerow([e['name'], e['formula'], e['ri'], '', '', json.dumps(peaks), 'synthetic'])

    # Library MSP (same content)
    with open(os.path.join(out_dir, 'library.msp'), 'w', newline='\n', encoding='utf-8') as f:
        for e in lib:
            f.write(f"NAME: {e['name']}\n")
            if e['formula']:
                f.write(f"FORMULA: {e['formula']}\n")
            if e['ri'] != '':
                f.write(f"RI: {e['ri']}\n")
            f.write(f"NUM PEAKS: {len(e['peaks'])}\n")
            for mz, inten in e['peaks']:
                f.write(f'{mz} {inten}\n')
            f.write('\n')

    # Ground truth
    truth = dict(blanks=blanks, samples=samples, bff_c_factor=5.0,
                 features=[{k: v for k, v in ft.items() if k != 'spectrum'} for ft in feats],
                 library=[{k: v for k, v in e.items() if k != 'peaks'} for e in lib])
    with open(os.path.join(out_dir, 'ground_truth.json'), 'w') as f:
        json.dump(truth, f, indent=2)
    return truth


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'data')
    t = write_dataset(out)
    print(f"wrote {len(t['features'])} features and {len(t['library'])} library entries to {out}")
