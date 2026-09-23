"""
End-to-end run of scripts/cli.py on the synthetic dataset, compared against
the ground truth written by synth/make_dataset.py.
"""
import csv
import json
import os
import subprocess
import sys

import pytest

def run_cli(k2_scripts, data_dir, out_dir, library, extra=(), expect_code=0):
    env = dict(os.environ, K2_DIAG_MATCHING_CSV=os.path.join(out_dir, 'diag.csv'))
    cmd = [sys.executable, 'cli.py',
           '--quant', os.path.join(data_dir, 'quant.csv'),
           '--msp', os.path.join(data_dir, 'spectra.msp'),
           '--library', os.path.join(data_dir, library),
           '--ri-cal', os.path.join(data_dir, 'ri_cal.txt'),
           '--blank-id', 'fieldblank', '--csv-only', '--output', out_dir] + list(extra)
    r = subprocess.run(cmd, cwd=k2_scripts, capture_output=True, text=True, env=env, timeout=600)
    assert r.returncode == expect_code, (r.returncode, r.stdout[-3000:] + r.stderr[-3000:])
    if expect_code != 0:
        return [], r.stdout
    matches = [f for f in os.listdir(out_dir) if f.endswith('.csv') and '_matches_' in f]
    assert len(matches) == 1, os.listdir(out_dir)
    with open(os.path.join(out_dir, matches[0]), newline='', encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))
    return rows, r.stdout


def pairs(rows):
    return {(int(r['Feature ID']), r['Compound_Name']) for r in rows}


@pytest.fixture(scope='module')
def csv_run(k2_scripts, dataset, tmp_path_factory):
    data_dir, truth = dataset
    out = str(tmp_path_factory.mktemp('csvlib'))
    rows, log = run_cli(k2_scripts, data_dir, out, 'library.csv')
    return truth, rows, log, out


def _expected_pairs(truth):
    exp = set()
    for ft in truth['features']:
        for name in ft['expected_matches']:
            exp.add((ft['id'], name))
    return exp


def test_pipeline_runs_and_loads_library(csv_run):
    truth, rows, log, out = csv_run
    assert 'Valid Compounds (Sorted by RI): 24' in log      # 25 entries, one has no RI
    assert 'Skipped (No RI/Spectra):        1' in log
    assert 'Sample classification: 2 blank(s), 4 sample(s)' in log


def test_no_unexpected_matches(csv_run):
    """Every reported match must be one the manuscripts' rules allow."""
    truth, rows, log, out = csv_run
    unexpected = pairs(rows) - _expected_pairs(truth)
    assert not unexpected, unexpected


def test_all_expected_matches_found(csv_run):
    truth, rows, log, out = csv_run
    missing = _expected_pairs(truth) - pairs(rows)
    assert not missing, missing


def test_bff_outcomes_match_ground_truth(csv_run):
    truth, rows, log, out = csv_run
    summ = [f for f in os.listdir(out) if f.endswith('_feature_summary.csv')]
    assert len(summ) == 1
    with open(os.path.join(out, summ[0]), newline='') as fh:
        feat_rows = {int(r['Feature_ID']): r for r in csv.DictReader(fh)}
    assert len(feat_rows) == len(truth['features'])
    for ft in truth['features']:
        assert (feat_rows[ft['id']]['Passed_BFF'] == 'Yes') is ft['expected_bff_pass'], ft['name']


def test_ri_extrapolation_flag_in_outputs(csv_run):
    truth, rows, log, out = csv_run
    summ = [f for f in os.listdir(out) if f.endswith('_feature_summary.csv')][0]
    with open(os.path.join(out, summ), newline='') as fh:
        flags = {int(r['Feature_ID']): r['RI_Extrapolated'] for r in csv.DictReader(fh)}
    assert flags[1] == 'Yes'      # toluene, RI 763 < C10
    assert flags[3] == 'No'       # naphthalene, inside range
    assert flags[18] == 'Yes'     # RI 2750 > C26
    r = next(r for r in rows if int(r['Feature ID']) == 1)
    assert r['RI_Extrapolated'] == 'Yes'
    assert 'elute outside the alkane calibration range' in log


def test_run_manifest_written(csv_run):
    truth, rows, log, out = csv_run
    with open(os.path.join(out, 'run_manifest.json')) as fh:
        m = json.load(fh)
    for key in ('k2_version', 'timestamp', 'python', 'packages', 'args', 'inputs',
                'sample_classification', 'library', 'ri_calibration', 'counts', 'outputs'):
        assert key in m, key
    assert m['k2_version'] == '3.1.0'
    assert m['inputs']['library']['sha256'] and m['inputs']['quant']['size'] > 0
    assert m['sample_classification']['blanks'] == ['FieldBlank_01', 'FieldBlank_02']
    assert m['counts']['features'] == len(truth['features'])
    assert m['counts']['features_with_level2_match'] == len(set(r['Feature ID'] for r in rows))
    assert m['library']['max_peaks'] == 20 and m['args']['ri_extrapolation'] == 'spline'
    assert m['args']['api_key'] is None
    assert not os.path.exists(os.path.join(out, 'temp_assets'))


def test_zero_match_run_exits_2_and_still_writes_summaries(k2_scripts, dataset, tmp_path):
    data_dir, truth = dataset
    lib = tmp_path / 'far.csv'
    lib.write_text('name,formula,ri,peaks_json\nNothing,C7H8,9000,"[[91,999]]"\n')
    out = tmp_path / 'out'
    _, log = run_cli(k2_scripts, data_dir, str(out), 'library.csv',
                     extra=['--library', str(lib)], expect_code=2)
    assert 'NO Level 2 matches' in log
    assert any(f.endswith('_feature_summary.csv') for f in os.listdir(out))
    assert os.path.exists(out / 'run_manifest.json')


