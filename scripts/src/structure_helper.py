"""
Structure Image Helper
Provides chemical structure images, hazard data, and spectral plots for reports
Separated from statistics visualization module in v2.7.0
Updated v2.9.0: Added enhanced hazard data via ctx-python (ToxValDB, genetox, severity)
Updated v3.1.0 (D-8): all PubChem traffic goes through the shared
``http_session`` (timeouts, retry/backoff, rate limit, User-Agent); results
are cached in memory and on disk (``~/.k2/cache/hazard_cache.json``); the
legacy guessed-endpoint ``EpaClient`` is gone and DTXSIDs are resolved with
``CTXClient`` only when an API key is supplied; a CTX hazard matrix is only
trusted when at least one record parsed, otherwise PubChem GHS is used.
Public methods never raise.
"""

import json
import os
import tempfile
import threading
import time
from urllib.parse import quote

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import requests

from src import http_session
from src.ctx_client import HAZARD_CATEGORIES, empty_matrix

PUBCHEM_PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_PUG_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"
COMPTOX_DASHBOARD = "https://comptox.epa.gov/dashboard"

CACHE_FILE_NAME = "hazard_cache.json"
CACHE_VERSION = 1
NEGATIVE_TTL_SECONDS = 7 * 24 * 3600  # negatives ("No Data", CID miss) expire after 7 days

# Errors that the fetch paths catch; nothing else is expected from requests/json/os.
FETCH_ERRORS = (requests.RequestException, ValueError, KeyError, TypeError, OSError)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def cache_dir():
    """Directory of the on-disk cache (override with ``K2_CACHE_DIR``)."""
    override = os.environ.get("K2_CACHE_DIR")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".k2", "cache")


def cache_path():
    return os.path.join(cache_dir(), CACHE_FILE_NAME)


