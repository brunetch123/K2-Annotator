"""
EPA CompTox API Client using official ctx-python package
v2.9.0 - Enhanced hazard data fetching with ToxValDB, genetox, and severity scoring
v3.1.0 - (D-8) every ctxpy call runs under a 20 s thread timeout, no broad
         ``except``, DTXSID resolution handles ctxpy's list response, and a
         GHS-like hazard matrix can be derived from ToxValDB cancer/genetox/
         toxicity records (``get_hazard_matrix``) so the legacy guessed
         ``EpaClient`` endpoint is no longer needed.

This module provides a wrapper around the ctx-python package to fetch comprehensive
hazard data including:
- Quantitative toxicity values (NOAEL, LOAEL, POD, RfD)
- Ecological toxicity (LC50, LD50)
- Genetic toxicity summary
- Computed severity index
"""

import concurrent.futures
import warnings
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests

# ctxpy does not expose a request timeout (it calls requests.request without
# one), so every call is run on a worker thread and abandoned after this long.
CTX_CALL_TIMEOUT = 20.0

# Errors that a ctxpy call or the pandas post-processing can raise.  TimeoutError
# (and concurrent.futures.TimeoutError, its subclass) is an OSError subclass.
CTX_ERRORS = (
    requests.RequestException,
    ValueError,
    KeyError,
    TypeError,
    OSError,
    AttributeError,
    IndexError,
)

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="ctx")

HAZARD_CATEGORIES = (
    "Carcinogenicity", "Mutagenicity", "Reprotoxicity",
    "Acute Toxicity", "Organ Damage", "Environmental",
)


def empty_matrix() -> Dict[str, int]:
    return {k: 0 for k in HAZARD_CATEGORIES}


def _log(msg: str) -> None:
    print(f"[Hazard] {msg}")


def _is_missing(val) -> bool:
    if val is None:
        return True
    try:
        import pandas as pd
        if pd.isna(val):
            return True
    except (TypeError, ValueError, ImportError):
        pass
    return str(val).strip() in ("", "-", "NA", "<NA>", "nan", "None")


def _to_float(val) -> Optional[float]:
    if _is_missing(val):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


