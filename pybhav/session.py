"""NSE session management.

NSE's servers check for a valid browser-like session (cookies + Referer).
Warming up by hitting the homepage seeds the required cookies.
"""

from curl_cffi import requests
from curl_cffi.requests import errors
from .exceptions import SessionError
from .urls import NSE_HOME

_HEADERS = {
    "Referer": NSE_HOME,
}


def make_session(timeout: int = 10) -> requests.Session:
    """Create and warm up a requests.Session against NSE."""
    session = requests.Session(impersonate="chrome110")
    session.headers.update(_HEADERS)
    try:
        resp = session.get(NSE_HOME, timeout=timeout)
        resp.raise_for_status()
    except errors.RequestsError as exc:
        raise SessionError(f"Failed to warm up NSE session: {exc}") from exc
    return session