class _HazardCache:
    """In-memory + on-disk JSON cache shared by every StructureHelper in the process.

    Sections:
      ``hazard``: key = CAS (or InChIKey/name when no CAS) ->
                  {"matrix", "summary", "url", "ts", "negative"}
      ``cid``:    key = "inchikey:<IK>" / "name:<lower name>" -> {"cid", "ts"}
    Negative entries (``negative``/``cid is None``) expire after 7 days;
    positive entries do not expire.  Transient failures are never cached.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._data = None
        self._path = None

    # -- persistence -------------------------------------------------------
    def _load(self):
        path = cache_path()
        with self._lock:
            if self._data is not None and self._path == path:
                return
            self._path = path
            self._data = {"version": CACHE_VERSION, "hazard": {}, "cid": {}}
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict) and loaded.get("version") == CACHE_VERSION:
                    self._data["hazard"] = dict(loaded.get("hazard") or {})
                    self._data["cid"] = dict(loaded.get("cid") or {})
            except FileNotFoundError:
                pass
            except (OSError, ValueError, TypeError) as e:
                print(f"[Hazard] cache unreadable ({path}): {type(e).__name__}: {e}; starting empty")

    def _save(self):
        with self._lock:
            path = self._path
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                fd, tmp = tempfile.mkstemp(prefix=".hazard_cache", suffix=".tmp", dir=os.path.dirname(path))
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(self._data, fh, indent=0, sort_keys=True)
                os.replace(tmp, path)
            except (OSError, TypeError, ValueError) as e:
                print(f"[Hazard] cache write failed ({path}): {type(e).__name__}: {e}")

    def clear_memory(self):
        """Drop the in-memory copy (the next access re-reads the disk file)."""
        with self._lock:
            self._data = None
            self._path = None

    @staticmethod
    def _expired(entry):
        try:
            return (time.time() - float(entry.get("ts", 0))) > NEGATIVE_TTL_SECONDS
        except (TypeError, ValueError):
            return True

    # -- hazard ------------------------------------------------------------
    def get_hazard(self, key):
        self._load()
        with self._lock:
            entry = self._data["hazard"].get(key)
            if not isinstance(entry, dict):
                return None
            if entry.get("negative") and self._expired(entry):
                return None
            matrix = entry.get("matrix")
            summary = entry.get("summary")
            url = entry.get("url")
            if not isinstance(matrix, dict) or not isinstance(summary, list) or not isinstance(url, str):
                return None
            return dict(matrix), list(summary), url

    def set_hazard(self, key, matrix, summary, url, negative):
        self._load()
        with self._lock:
            self._data["hazard"][key] = {
                "matrix": dict(matrix), "summary": list(summary), "url": url,
                "ts": time.time(), "negative": bool(negative),
            }
            self._save()

    # -- cid ---------------------------------------------------------------
    def get_cid(self, key):
        """Returns (found, cid): found=False when not cached (or negative expired)."""
        self._load()
        with self._lock:
            entry = self._data["cid"].get(key)
            if not isinstance(entry, dict):
                return False, None
            cid = entry.get("cid")
            if cid is None and self._expired(entry):
                return False, None
            return True, cid

    def set_cid(self, key, cid):
        self._load()
        with self._lock:
            self._data["cid"][key] = {"cid": cid, "ts": time.time()}
            self._save()


CACHE = _HazardCache()


def _hazard_flags(matrix):
    """Human-readable flags for a hazard matrix (same wording as v3.0)."""
    flags = []
    if matrix.get("Carcinogenicity", 0) > 0:
        flags.append("Carcinogen")
    if matrix.get("Mutagenicity", 0) > 0:
        flags.append("Mutagen")
    if matrix.get("Reprotoxicity", 0) > 0:
        flags.append("Reprotoxic")
    if matrix.get("Acute Toxicity", 0) == 3:
        flags.append("Fatal")
    if matrix.get("Organ Damage", 0) > 0:
        flags.append("Organ Damage")
    return flags


def _ghs_codes_to_matrix(h_codes):
    matrix = empty_matrix()
    for h in h_codes:
        if h in (350, 351):
            matrix["Carcinogenicity"] = max(matrix["Carcinogenicity"], 3 if h == 350 else 2)
        if h in (340, 341):
            matrix["Mutagenicity"] = max(matrix["Mutagenicity"], 3 if h == 340 else 2)
        if h in (360, 361, 362):
            matrix["Reprotoxicity"] = max(matrix["Reprotoxicity"], 3 if h == 360 else 2)
        if h in (300, 310, 330):
            matrix["Acute Toxicity"] = max(matrix["Acute Toxicity"], 3)
        elif h in (301, 311, 331):
            matrix["Acute Toxicity"] = max(matrix["Acute Toxicity"], 2)
        if h in (370, 372):
            matrix["Organ Damage"] = 3
        elif h in (371, 373):
            matrix["Organ Damage"] = max(matrix["Organ Damage"], 2)
        if h >= 400:
            matrix["Environmental"] = 2
    return matrix


def _extract_h_codes(obj, out):
    """Collect GHS H-codes (as ints) from a PubChem pug_view JSON tree."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "StringWithMarkup" and isinstance(v, list):
                for item in v:
                    txt = item.get("String", "") if isinstance(item, dict) else ""
                    if isinstance(txt, str) and txt.startswith("H") and txt[1:4].isdigit():
                        out.add(int(txt[1:4]))
            elif isinstance(v, (dict, list)):
                _extract_h_codes(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _extract_h_codes(item, out)
    return out


class StructureHelper:
    def __init__(self, temp_dir="temp_images", api_key=None):
        """
        Initialize structure helper with temporary directory for images

        Args:
            temp_dir: Directory for storing generated images
            api_key: EPA CCTE API key for hazard data (optional)
        """
        self.temp_dir = temp_dir
        self.api_key = api_key  # Store for enhanced hazard lookup
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

        self._cache = CACHE
        self._image_failed = set()  # filenames whose fetch failed in this process

        # CTX client (official ctx-python) is the only EPA path (v3.1.0)
        self._ctx_client = None
        if api_key:
            try:
                from src.ctx_client import CTXClient
                client = CTXClient(api_key)
                if client.is_available:
                    self._ctx_client = client
                else:
                    print("[Hazard] ctx-python unavailable; EPA lookups disabled, using PubChem GHS only")
            except (ImportError, ValueError, KeyError, TypeError, OSError) as e:
                print(f"[Hazard] CTX client init failed: {type(e).__name__}: {e}")

    # ------------------------------------------------------------------ #
    # PubChem helpers (direct PUG-REST through the shared session)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _pubchem_cid(kind, value):
        """CID for an identifier. ``None`` when PubChem has no match (400/404).

        Raises ``requests.RequestException`` on transport failure or when the
        retry budget is exhausted, so callers can distinguish "no data" from
        "could not fetch".
        """
        url = f"{PUBCHEM_PUG}/compound/{kind}/{quote(str(value), safe='')}/cids/JSON"
        r = http_session.get(url)
        if r.status_code in (400, 404):
            return None
        r.raise_for_status()
        cids = r.json().get("IdentifierList", {}).get("CID", [])
        if not cids:
            return None
        return int(cids[0])

    def _resolve_cid(self, inchikey=None, name=None):
        """Cached CID lookup by InChIKey, then by name. May raise RequestException."""
        lookups = []
        if inchikey and len(str(inchikey).strip()) > 5:
            lookups.append(("inchikey", str(inchikey).strip()))
        if name and str(name).strip():
            lookups.append(("name", str(name).strip()))

        for kind, value in lookups:
            key = f"{kind}:{value.lower() if kind == 'name' else value}"
            found, cid = self._cache.get_cid(key)
            if not found:
                cid = self._pubchem_cid(kind, value)
                self._cache.set_cid(key, cid)
            if cid:
                return cid
        return None

    @staticmethod
    def _fetch_ghs(cid):
        """GHS Classification pug_view JSON for a CID; ``None`` when absent (404)."""
        url = f"{PUBCHEM_PUG_VIEW}/data/compound/{int(cid)}/JSON"
        r = http_session.get(url, params={"heading": "GHS Classification"})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------ #
    # Public API (signatures unchanged)
    # ------------------------------------------------------------------ #
    def get_structure_image(self, inchikey, name, filename):
        """
        Fetch chemical structure image from PubChem

        Args:
            inchikey: InChIKey identifier
            name: Chemical name (unused: name lookups gave wrong structures, v3.0.2)
            filename: Output filename

        Returns:
            Path to saved PNG file, or None if fetch failed
        """
        save_path = os.path.join(self.temp_dir, filename)
        if os.path.exists(save_path):
            return save_path
        if filename in self._image_failed:
            return None

        # Only use InChIKey for structure lookup (v3.0.2)
        if not inchikey or len(str(inchikey).strip()) <= 5:
            return None

        try:
            cid = self._resolve_cid(inchikey=inchikey)
            if not cid:
                self._image_failed.add(filename)
                return None

            url = f"{PUBCHEM_PUG}/compound/cid/{cid}/PNG"
            r = http_session.get(url, params={"image_size": "large"})
            if r.status_code != 200 or not r.content.startswith(_PNG_MAGIC):
                print(f"[Structure] PubChem PNG for CID {cid} unavailable (HTTP {r.status_code})")
                self._image_failed.add(filename)
                return None

            tmp = save_path + ".part"
            with open(tmp, "wb") as fh:
                fh.write(r.content)
            os.replace(tmp, save_path)
            return save_path
        except FETCH_ERRORS as e:
            print(f"[Structure] fetch failed for {inchikey}: {type(e).__name__}: {str(e)[:120]}")
            self._image_failed.add(filename)
            return None

    def create_mirror_plot(self, feat_spectrum, lib_spectrum, title, filename):
        """
        Create mirror plot comparing experimental and library spectra

        Args:
            feat_spectrum: List of (m/z, intensity) tuples for experimental spectrum
            lib_spectrum: List of (m/z, intensity) tuples for library spectrum
            title: Plot title
            filename: Output filename

        Returns:
            Path to saved PNG file
        """
        save_path = os.path.join(self.temp_dir, filename)

        def normalize(peaks):
            if not peaks:
                return [], []
            max_i = max(i for m, i in peaks)
            return [m for m, i in peaks], [(i/max_i)*100 for m, i in peaks]

        fmz, fint = normalize(feat_spectrum)
        lmz, lint = normalize(lib_spectrum)
        lint_neg = [-x for x in lint]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.vlines(fmz, 0, fint, color='#1f77b4', label='Feature (Exp)', linewidth=1.5)
        ax.vlines(lmz, 0, lint_neg, color='#d62728', label='Library (Ref)', linewidth=1.5)
        ax.axhline(0, color='black', linewidth=1.0)

        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xlabel("m/z", fontsize=10)
        ax.set_ylabel("Relative Intensity (%)", fontsize=10)
        ax.set_ylim(-110, 110)

        ticks = [-100, -50, 0, 50, 100]
        ax.set_yticks(ticks)
        ax.set_yticklabels([str(abs(t)) for t in ticks])

        ax.legend(loc='upper right', fontsize='medium')
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        plt.close(fig)
        return save_path

    def get_hazard_matrix(self, inchikey, name, cas):
        """
        Fetch hazard classification data from EPA CompTox (ctx-python, needs an
        API key) or PubChem GHS.

        Args:
            inchikey: InChIKey identifier
            name: Chemical name
            cas: CAS number

        Returns:
            tuple: (matrix dict, summary list, epa_url string)
            Deterministic per CAS (cached); ``({}, ["Data Fetch Error"], url)``
            when the data could not be fetched.  Never raises.
        """
        cas = (cas or "").strip() if isinstance(cas, str) else (cas or "")
        epa_url = f"{COMPTOX_DASHBOARD}/search/details?search={quote(str(cas))}" if cas else f"{COMPTOX_DASHBOARD}/"

        key = str(cas) or (str(inchikey).strip() if inchikey else "") or (str(name).strip().lower() if name else "")
        if not key:
            return empty_matrix(), ["No Data"], epa_url

        cached = self._cache.get_hazard(key)
        if cached is not None:
            return cached

        try:
            # 1. EPA CompTox via ctx-python (only with an API key)
            if self._ctx_client is not None:
                dtxsid = self._ctx_client.resolve_dtxsid(cas) if cas else None
                if not dtxsid and name:
                    dtxsid = self._ctx_client.resolve_dtxsid(name)
                if dtxsid:
                    epa_url = f"{COMPTOX_DASHBOARD}/chemical/details/{dtxsid}"
                    ctx_matrix, n_records = self._ctx_client.get_hazard_matrix(dtxsid)
                    if n_records > 0:
                        summary = (_hazard_flags(ctx_matrix)[:3] + ["Source: EPA CCTE"])
                        self._cache.set_hazard(key, ctx_matrix, summary, epa_url, negative=False)
                        return dict(ctx_matrix), summary, epa_url

            # 2. PubChem GHS classification
            cid = self._resolve_cid(inchikey=inchikey, name=name)
            if not cid:
                summary = ["No Data"]
                self._cache.set_hazard(key, empty_matrix(), summary, epa_url, negative=True)
                return empty_matrix(), summary, epa_url

            data = self._fetch_ghs(cid)
            h_codes = _extract_h_codes(data, set()) if data is not None else set()
            matrix = _ghs_codes_to_matrix(h_codes)

            if any(v > 0 for v in matrix.values()):
                summary = _hazard_flags(matrix)[:4]
                negative = False
            else:
                summary = ["No GHS Data"]
                negative = True
            self._cache.set_hazard(key, matrix, summary, epa_url, negative=negative)
            return matrix, summary, epa_url

        except FETCH_ERRORS as e:
            print(f"[Hazard] fetch failed for {key}: {type(e).__name__}: {str(e)[:120]}")
            return {}, ["Data Fetch Error"], epa_url

    def get_enhanced_hazard(self, cas: str) -> dict:
        """
        Get comprehensive hazard data using ctx-python (v2.9.0).

        Fetches quantitative toxicity values from ToxValDB including:
        - NOAEL, LOAEL, POD, RfD (human health thresholds)
        - LC50, LD50 (ecological toxicity)
        - Genetic toxicity summary
        - Computed severity index (1-5)

        Args:
            cas: CAS registry number

        Returns:
            Dictionary with hazard data fields for CSV export, or empty dict if unavailable
        """
        if not self._ctx_client or not cas:
            return {}

        try:
            if not self._ctx_client.is_available:
                return {}

            profile = self._ctx_client.get_hazard_profile(cas)
            return profile.to_dict()

        except FETCH_ERRORS as e:
            # Log but don't fail - enhanced hazard data is optional
            print(f"[Hazard] enhanced hazard data not available for CAS {cas}: {type(e).__name__}: {e}")
            return {}