def test_missing_blanks_is_an_error_unless_allowed(k2_scripts, dataset, tmp_path):
    data_dir, truth = dataset
    _, log = run_cli(k2_scripts, data_dir, str(tmp_path / 'a'), 'library.csv',
                     extra=['--blank-id', 'nosuchblank'], expect_code=1)
    assert 'No blank columns were identified' in log
    rows, log = run_cli(k2_scripts, data_dir, str(tmp_path / 'b'), 'library.csv',
                        extra=['--blank-id', 'nosuchblank', '--allow-no-blanks'])
    assert 'Continuing WITHOUT blank filtering' in log


def test_missing_ri_cal_for_mzmine_is_an_error(k2_scripts, dataset, tmp_path):
    data_dir, truth = dataset
    cmd = [sys.executable, 'cli.py', '--quant', os.path.join(data_dir, 'quant.csv'),
           '--msp', os.path.join(data_dir, 'spectra.msp'),
           '--library', os.path.join(data_dir, 'library.csv'), '--csv-only',
           '--output', str(tmp_path)]
    r = subprocess.run(cmd, cwd=k2_scripts, capture_output=True, text=True, timeout=600)
    assert r.returncode == 1 and 'RI calibration' in r.stdout


def test_csv_only_and_pdf_only_are_exclusive(k2_scripts, dataset, tmp_path):
    data_dir, truth = dataset
    _, log = run_cli(k2_scripts, data_dir, str(tmp_path), 'library.csv',
                     extra=['--pdf-only'], expect_code=1)


def test_run_name_used_in_output_files(k2_scripts, dataset, tmp_path):
    data_dir, truth = dataset
    run_cli(k2_scripts, data_dir, str(tmp_path), 'library.csv', extra=['--name', 'MyRun'])
    names = os.listdir(tmp_path)
    assert any(n.startswith('MyRun_matches_') for n in names)
    assert any(n.startswith('MyRun_') and n.endswith('_feature_summary.csv') for n in names)


def test_bff_threshold_value_in_csv(csv_run):
    truth, rows, log, out = csv_run
    r = next(r for r in rows if int(r['Feature ID']) == 1)
    assert float(r['BFF_Threshold']) == pytest.approx(2061, abs=1)


def test_candidates_sorted_by_reverse_dot(csv_run):
    truth, rows, log, out = csv_run
    by_feat = {}
    for r in rows:
        by_feat.setdefault(int(r['Feature ID']), []).append(int(r['RevDot']))
    for fid, revs in by_feat.items():
        assert revs == sorted(revs, reverse=True), (fid, revs)


def test_msp_library_gives_same_result_as_csv(k2_scripts, dataset, tmp_path, csv_run):
    data_dir, truth = dataset
    rows_msp, _ = run_cli(k2_scripts, data_dir, str(tmp_path), 'library.msp')
    assert pairs(rows_msp) == pairs(csv_run[1])


def _diag(out):
    with open(os.path.join(out, 'diag.csv'), newline='') as fh:
        return list(csv.DictReader(fh))


def test_diag_trace_written(csv_run):
    """The diagnostic per-candidate trace is used by the review report."""
    truth, rows, log, out = csv_run
    assert _diag(out)


def test_feature_ri_reproduced_exactly(csv_run):
    truth, rows, log, out = csv_run
    seen = {int(r['feat_id']): float(r['feat_ri']) for r in _diag(out)}
    for ft in truth['features']:
        if ft['id'] in seen:
            assert seen[ft['id']] == pytest.approx(ft['ri'], abs=0.05), ft['name']


def test_exact_mass_entries_take_the_hr_path(csv_run):
    truth, rows, log, out = csv_run
    hr_flags = {r['lib_name']: r['is_hr'] for r in _diag(out) if r['lib_name'].endswith('[HR]')}
    assert hr_flags['Naphthalene [HR]'] == 'True'
    assert hr_flags['Benzene [HR]'] == 'True'
    assert hr_flags['Chlorobenzene [HR]'] == 'True'


def test_gross_mass_error_rejected_by_exact_mass_criteria(csv_run):
    truth, rows, log, out = csv_run
    for r in _diag(out):
        if int(r['feat_id']) in (14, 20) and r['lib_name'] in ('Toluene [LR]', 'Toluene [HR]'):
            assert r['passed_dot_thresholds'] == 'True'   # unit-res dot cannot tell
            assert r['final_pass'] == 'False'             # RHRMF / HR-aware dot can


def test_grouping_json_changes_blank_set(k2_scripts, dataset, tmp_path):
    data_dir, truth = dataset
    grouping = {'Sample_D': {'type': 'Blank'}, 'FieldBlank_01': {'type': 'Blank'},
                'FieldBlank_02': {'type': 'Blank'}, 'Sample_A': {'type': 'Sample'},
                'Sample_B': {'type': 'Sample'}, 'Sample_C': {'type': 'Sample'}}
    gpath = tmp_path / 'grouping.json'
    gpath.write_text(json.dumps(grouping))
    rows, log = run_cli(k2_scripts, data_dir, str(tmp_path / 'out'), 'library.csv',
                        extra=['--grouping', str(gpath)])
    assert 'Sample classification: 3 blank(s), 3 sample(s)' in log
    assert set(int(r['Feature ID']) for r in rows)  # run still produced matches
