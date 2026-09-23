"""
Unit-level tests of the Level-2 criteria as implemented in K2 Annotator,
checked against the rules stated in Koelmel et al. 2022 (osac007), the
NYCSS manuscript (Table 1, SI S3) and Kwiecien et al. 2015 (HRF).

Tests marked xfail(strict=True) encode behaviour the manuscripts require but
the current code does not deliver.  Each carries a finding ID that maps to
the review report.  If a fix lands, the xfail flips to XPASS and pytest
fails loudly, which is the signal to delete the marker.
"""
import math
import os
import tempfile

import numpy as np
import pytest

from src.universal_parser import Feature
from src.spectral_math import (bin_spectrum, calculate_scores,
                               calculate_scores_hr_aware)
from src.rhrmf import (FormulaExplainer, calculate_rhrmf_variant,
                       is_library_high_res, _peak_explained_variant)
from src.library_parser import LibraryCompound, LibraryParser, _trim_spectrum
from src.ri_calibration import RICalibrator
from src.is_normalizer import InternalStandardNormalizer
from src.surrogate_analyzer import SurrogateAnalyzer, SurrogateMatch
from src.matching_engine import MatchingEngine

import make_dataset as md

EX = FormulaExplainer()


def rhrmf(feat_peaks, formula, lib_peaks):
    lc = LibraryCompound('x', formula, 1000, [list(p) for p in lib_peaks], {})
    return calculate_rhrmf_variant(feat_peaks, lc, EX, tolerance_ppm=10,
                                   include_isotopologues=True, score_mode='tic')


# ===========================================================================
# 1. Blank feature filter  (Koelmel: BFF = c * (mean_B + 3 * SD_B); NYCSS c=5,
#    keep feature if max sample abundance exceeds threshold)
# ===========================================================================
def _feature(blanks, samples):
    f = Feature(1, 10.0, 1000.0)
    for i, b in enumerate(blanks):
        f.abundances[f'B{i}'] = b
    for i, s in enumerate(samples):
        f.abundances[f'S{i}'] = s
    f.calculate_bff([f'B{i}' for i in range(len(blanks))],
                    [f'S{i}' for i in range(len(samples))], c_factor=5.0)
    return f


def test_bff_standard_formula_matches_manuscript():
    f = _feature([150.0, 250.0], [5200.0, 6800.0, 7500.0])
    expected = 5.0 * (200.0 + 3.0 * np.std([150.0, 250.0], ddof=1))
    assert f.bff_threshold == pytest.approx(expected)
    assert f.passed_bff is True


def test_bff_is_strictly_greater_than():
    assert _feature([100.0, 100.0], [501.0]).passed_bff is True
    assert _feature([100.0, 100.0], [500.0]).passed_bff is False


def test_bff_blank_only_feature_fails():
    assert _feature([3000.0, 3200.0], [0.0, 0.0]).passed_bff is False


def test_bff_single_blank_uses_zero_sd():
    f = _feature([100.0], [600.0])
    assert f.bff_threshold == pytest.approx(500.0)


def test_bff_no_blank_columns_passes_everything():
    """Design finding S-BFF-1: with zero blank columns (e.g. blank identifier
    typo) every feature passes with threshold 0 and no warning is raised."""
    f = _feature([], [1.0])
    assert f.bff_threshold == 0.0 and f.passed_bff is True


# ===========================================================================
# 2. Retention index window  (|dRI| <= 50 AND |dRI|/RI_feature <= 1.5 %)
# ===========================================================================
def _engine_with_library(tmp_path, feature_ri, lib_entries):
    """Drive MatchingEngine.run_matching with an in-memory feature and a tiny
    CSV library.  lib_entries: list of (name, formula, ri, peaks)."""
    import csv, json
    lib_path = tmp_path / 'lib.csv'
    with open(lib_path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['name', 'formula', 'ri', 'peaks_json'])
        for n, fo, ri, pk in lib_entries:
            w.writerow([n, fo, ri, json.dumps([list(p) for p in pk])])
    eng = MatchingEngine('', 'q', 'm', str(lib_path))
    eng.library_parser = LibraryParser(str(lib_path))
    eng.library_parser.load_library()

    class _P:
        def __init__(self, feats):
            self._f = feats
        def get_feature_list(self):
            return self._f
    f = Feature(1, 10.0, feature_ri)
    f.spectrum = md.exact_spectrum('Toluene')
    f.passed_bff = True
    eng.parser = _P([f])
    eng.run_matching()
    return {c.compound.name for c in eng.results.get(1, [])}


