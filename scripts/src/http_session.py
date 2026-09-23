"""
Shared HTTP session for all external API calls (v3.1.0, D-8).

One process-wide ``requests.Session`` with:
- connect/read timeouts ``(5, 20)`` applied to every request,
- urllib3 ``Retry(total=3, backoff_factor=0.5)`` on 429/500/502/503/504,
- a ``User-Agent`` header identifying the tool,
- a token-bucket rate limiter of at most 4 requests/second for
  ``pubchem.ncbi.nlm.nih.gov`` (PubChem's published limit is 5/s).

Callers should use :func:`get` (or :func:`request`) rather than touching
``SESSION`` directly so the timeout and rate limiter are always applied.
"""

import threading
import time
from collections import deque
from urllib.parse import urlsplit

import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "K2-Annotator/3.1.1"
TIMEOUT = (5, 20)  # (connect, read) seconds
RETRY_STATUS = (429, 500, 502, 503, 504)

# Hosts that are rate limited -> max requests per second
RATE_LIMITS = {
    "pubchem.ncbi.nlm.nih.gov": 4,
}


class _TokenBucket:
    """Sliding-window limiter: at most ``rate`` calls in any 1 s window."""

    def __init__(self, rate):
        self.rate = int(rate)
        self._lock = threading.Lock()
        self._stamps = deque()

    def acquire(self):
        while True:
            with self._lock:
                now = time.monotonic()
                while self._stamps and now - self._stamps[0] >= 1.0:
                    self._stamps.popleft()
                if len(self._stamps) < self.rate:
                    self._stamps.append(now)
                    return
                wait = 1.0 - (now - self._stamps[0])
            time.sleep(max(wait, 0.01))


_BUCKETS = {host: _TokenBucket(rate) for host, rate in RATE_LIMITS.items()}


# ---------------------------------------------------------------------------
# Circuit breaker (v3.1.1).  When a host stops answering (timeouts, connection
# errors, exhausted retry budget) every further request to it would block for
# the full timeout and retry schedule, so a run with several hundred matches
# could spend hours waiting on lookups that cannot succeed.  After
# FAILURE_LIMIT consecutive transport failures the host is marked unavailable
# for the rest of the process and requests to it raise ServiceUnavailable
# immediately.  HTTP 4xx responses are answers, not failures, and do not count.
# Set K2_API_FAILURE_LIMIT to raise the limit, or 0 to disable the breaker.
# ---------------------------------------------------------------------------
def _failure_limit():
    try:
        return int(os.environ.get("K2_API_FAILURE_LIMIT", "1"))
    except ValueError:
        return 1


class ServiceUnavailable(requests.RequestException):
    """Raised without a network call once a host's breaker is open."""


class _Breaker:
    def __init__(self, host):
        self.host = host
        self.failures = 0
        self.open = False
        self.reason = None
        self._lock = threading.Lock()

    def record_failure(self, exc):
        limit = _failure_limit()
        with self._lock:
            self.failures += 1
            if limit > 0 and self.failures >= limit and not self.open:
                self.open = True
                self.reason = f"{type(exc).__name__}: {str(exc)[:100]}"
                print(f"[API] {self.host} is not responding ({self.reason}). "
                      f"Skipping all further requests to it for this run.")

    def record_success(self):
        with self._lock:
            self.failures = 0


_BREAKERS = {}
_BREAKERS_LOCK = threading.Lock()


def breaker_for(host):
    host = (host or "").lower()
    with _BREAKERS_LOCK:
        if host not in _BREAKERS:
            _BREAKERS[host] = _Breaker(host)
        return _BREAKERS[host]


def is_available(url_or_host):
    """False once the host's breaker has opened."""
    host = urlsplit(url_or_host).hostname if "://" in str(url_or_host) else url_or_host
    return not breaker_for(host).open


def reset_breakers():
    with _BREAKERS_LOCK:
        _BREAKERS.clear()


def breaker_status():
    """{host: {'open': bool, 'failures': n, 'reason': str}} for the run manifest."""
    with _BREAKERS_LOCK:
        return {h: {"open": b.open, "failures": b.failures, "reason": b.reason}
                for h, b in _BREAKERS.items()}


def _build_session():
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=list(RETRY_STATUS),
        allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
        raise_on_status=True,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=8)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, */*;q=0.5"})
    return session


SESSION = _build_session()


def throttle(url):
    """Block until a request to ``url``'s host is allowed by its rate limit."""
    host = (urlsplit(url).hostname or "").lower()
    bucket = _BUCKETS.get(host)
    if bucket is not None:
        bucket.acquire()


def request(method, url, **kwargs):
    """Session request with the shared timeout and per-host rate limit applied.

    Raises ``requests.RequestException`` (including ``RetryError`` once the
    retry budget is exhausted and ``Timeout``); never swallows errors.
    """
    kwargs.setdefault("timeout", TIMEOUT)
    host = (urlsplit(url).hostname or "").lower()
    breaker = breaker_for(host)
    if breaker.open:
        raise ServiceUnavailable(f"{host} marked unavailable after repeated failures "
                                 f"({breaker.reason})")
    throttle(url)
    try:
        resp = SESSION.request(method, url, **kwargs)
    except (requests.ConnectionError, requests.Timeout,
            requests.exceptions.RetryError) as e:
        breaker.record_failure(e)
        raise
    breaker.record_success()
    return resp


def get(url, **kwargs):
    return request("GET", url, **kwargs)
