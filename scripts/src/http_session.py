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

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "K2-Annotator/3.1.0"
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
    throttle(url)
    return SESSION.request(method, url, **kwargs)


def get(url, **kwargs):
    return request("GET", url, **kwargs)