@pytest.mark.parametrize('delta, expect', [(11, True), (12, False), (-49, False), (60, False)])
def test_ri_percent_rule_binds_at_low_ri(tmp_path, delta, expect):
    # feature RI 763: 1.5 % = 11.4 units, so the % rule is the binding one
    lr = md.lowres_spectrum('Toluene')
    names = _engine_with_library(tmp_path, 763.0, [('T', 'C7H8', 763 + delta, lr)])
    assert ('T' in names) is expect


@pytest.mark.parametrize('delta, expect', [(49, True), (50, True), (51, False)])
def test_ri_absolute_rule_binds_at_high_ri(tmp_path, delta, expect):
    # feature RI 4000: 1.5 % = 60 units, so the +-50 rule is the binding one
    lr = md.lowres_spectrum('Toluene')
    names = _engine_with_library(tmp_path, 4000.0, [('T', 'C7H8', 4000 + delta, lr)])
    assert ('T' in names) is expect


@pytest.mark.xfail(strict=True, reason='Finding S-RI-2: features with RI=0 (no calibration) are '
                   'silently unmatchable; the engine should refuse or warn because RI is a '
                   'mandatory Level-2 criterion')
def test_engine_refuses_features_without_ri(tmp_path):
    lr = md.lowres_spectrum('Toluene')
    with pytest.raises(Exception):
        _engine_with_library(tmp_path, 0.0, [('T', 'C7H8', 0, lr)])


# ===========================================================================
# 3. Spectral similarity  (reverse dot > 600 AND forward dot > 500)
# ===========================================================================
def test_identical_spectra_score_1000():
    s = md.lowres_spectrum('Toluene')
    assert calculate_scores(s, s) == (1000, 1000)


def test_reverse_dot_ignores_feature_only_peaks_forward_penalises_them():
    """NYCSS Fig. 1: rev-dot ignores sample peaks absent from the library."""
    lib = md.lowres_spectrum('Naphthalene')
    feat = lib + [(55, 999), (69, 950), (83, 900), (97, 800), (111, 700), (125, 600)]
    dot, rev = calculate_scores(feat, lib)
    assert rev >= 999         # int() truncation of 999.9
    assert dot < 500          # co-elution is rejected by the forward-dot gate
    weak = lib + [(43, 999), (57, 950), (71, 700), (85, 500)]
    assert calculate_scores(weak, lib)[0] > 500   # milder interference still passes


def test_reverse_dot_penalises_library_only_peaks():
    lib = md.lowres_spectrum('Toluene') + [(150, 900), (200, 800)]
    dot, rev = calculate_scores(md.lowres_spectrum('Toluene'), lib)
    assert rev < 600


def test_empty_spectra_score_zero():
    assert calculate_scores([], md.lowres_spectrum('Toluene')) == (0, 0)
    assert calculate_scores_hr_aware([], md.exact_spectrum('Toluene')) == (0, 0)


def test_half_integer_binning_is_direction_consistent():
    b = bin_spectrum([(76.5, 1), (77.5, 1)])
    assert set(b) in ({76, 77}, {77, 78})


