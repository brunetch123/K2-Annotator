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


@pytest.mark.xfail(strict=True, reason='Finding D-3: NIST/Lib2NIST peak-line syntax "91 999; 92 700;" '
                   'is rejected line by line, so the whole entry is dropped')
def test_nist_semicolon_peak_lines(tmp_path):
    msp = "NAME: Toluene\nFORMULA: C7H8\nRI: 763\nNUM PEAKS: 3\n91 999; 92 700; 65 120;\n\n"
    lp = LibraryParser(_write(tmp_path / 'a.msp', msp))
    lp.load_library()
    assert len(lp.get_compounds()) == 1
    assert len(lp.get_compounds()[0].spectrum) == 3


@pytest.mark.xfail(strict=True, reason='Finding D-3: a UTF-8 BOM (Excel "CSV UTF-8" / some MSP '
                   'exporters) hides the first key, so the first entry is silently skipped')
def test_bom_msp(tmp_path):
    lp = LibraryParser(_write(tmp_path / 'a.msp', MSP_OK, encoding='utf-8-sig'))
    lp.load_library()
    assert len(lp.get_compounds()) == 1


@pytest.mark.xfail(strict=True, reason='Finding D-3: "Retention_index:" and "NUM_PEAKS:" '
                   '(MassBank / NIST export spellings) are not recognised; entry silently skipped')
def test_massbank_key_spellings(tmp_path):
    msp = "NAME: Toluene\nFORMULA: C7H8\nRetention_index: SemiStdNP=763/8/25\nNUM_PEAKS: 3\n91 999\n92 700\n65 120\n\n"
    lp = LibraryParser(_write(tmp_path / 'a.msp', msp))
    lp.load_library()
    assert len(lp.get_compounds()) == 1


@pytest.mark.xfail(strict=True, reason='Finding D-3: MSP entries not separated by a blank line are '
                   'merged into one compound')
def test_msp_without_blank_line_separator(tmp_path):
    msp = MSP_OK.rstrip('\n') + "\nNAME: Xylene\nFORMULA: C8H10\nRI: 870\nNUM PEAKS: 2\n91 999\n106 600\n"
    lp = LibraryParser(_write(tmp_path / 'a.msp', msp))
    lp.load_library()
    assert len(lp.get_compounds()) == 2


QUANT = ("row ID,row m/z,row retention time,FieldBlank_01 Peak area,Sample_A Peak area\n"
         "1,91.05,8.99,100,5000\n")


def _mzmine_msp(name_key='Name', peaks_key='Num Peaks'):
    return f"{name_key}: #1 m/z 91.0542 (8.99 min)\nRT: 8.99\n{peaks_key}: 2\n91.0542 999\n92.0621 700\n\n"


def test_mzmine_msp_reference_case(tmp_path):
    up = UniversalParser('', 'fieldblank')
    up.parse_files(_write(tmp_path / 'q.csv', QUANT), _write(tmp_path / 's.msp', _mzmine_msp()))
    assert len(up.get_feature_list()[0].spectrum) == 2


@pytest.mark.xfail(strict=True, reason='Finding D-3: format detection is case-insensitive but the '
                   'MZmine MSP parser is case-sensitive ("NAME:" / "NUM PEAKS:" give empty spectra)')
def test_mzmine_msp_uppercase_keys(tmp_path):
    up = UniversalParser('', 'fieldblank')
    up.parse_files(_write(tmp_path / 'q.csv', QUANT),
                   _write(tmp_path / 's.msp', _mzmine_msp('NAME', 'NUM PEAKS')))
    assert len(up.get_feature_list()[0].spectrum) == 2


@pytest.mark.xfail(strict=True, reason='Finding D-2: a blank identifier that matches no column '
                   'yields zero blanks, a BFF threshold of 0 for every feature, and only a print')
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
