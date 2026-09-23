"""
Input-layer robustness tests (findings D-* in the report).  Each xfail encodes
the behaviour a user would reasonably expect from the documented formats.
"""
import os

import pytest

from src.library_parser import LibraryParser
from src.universal_parser import UniversalParser
from src.ri_calibration import RICalibrator


def _write(path, text, encoding='utf-8'):
    with open(path, 'w', encoding=encoding, newline='') as fh:
        fh.write(text)
    return str(path)


MSP_OK = "NAME: Toluene\nFORMULA: C7H8\nRI: 763\nNUM PEAKS: 3\n91 999\n92 700\n65 120\n\n"


def test_reference_msp_loads(tmp_path):
    lp = LibraryParser(_write(tmp_path / 'a.msp', MSP_OK))
    lp.load_library()
    assert len(lp.get_compounds()) == 1


def test_nist_semicolon_peak_lines(tmp_path):
    msp = "NAME: Toluene\nFORMULA: C7H8\nRI: 763\nNUM PEAKS: 3\n91 999; 92 700; 65 120;\n\n"
    lp = LibraryParser(_write(tmp_path / 'a.msp', msp))
    lp.load_library()
    assert len(lp.get_compounds()) == 1
    assert len(lp.get_compounds()[0].spectrum) == 3


def test_bom_msp(tmp_path):
    lp = LibraryParser(_write(tmp_path / 'a.msp', MSP_OK, encoding='utf-8-sig'))
    lp.load_library()
    assert len(lp.get_compounds()) == 1


def test_massbank_key_spellings(tmp_path):
    msp = "NAME: Toluene\nFORMULA: C7H8\nRetention_index: SemiStdNP=763/8/25\nNUM_PEAKS: 3\n91 999\n92 700\n65 120\n\n"
    lp = LibraryParser(_write(tmp_path / 'a.msp', msp))
    lp.load_library()
    assert len(lp.get_compounds()) == 1


def test_msp_without_blank_line_separator(tmp_path):
    msp = MSP_OK.rstrip('\n') + "\nNAME: Xylene\nFORMULA: C8H10\nRI: 870\nNUM PEAKS: 2\n91 999\n106 600\n"
    lp = LibraryParser(_write(tmp_path / 'a.msp', msp))
    lp.load_library()
    assert len(lp.get_compounds()) == 2


QUANT = ("row ID,row m/z,row retention time,FieldBlank_01 Peak area,Sample_A Peak area\n"
         "1,91.05,8.99,100,5000\n")


def test_mzmine_quant_variants(tmp_path):
    msp = _write(tmp_path / 's.msp', _mzmine_msp())
    # Peak height columns and datafile:X.mzML:area columns are accepted and names normalised
    q = ("row ID,row m/z,row retention time,FieldBlank_01.mzML Peak height,datafile:Sample_A.mzML:area\n"
         "1,91.05,8.99,100,5000\n")
    up = UniversalParser('', 'fieldblank')
    up.parse_files(_write(tmp_path / 'q.csv', q), msp)
    assert up.blank_columns == ['FieldBlank_01'] and up.sample_columns == ['Sample_A']
    assert up.get_feature_list()[0].abundances == {'FieldBlank_01': 100.0, 'Sample_A': 5000.0}


def test_mzmine_quant_errors(tmp_path):
    msp = _write(tmp_path / 's.msp', _mzmine_msp())
    with pytest.raises(ValueError, match='No quantification columns'):
        UniversalParser('', 'fieldblank').parse_files(
            _write(tmp_path / 'q1.csv', "row ID,row m/z,row retention time,X\n1,91,8.99,5\n"), msp)
    with pytest.raises(ValueError, match="not an integer"):
        UniversalParser('', 'fieldblank').parse_files(
            _write(tmp_path / 'q2.csv', QUANT.replace('\n1,', '\nF1,')), msp)
    with pytest.raises(ValueError, match='required column'):
        UniversalParser('', 'fieldblank').parse_files(
            _write(tmp_path / 'q3.csv', QUANT.replace('row retention time', 'rt')), msp)
    with pytest.raises(ValueError, match='non-empty'):
        UniversalParser('', '')


def test_sample_types_override_and_unknown_names(tmp_path):
    msp = _write(tmp_path / 's.msp', _mzmine_msp())
    q = _write(tmp_path / 'q.csv', QUANT)
    up = UniversalParser('', 'fieldblank')
    up.parse_files(q, msp, sample_types={'Sample_A': 'blank', 'FieldBlank_01': 'sample'})
    assert up.blank_columns == ['Sample_A'] and up.sample_columns == ['FieldBlank_01']
    with pytest.raises(ValueError, match='not found'):
        UniversalParser('', 'fieldblank').parse_files(q, msp, sample_types={'Nope': 'blank'})


def test_msp_extra_syntax(tmp_path):
    from src.msp_reader import read_msp
    p = _write(tmp_path / 'x.msp',
               "Name: A\r\nFormula: C7H8\r\nRI: 763\r\nNum Peaks: 3\r\n91\t999\r\n(92 700)\r\n65 120 \"C5H5+\"\r\n"
               "\r\nNAME: B\nRI: 800\nNum Peaks: 5\n50 1\n51 2\n")
    warnings = []
    recs = read_msp(p, warn=warnings.append)
    assert [len(pk) for _, pk in recs] == [3, 2]
    assert recs[0][1] == [(91.0, 999.0), (92.0, 700.0), (65.0, 120.0)]
    assert any('differs' in w for w in warnings)


def _mzmine_msp(name_key='Name', peaks_key='Num Peaks'):
    return f"{name_key}: #1 m/z 91.0542 (8.99 min)\nRT: 8.99\n{peaks_key}: 2\n91.0542 999\n92.0621 700\n\n"


def test_mzmine_msp_reference_case(tmp_path):
    up = UniversalParser('', 'fieldblank')
    up.parse_files(_write(tmp_path / 'q.csv', QUANT), _write(tmp_path / 's.msp', _mzmine_msp()))
    assert len(up.get_feature_list()[0].spectrum) == 2


def test_mzmine_msp_uppercase_keys(tmp_path):
    up = UniversalParser('', 'fieldblank')
    up.parse_files(_write(tmp_path / 'q.csv', QUANT),
                   _write(tmp_path / 's.msp', _mzmine_msp('NAME', 'NUM PEAKS')))
    assert len(up.get_feature_list()[0].spectrum) == 2


def test_zero_blank_columns_is_an_error(tmp_path):
    up = UniversalParser('', 'feildblank')   # typo
    with pytest.raises(Exception):
        up.parse_files(_write(tmp_path / 'q.csv', QUANT), _write(tmp_path / 's.msp', _mzmine_msp()))


def test_ri_cal_without_header(tmp_path):
    cal = RICalibrator(_write(tmp_path / 'cal.txt', "10\t15.25\n11\t18.29\n12\t21.58\n13\t25.1\n"))
    assert cal.carbon_numbers == [10, 11, 12, 13]


def test_ri_cal_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        RICalibrator(str(tmp_path / 'does_not_exist.txt'))