def test_weighting_exponent_choice_changes_scores_materially():
    """Documentation finding S-DOT-1: the manuscript cites Stein & Scott, whose
    optimised weights are m^3 * I^0.6; the code uses m^1 * I^0.5.  Same spectra,
    different numbers."""
    lib = md.lowres_spectrum('Toluene')
    feat = lib + [(77, 400), (43, 900)]

    def cos2(m_exp, i_exp):
        fb, lb = bin_spectrum(feat), bin_spectrum(lib)
        ms = sorted(set(fb) | set(lb))
        wf = np.array([(fb.get(m, 0) ** i_exp) * m ** m_exp for m in ms])
        wl = np.array([(lb.get(m, 0) ** i_exp) * m ** m_exp for m in ms])
        return 1000 * (wf @ wl) ** 2 / ((wf @ wf) * (wl @ wl))
    code = calculate_scores(feat, lib)[0]
    assert code == pytest.approx(cos2(1, 0.5), abs=1)
    assert abs(cos2(3, 0.6) - code) > 50


# ===========================================================================
# 4a. RHRMF (Kwiecien 2015): 10 ppm, electron mass subtracted, isotopologues,
#     TIC-weighted, > 75
# ===========================================================================
@pytest.mark.parametrize('name', ['Toluene', 'Naphthalene', 'Chlorobenzene',
                                  'Dibenzofuran', 'Limonene', 'Diethyl phthalate'])
def test_rhrmf_perfect_spectrum_passes(name):
    s = rhrmf(md.exact_spectrum(name), md.COMPOUNDS[name]['formula'], md.lowres_spectrum(name))
    assert s > 75, s


def test_rhrmf_perfect_benzene_scores_100():
    """S-RHRMF-1 (fixed in v3.1.0): before the electron-mass correction a
    perfect benzene spectrum scored ~85 because the three peaks below m/z 55
    were rejected."""
    s = rhrmf(md.exact_spectrum('Benzene'), 'C6H6', md.lowres_spectrum('Benzene'))
    assert s == pytest.approx(100.0), s


def test_rhrmf_all_peaks_of_perfect_benzene_are_explained():
    lc = LibraryCompound('x', 'C6H6', 1000, [list(p) for p in md.lowres_spectrum('Benzene')], {})
    count_score = calculate_rhrmf_variant(md.exact_spectrum('Benzene'), lc, EX, tolerance_ppm=10,
                                          include_isotopologues=True, score_mode='count')
    assert count_score == pytest.approx(100.0), count_score


def test_rhrmf_true_low_mz_cation_is_explained():
    """S-RHRMF-1: the ion m/z (cation) must be explained; a value sitting at
    the *neutral* mass is 10.8 ppm off at m/z 51 and must be rejected, i.e.
    the +-10 ppm window is centred on the cation."""
    parent = EX.parse_formula('C6H6')
    mz = md.cation_mz({'C': 4, 'H': 3})
    assert _peak_explained_variant(mz, parent, EX, 10, True) is True
    assert _peak_explained_variant(mz + md.ELECTRON, parent, EX, 10, True) is False
    assert _peak_explained_variant(mz * (1 + 9e-6), parent, EX, 10, True) is True
    assert _peak_explained_variant(mz * (1 - 9e-6), parent, EX, 10, True) is True
    assert _peak_explained_variant(mz * (1 + 11e-6), parent, EX, 10, True) is False


def test_rhrmf_tolerates_plus_5ppm_error():
    # +5 ppm moves the measured cation *towards* the neutral mass the code uses
    s = rhrmf(md.exact_spectrum('Toluene', +5), 'C7H8', md.lowres_spectrum('Toluene'))
    assert s > 75, s


@pytest.mark.parametrize('shift', [-9, -5, 0, +5, +9])
def test_rhrmf_window_is_symmetric(shift):
    """S-RHRMF-1 (fixed): +-10 ppm, symmetric about the measured cation m/z."""
    s = rhrmf(md.exact_spectrum('Toluene', shift), 'C7H8', md.lowres_spectrum('Toluene'))
    assert s == pytest.approx(100.0), (shift, s)


@pytest.mark.parametrize('shift', [+30, -30])
def test_rhrmf_rejects_30ppm_error(shift):
    s = rhrmf(md.exact_spectrum('Toluene', shift), 'C7H8', md.lowres_spectrum('Toluene'))
    assert s < 75


