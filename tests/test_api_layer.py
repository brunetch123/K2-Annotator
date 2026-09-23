"""
External-API behaviour that must not depend on the network: the circuit
breaker that stops a run from waiting on a dead service for every compound
(v3.1.1), and the --no-hazard switch.
"""
import concurrent.futures
import time

import pytest
import requests

from src import http_session
from src.structure_helper import StructureHelper
import src.ctx_client as ctx_client


@pytest.fixture(autouse=True)
def _clean_breakers(monkeypatch):
    http_session.reset_breakers()
    monkeypatch.delenv('K2_API_FAILURE_LIMIT', raising=False)
    yield
    http_session.reset_breakers()


class _Counter:
    def __init__(self, exc):
        self.calls = 0
        self.exc = exc

    def __call__(self, method, url, **kwargs):
        self.calls += 1
        raise self.exc


def test_breaker_opens_after_first_transport_failure(monkeypatch):
    counter = _Counter(requests.Timeout('read timed out'))
    monkeypatch.setattr(http_session.SESSION, 'request', counter)
    with pytest.raises(requests.Timeout):
        http_session.get('https://pubchem.ncbi.nlm.nih.gov/x')
    assert counter.calls == 1
    assert http_session.is_available('pubchem.ncbi.nlm.nih.gov') is False
    with pytest.raises(http_session.ServiceUnavailable):
        http_session.get('https://pubchem.ncbi.nlm.nih.gov/y')
    assert counter.calls == 1                      # no second network call
    assert http_session.is_available('other.host') is True


def test_breaker_limit_is_configurable(monkeypatch):
    monkeypatch.setenv('K2_API_FAILURE_LIMIT', '3')
    counter = _Counter(requests.ConnectionError('refused'))
    monkeypatch.setattr(http_session.SESSION, 'request', counter)
    for _ in range(3):
        with pytest.raises(requests.ConnectionError):
            http_session.get('https://pubchem.ncbi.nlm.nih.gov/x')
    assert counter.calls == 3 and not http_session.is_available('pubchem.ncbi.nlm.nih.gov')
    monkeypatch.setenv('K2_API_FAILURE_LIMIT', '0')
    http_session.reset_breakers()
    for _ in range(4):
        with pytest.raises(requests.ConnectionError):
            http_session.get('https://pubchem.ncbi.nlm.nih.gov/x')
    assert http_session.is_available('pubchem.ncbi.nlm.nih.gov')   # breaker disabled


def test_hazard_lookups_skipped_once_pubchem_is_down(tmp_path, monkeypatch):
    counter = _Counter(requests.Timeout('read timed out'))
    monkeypatch.setattr(http_session.SESSION, 'request', counter)
    helper = StructureHelper(str(tmp_path))
    helper._cache.clear_memory()
    monkeypatch.setattr(helper._cache, 'get_hazard', lambda key: None)
    monkeypatch.setattr(helper._cache, 'get_cid', lambda key: (False, None))
    monkeypatch.setattr(helper._cache, 'set_cid', lambda key, cid: None)
    m1 = helper.get_hazard_matrix('UHOVQNZJYSORNB-UHFFFAOYSA-N', 'benzene', '71-43-2')
    assert m1[1] == ['Data Fetch Error'] and counter.calls == 1
    m2 = helper.get_hazard_matrix('YXFVVABEGXRONW-UHFFFAOYSA-N', 'toluene', '108-88-3')
    assert m2[1] == ['Skipped (API unavailable)'] and counter.calls == 1
    assert helper.get_structure_image('YXFVVABEGXRONW-UHFFFAOYSA-N', 'toluene', 'x.png') is None
    assert counter.calls == 1
    assert helper.api_status()['pubchem'] == 'unavailable'


def test_ctx_client_gives_up_after_timeout(monkeypatch):
    monkeypatch.setattr(ctx_client, 'CTX_CALL_TIMEOUT', 0.2)
    client = ctx_client.CTXClient.__new__(ctx_client.CTXClient)
    client.api_key = 'k'
    client._ctx_available = True
    client.consecutive_failures = 0
    client.unavailable_reason = None
    calls = []

    class _Chem:
        def search(self, **kw):
            calls.append(kw)
            time.sleep(1.0)
            return []
    client._chem = _Chem()
    client._haz = None

    t0 = time.monotonic()
    assert client.resolve_dtxsid('71-43-2') is None
    assert 0.15 < time.monotonic() - t0 < 0.9     # timed out at 0.2 s, not 1 s
    assert client.is_available is False
    t1 = time.monotonic()
    assert client.resolve_dtxsid('108-88-3') is None
    assert time.monotonic() - t1 < 0.05           # immediate, no call made
    assert len(calls) == 1
    assert 'timed out' in client.unavailable_reason


def test_no_hazard_flag_skips_lookups(tmp_path, monkeypatch):
    from src.reporter import ReportGenerator
    from src.universal_parser import Feature
    counter = _Counter(requests.Timeout('x'))
    monkeypatch.setattr(http_session.SESSION, 'request', counter)
    f = Feature(1, 9.0, 763.0)
    rep = ReportGenerator({}, [f], output_dir=str(tmp_path), sample_columns=[], hazard_lookups=False)
    assert rep._hazard('IK', 'toluene', '108-88-3')[1] == ['Skipped (--no-hazard)']
    assert counter.calls == 0