@dataclass
class HazardProfile:
    """Comprehensive hazard data for a chemical"""
    dtxsid: str = ""

    # Quantitative toxicity (human health)
    noael: Optional[float] = None  # mg/kg-day
    loael: Optional[float] = None  # mg/kg-day
    pod: Optional[float] = None    # Point of Departure mg/kg-day
    rfd: Optional[float] = None    # Reference Dose mg/kg-day
    tox_source: str = ""           # Source of toxicity data

    # Ecological toxicity
    lc50: Optional[float] = None   # Fish LC50 (mg/L)
    ld50: Optional[float] = None   # Oral LD50 (mg/kg)

    # Genetic toxicity
    genetox_positive: int = 0      # Count of positive reports
    genetox_negative: int = 0      # Count of negative reports
    genetox_ames: str = ""         # Ames test result

    # Computed severity (1-5 scale)
    severity_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV export"""
        return {
            'Tox_NOAEL': self.noael if self.noael else '',
            'Tox_LOAEL': self.loael if self.loael else '',
            'Tox_POD': self.pod if self.pod else '',
            'Tox_RfD': self.rfd if self.rfd else '',
            'Tox_Source': self.tox_source,
            'Eco_LC50': self.lc50 if self.lc50 else '',
            'Eco_LD50': self.ld50 if self.ld50 else '',
            'Genetox_Positive': self.genetox_positive if self.genetox_positive > 0 else '',
            'Genetox_Negative': self.genetox_negative if self.genetox_negative > 0 else '',
            'Genetox_Ames': self.genetox_ames,
            'Severity_Index': self.severity_index if self.severity_index > 0 else '',
        }


class CTXClient:
    """
    Wrapper around ctx-python for EPA CompTox API access.

    Provides methods to:
    - Resolve CAS numbers to DTXSIDs
    - Fetch comprehensive hazard profiles including quantitative toxicity,
      ecological data, and genetic toxicity summaries
    - Derive a GHS-like hazard matrix from ToxValDB records
    - Compute severity indices based on toxicity thresholds

    Every call into ctxpy is executed on a worker thread and abandoned after
    ``CTX_CALL_TIMEOUT`` seconds; a timeout is treated as "no data".
    """

    def __init__(self, api_key: str):
        """
        Initialize the CTX client.

        Args:
            api_key: EPA CCTE API key (request from ccte_api@epa.gov)
        """
        self.api_key = api_key
        self._ctx_available = False
        self._chem = None
        self._haz = None

        # Try to import ctx-python
        try:
            import ctxpy as ctx
            self._chem = ctx.Chemical(x_api_key=api_key)
            self._haz = ctx.Hazard(x_api_key=api_key)
            self._ctx_available = True
        except ImportError:
            warnings.warn(
                "ctx-python not installed. Enhanced hazard data will not be available. "
                "Install with: pip install ctx-python"
            )
        except CTX_ERRORS as e:
            warnings.warn(f"Failed to initialize ctx-python: {e}")

    @property
    def is_available(self) -> bool:
        """Check if ctx-python is available and initialized"""
        return self._ctx_available

    # ------------------------------------------------------------------ #
    # Low-level helpers
    # ------------------------------------------------------------------ #
    def _call(self, label: str, fn, *args, **kwargs):
        """Run ``fn`` on a worker thread with a hard timeout.

        Returns the function result, or ``None`` on timeout / any error in
        ``CTX_ERRORS`` (each logged as one line).
        """
        if not self._ctx_available:
            return None
        future = _EXECUTOR.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=CTX_CALL_TIMEOUT)
        except concurrent.futures.TimeoutError:
            _log(f"CTX {label} timed out after {CTX_CALL_TIMEOUT:.0f}s")
            future.cancel()
            return None
        except CTX_ERRORS as e:
            _log(f"CTX {label} failed: {type(e).__name__}: {str(e)[:120]}")
            return None

    @staticmethod
    def _records(result):
        """Normalise a ctxpy response (list of dicts or DataFrame) to a list of dicts."""
        if result is None:
            return []
        if isinstance(result, list):
            return [r for r in result if isinstance(r, dict)]
        if isinstance(result, dict):
            return [result]
        to_dict = getattr(result, "to_dict", None)
        if callable(to_dict):
            try:
                if getattr(result, "empty", False):
                    return []
                return [r for r in to_dict(orient="records") if isinstance(r, dict)]
            except (TypeError, ValueError, KeyError, AttributeError):
                return []
        return []

    def _toxvaldb(self, by: str, dtxsid: str):
        """ToxValDB search as a list of record dicts (empty on any failure)."""
        result = self._call(f"toxvaldb/{by}", self._haz.search_toxvaldb, by=by, dtxsid=dtxsid)
        return self._records(result)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def resolve_dtxsid(self, cas: str) -> Optional[str]:
        """
        Convert CAS number (or name) to DTXSID (DSSTox Substance Identifier).

        Args:
            cas: CAS registry number (e.g., "71-43-2")

        Returns:
            DTXSID string or None if not found
        """
        if not self._ctx_available or not cas:
            return None

        result = self._call("chemical/search", self._chem.search, by='equals', query=str(cas))
        for rec in self._records(result):
            dtxsid = rec.get('dtxsid')
            if dtxsid and not _is_missing(dtxsid):
                return str(dtxsid)
        return None

    def get_hazard_matrix(self, dtxsid: str) -> Tuple[Dict[str, int], int]:
        """
        Derive a GHS-like hazard matrix from ToxValDB records.

        Returns:
            (matrix, n_records) where ``n_records`` is the number of records
            that actually parsed.  Callers must treat the matrix as unknown
            (and fall back to another source) when ``n_records == 0``.

        Mapping (conservative, only where ToxValDB carries the information):
        - cancer-summary ``cancerCall``: known/likely/probable -> 3,
          possible/suggestive/suspected -> 2
        - genetox summary: Ames positive or >5 positive reports -> Mutagenicity 2
        - toxval ``LD50`` (oral/dermal/inhalation, mg/kg): <=50 -> Acute 3,
          <=300 -> Acute 2   (GHS acute categories 1-3)
        - toxval ``LC50`` aquatic (mg/L): <1 -> Environmental 2
        Reprotoxicity and Organ Damage are not derivable from these endpoints.
        """
        matrix = empty_matrix()
        n_records = 0
        if not self._ctx_available or not dtxsid:
            return matrix, 0

        # --- Cancer calls
        for rec in self._toxvaldb('cancer', dtxsid):
            call = str(rec.get('cancerCall') or rec.get('cancer_call') or '').lower()
            if not call:
                continue
            n_records += 1
            if any(w in call for w in ('known', 'likely', 'probable', 'group 1', 'group 2a', 'category 1')):
                matrix["Carcinogenicity"] = 3
            elif any(w in call for w in ('possib', 'suggestive', 'suspect', 'group 2b', 'category 2')):
                matrix["Carcinogenicity"] = max(matrix["Carcinogenicity"], 2)

        # --- Genetox summary
        for rec in self._toxvaldb('genetox-summary', dtxsid):
            ames = str(rec.get('ames') or '').strip().lower()
            pos = _to_float(rec.get('reportsPositive'))
            if not ames and pos is None:
                continue
            n_records += 1
            if ames == 'positive' or (pos is not None and pos > 5):
                matrix["Mutagenicity"] = max(matrix["Mutagenicity"], 2)

        # --- Quantitative toxicity (LD50 / LC50)
        for rec in self._toxvaldb('all', dtxsid):
            ttype = str(rec.get('toxvalType') or '').upper()
            val = _to_float(rec.get('toxvalNumeric'))
            if val is None or not ttype:
                continue
            units = str(rec.get('toxvalUnits') or '').lower()
            if ttype.startswith('LD50'):
                n_records += 1
                if units and 'mg/kg' not in units:
                    continue
                if val <= 50:
                    matrix["Acute Toxicity"] = 3
                elif val <= 300:
                    matrix["Acute Toxicity"] = max(matrix["Acute Toxicity"], 2)
            elif ttype.startswith('LC50'):
                n_records += 1
                if units and 'mg/l' not in units:
                    continue
                if val < 1:
                    matrix["Environmental"] = 2

        return matrix, n_records

    def get_hazard_profile(self, cas: str) -> HazardProfile:
        """
        Get comprehensive hazard data for a chemical by CAS number.

        Args:
            cas: CAS registry number

        Returns:
            HazardProfile with all available data
        """
        profile = HazardProfile()

        if not self._ctx_available or not cas:
            return profile

        # First resolve CAS to DTXSID
        dtxsid = self.resolve_dtxsid(cas)
        if not dtxsid:
            return profile

        profile.dtxsid = dtxsid

        # One ToxValDB fetch serves both the human and ecological summaries
        # (this ctxpy version has no separate 'human'/'eco' search options).
        records = self._toxvaldb('all', dtxsid)
        self._fill_human_tox(profile, records)
        self._fill_eco_tox(profile, records)

        # Fetch genetic toxicity summary
        self._fetch_genetox(profile, dtxsid)

        # Compute severity index
        profile.severity_index = self._compute_severity(profile)

        return profile

    @staticmethod
    def _min_value(records, type_words, human_eco=None):
        """(min toxvalNumeric, source) over records whose toxvalType contains any word."""
        best = None
        best_src = ''
        for rec in records:
            ttype = str(rec.get('toxvalType') or '').upper()
            if not any(w in ttype for w in type_words):
                continue
            if human_eco:
                he = str(rec.get('humanEcoNt') or '').lower()
                if he and he != human_eco:
                    continue
            val = _to_float(rec.get('toxvalNumeric'))
            if val is None:
                continue
            if best is None or val < best:
                best = val
                best_src = '' if _is_missing(rec.get('source')) else str(rec.get('source'))
        return best, best_src

    def _fill_human_tox(self, profile: HazardProfile, records) -> None:
        """Fill human health toxicity values from ToxValDB records"""
        noael, src = self._min_value(records, ('NOAEL',), 'human')
        if noael is not None:
            profile.noael = noael
            profile.tox_source = src
        loael, _ = self._min_value(records, ('LOAEL',), 'human')
        if loael is not None:
            profile.loael = loael
        pod, _ = self._min_value(records, ('POD', 'BMD'), 'human')
        if pod is not None:
            profile.pod = pod
        rfd, src = self._min_value(records, ('RFD', 'RFC'), 'human')
        if rfd is not None:
            profile.rfd = rfd
            if src:
                profile.tox_source = src  # RfD source is usually more authoritative

    def _fill_eco_tox(self, profile: HazardProfile, records) -> None:
        """Fill ecological toxicity values from ToxValDB records"""
        lc50, _ = self._min_value(records, ('LC50',))
        if lc50 is not None:
            profile.lc50 = lc50
        ld50, _ = self._min_value(records, ('LD50',))
        if ld50 is not None:
            profile.ld50 = ld50

    def _fetch_genetox(self, profile: HazardProfile, dtxsid: str) -> None:
        """Fetch genetic toxicity summary"""
        for row in self._toxvaldb('genetox-summary', dtxsid):
            pos = _to_float(row.get('reportsPositive'))
            if pos is not None:
                profile.genetox_positive = int(pos)
            neg = _to_float(row.get('reportsNegative'))
            if neg is not None:
                profile.genetox_negative = int(neg)
            ames = row.get('ames')
            if not _is_missing(ames):
                profile.genetox_ames = str(ames).strip()
            break  # first row is the summary

    def _compute_severity(self, profile: HazardProfile) -> int:
        """
        Compute a severity index (1-5) based on toxicity values.

        Scoring criteria:
        - NOAEL < 1 mg/kg-day: Severity 5 (very high)
        - NOAEL < 10 mg/kg-day: Severity 4 (high)
        - NOAEL < 100 mg/kg-day: Severity 3 (moderate)
        - Ames positive: +1 severity
        - >5 positive genetox reports: +1 severity
        - LC50 < 1 mg/L (very toxic to aquatic life): +1 severity

        Returns:
            Integer 1-5, where 5 is most severe
        """
        score = 1

        # Score based on NOAEL (lower = more toxic)
        if profile.noael is not None:
            if profile.noael < 1:
                score = max(score, 5)
            elif profile.noael < 10:
                score = max(score, 4)
            elif profile.noael < 100:
                score = max(score, 3)
            elif profile.noael < 1000:
                score = max(score, 2)

        # Score based on RfD (lower = more concern)
        if profile.rfd is not None:
            if profile.rfd < 0.0001:  # < 0.1 µg/kg-day
                score = max(score, 5)
            elif profile.rfd < 0.001:
                score = max(score, 4)
            elif profile.rfd < 0.01:
                score = max(score, 3)

        # Genotoxicity concerns
        if profile.genetox_ames.lower() == 'positive':
            score = min(5, score + 1)

        if profile.genetox_positive > 10:
            score = min(5, score + 1)
        elif profile.genetox_positive > 5:
            score = max(score, 3)

        # Ecological toxicity
        if profile.lc50 is not None and profile.lc50 < 1:
            score = max(score, 4)

        if profile.ld50 is not None and profile.ld50 < 50:
            score = max(score, 4)

        return score


# Singleton instance for module-level access
_client_instance: Optional[CTXClient] = None


def get_client(api_key: str) -> CTXClient:
    """Get or create a CTXClient instance"""
    global _client_instance
    if _client_instance is None or _client_instance.api_key != api_key:
        _client_instance = CTXClient(api_key)
    return _client_instance