def test_rhrmf_isotopologue_37Cl_is_explained():
    parent = EX.parse_formula('C6H5Cl')
    mz37 = md.cation_mz({'C': 6, 'H': 5, 'Cl37': 1})
    assert _peak_explained_variant(mz37 + md.ELECTRON, parent, EX, 10, True) is True
    assert _peak_explained_variant(mz37 + md.ELECTRON, parent, EX, 10, False) is False


def test_rhrmf_isobaric_formula_decoy_fails():
    s = rhrmf(md.exact_spectrum('Toluene'), 'C2H5NO4S', md.lowres_spectrum('Toluene'))
    assert s < 75


def test_rhrmf_missing_formula_scores_zero():
    assert rhrmf(md.exact_spectrum('Toluene'), '', md.lowres_spectrum('Toluene')) == 0.0


def test_rhrmf_reverse_semantics_skips_feature_only_peaks():
    feat = md.exact_spectrum('Toluene') + [(200.1234, 999)]   # unexplainable, not in library
    s = rhrmf(feat, 'C7H8', md.lowres_spectrum('Toluene'))
    assert s > 75


def test_rhrmf_deuterated_surrogate_passes():
    s = rhrmf(md.exact_spectrum('Naphthalene-d8'), 'C10D8', md.lowres_spectrum('Naphthalene-d8'))
    assert s > 75, s


def test_rhrmf_13C_surrogate_passes():
    s = rhrmf(md.exact_spectrum('Biphenyl-13C12'), '[13C]12H10',
              md.lowres_spectrum('Biphenyl-13C12'))
    assert s > 75, s


def test_rhrmf_reverse_set_depends_on_library_trimming():
    """Finding S-TRIM-1: the top-20 library trim (undocumented in the SI)
    changes which feature peaks RHRMF evaluates."""
    lib_full = [(m, 999 - 30 * i) for i, m in enumerate(range(100, 125))]  # 25 peaks, m/z 100..124
    feat = md.exact_spectrum('Toluene') + [(124.0000, 999)]  # m/z 124 unexplainable by C7H8
    lib_lr_tol = md.lowres_spectrum('Toluene')
    full = rhrmf(feat, 'C7H8', lib_lr_tol + lib_full)
    trimmed = rhrmf(feat, 'C7H8', lib_lr_tol + _trim_spectrum(lib_full, 20))
    assert full != trimmed


# ===========================================================================
# 4b. High-resolution library detection and HR-aware dot product
# ===========================================================================
@pytest.mark.parametrize('name', ['Toluene', 'Naphthalene', 'Limonene',
                                  'Dibenzofuran', 'Diethyl phthalate'])
def test_hr_detector_accepts_exact_mass_entries(name):
    assert is_library_high_res(md.exact_spectrum(name)) is True


@pytest.mark.parametrize('name', ['Benzene', 'Chlorobenzene'])
def test_hr_detector_accepts_small_defect_exact_mass_entries(name):
    assert is_library_high_res(md.exact_spectrum(name)) is True


def test_hr_detector_rejects_integer_half_integer_and_one_decimal():
    assert is_library_high_res(md.lowres_spectrum('Toluene')) is False
    assert is_library_high_res([(76.5, 999), (77.5, 500), (154, 300)]) is False
    assert is_library_high_res([(93.1, 999), (91.1, 500), (136.1, 300)]) is False


def test_hr_detector_accepts_real_fragments_with_defect_between_0p4_and_0p6():
    """S-HR-1 (fixed): long-chain alkyl fragments (C28H57+ = 393.446) were
    treated as z=2 artefacts by the v3.0.21 mass-defect rule; the stored-
    precision rule accepts them."""
    spec = [(393.4455, 999), (379.4299, 800), (57.0699, 100)]   # C28H57+, C27H55+, C4H9+
    assert is_library_high_res(spec) is True


def test_hr_detector_metadata_override():
    lr = md.lowres_spectrum('Toluene')
    hr = md.exact_spectrum('Toluene')
    assert is_library_high_res(lr, {'resolution': 'high'}) is True
    assert is_library_high_res(hr, {'Resolution': 'LOW'}) is False
    assert is_library_high_res(hr, {'source': 'NIST'}) is True   # unrelated keys ignored


def test_hr_aware_dot_within_and_outside_tolerance():
    ref = md.exact_spectrum('Toluene')
    assert calculate_scores_hr_aware(ref, ref) == (1000, 1000)
    d5, r5 = calculate_scores_hr_aware(md.exact_spectrum('Toluene', +5), ref)
    assert d5 > 500 and r5 > 600
    assert calculate_scores_hr_aware(md.exact_spectrum('Toluene', +30), ref) == (0, 0)


def test_hr_match_rhrmf_not_reported_as_100(tmp_path):
    import csv
    from src.reporter import ReportGenerator
    names = None
    lib = [('Naph HR', 'C10H8', 1181, md.exact_spectrum('Naphthalene'))]
    # reuse the engine helper but capture the candidate objects
    import json
    lib_path = tmp_path / 'lib.csv'
    with open(lib_path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['name', 'formula', 'ri', 'peaks_json'])
        for n, fo, ri, pk in lib:
            w.writerow([n, fo, ri, json.dumps([list(p) for p in pk])])
    eng = MatchingEngine('', 'q', 'm', str(lib_path))
    eng.library_parser = LibraryParser(str(lib_path)); eng.library_parser.load_library()
    f = Feature(3, 30.0, 1181.0); f.spectrum = md.exact_spectrum('Naphthalene'); f.passed_bff = True

    class _P:
        def get_feature_list(self):
            return [f]
    eng.parser = _P(); eng.run_matching()
    assert eng.results
    rep = ReportGenerator(eng.results, [f], output_dir=str(tmp_path), sample_columns=[])
    path = rep.generate_csv('m.csv')
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]['HighRes?'] == 'Yes'
    assert rows[0]['RHRMF'] != '100.0'


# ===========================================================================
# 5. RI calibration (cubic spline through alkanes, extrapolated)
# ===========================================================================
def _calibrator(tmp_path, jitter=0.0, seed=0):
    rng = np.random.default_rng(seed)
    p = tmp_path / 'cal.txt'
    with open(p, 'w') as fh:
        fh.write('Carbon number\tRT(min)\n')
        for n in md.CN_CAL:
            fh.write(f'{n}\t{md.alkane_rt(n) + rng.normal(0, jitter):.3f}\n')
    return RICalibrator(str(p))


def test_ri_spline_interpolates_alkanes_exactly(tmp_path):
    cal = _calibrator(tmp_path)
    for n in md.CN_CAL:
        assert cal.rt_to_ri(md.alkane_rt(n)) == pytest.approx(100 * n, abs=1e-6)


def test_ri_spline_extrapolation_is_unbounded_and_can_be_non_monotonic(tmp_path):
    """Finding S-RI-1 (risk): outside the alkane range the RI is a cubic
    polynomial extrapolation.  With a smooth calibration the deviation from
    linear extrapolation is small, but with a curved early region (initial
    oven hold) or noisy alkane RTs the extrapolated RI can run backwards and
    place early eluters in the wrong RI window.  Nothing in the output flags an
    RI as extrapolated."""
    cal = _calibrator(tmp_path)
    r0, r1 = md.alkane_rt(10), md.alkane_rt(11)
    devs = []
    for rt in (3.0, 5.0, 8.0, 12.0):
        linear = 100 * (10 + (rt - r0) / (r1 - r0))
        devs.append(abs(cal.rt_to_ri(rt) - linear))
    print(f'\n  smooth table: max |spline - linear| below C10 = {max(devs):.1f} RI units')
    p = tmp_path / 'hold.txt'
    rts = {10: 12.5, 11: 14.2, 12: 16.6, 13: 19.8, 14: 23.6, 15: 27.8, 16: 32.2,
           17: 36.7, 18: 41.3, 19: 45.9, 20: 50.5}
    with open(p, 'w') as fh:
        fh.write('Carbon number\tRT(min)\n')
        for n, rt in rts.items():
            fh.write(f'{n}\t{rt}\n')
    hold = RICalibrator(str(p))
    ri_early = [hold.rt_to_ri(rt) for rt in (3.0, 5.0, 7.0, 9.0, 11.0)]
    print(f'  hold-shaped table: RI at RT 3,5,7,9,11 min = {[round(x) for x in ri_early]}')
    monotonic = all(a < b for a, b in zip(ri_early, ri_early[1:]))
    print(f'  monotonic below C10: {monotonic}')
    assert not monotonic or max(devs) > 0   # informational; see report


@pytest.mark.xfail(strict=True, reason='Finding S-RI-1: RICalibrator gives no indication that a RT '
                   'lies outside the calibrated alkane range')
def test_ri_calibrator_flags_extrapolation(tmp_path):
    cal = _calibrator(tmp_path)
    assert hasattr(cal, 'is_in_range')
    assert cal.is_in_range(3.0) is False


# ===========================================================================
# 6. Internal-standard normalisation and surrogate recovery
# ===========================================================================
def _is_setup():
    samples = ['Ref', 'S1', 'S2']
    f_is = Feature(1, 10, 1000); f_is.abundances = {'Ref': 1000.0, 'S1': 500.0, 'S2': 250.0}
    f_sur = Feature(2, 20, 1500); f_sur.abundances = {'Ref': 1000.0, 'S1': 500.0, 'S2': 250.0}
    norm = InternalStandardNormalizer([f_is, f_sur], samples)
    assert norm.normalize_manual(dict(f_is.abundances))
    return samples, f_is, f_sur


def test_is_normalisation_equalises_a_feature_that_tracks_the_is():
    _, _, f_sur = _is_setup()
    assert all(v == pytest.approx(1000.0) for v in f_sur.abundances.values())
    assert f_sur.normalization_factors == {'Ref': 1.0, 'S1': 2.0, 'S2': 4.0}


def test_surrogate_recovery_is_100_when_surrogate_tracks_is():
    samples, f_is, f_sur = _is_setup()
    cfg = dict(enabled=True, library_path='', spiked_samples=['S1', 'S2'],
               reference_samples=['Ref'], spike_ratios={},
               groups={'G': {'samples': ['S1', 'S2'], 'references': ['Ref']}})
    sa = SurrogateAnalyzer([f_is, f_sur], cfg, samples, [], is_config={'enabled': True, 'method': 'manual'})
    lc = LibraryCompound('Sur', 'C6H6', 1500, [[78, 999]], {})
    sa.matches = {'Sur': SurrogateMatch('Sur', 2, 1500, 1500, 0, 0, 999, 999, 100, False, lc)}
    sa.extract_abundances()
    rec = sa.calculate_recoveries()['Sur']
    assert rec == {'S1': pytest.approx(100.0), 'S2': pytest.approx(100.0)}


def test_surrogate_and_engine_use_same_ri_percent_reference(tmp_path):
    feat_ri, lib_ri = 763.0, 774.5     # 11.5/763 = 1.507 %  vs 11.5/774.5 = 1.485 %
    lr = md.lowres_spectrum('Toluene')
    engine_names = _engine_with_library(tmp_path, feat_ri, [('T', 'C7H8', lib_ri, lr)])
    f = Feature(1, 10.0, feat_ri); f.spectrum = md.exact_spectrum('Toluene')
    sa = SurrogateAnalyzer([f], {'enabled': True}, ['S'], [])
    sa.library_compounds = [LibraryCompound('T', 'C7H8', lib_ri, [list(p) for p in lr], {})]
    sur = sa.match_surrogates()
    assert ('T' in engine_names) == (sur['T'] is not None)
