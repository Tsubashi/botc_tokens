"""Helpers for fetching remote resources and decoding data URIs."""
# Standard Library
import base64
import http.client
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Application Specific
from ..__version__ import version

REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": f"botc_tokens/{version} (+https://github.com/Tsubashi/botc_tokens)",
}
FETCH_ATTEMPTS = 3
FETCH_RETRY_DELAY = 1.5
FETCH_TIMEOUT = 30


class FetchError(RuntimeError):
    """Raised when a remote resource cannot be fetched."""


def is_url(location: str) -> bool:
    """Return True if the location is an http or https URL."""
    return location.lower().startswith(("http://", "https://"))


def is_data_uri(location: str) -> bool:
    """Return True if the location is a data URI."""
    return location.startswith("data:")


def decode_data_uri(uri: str) -> bytes:
    """Decode the payload of a base64 data URI."""
    header, comma, payload = uri.partition(",")
    if not comma or ";base64" not in header:
        raise ValueError("Only base64 data URIs are supported.")
    return base64.b64decode(payload)


def fetch(url: str) -> bytes:
    """Fetch a URL, retrying transient failures, and return the response body."""
    reason: object = "unknown error"
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            return urlopen(Request(url, headers=REQUEST_HEADERS), timeout=FETCH_TIMEOUT).read()
        except HTTPError as e:
            if e.code == 404:
                raise FetchError(f"Unable to fetch {url}: not found") from e
            reason = e
        except (URLError, OSError, http.client.HTTPException) as e:  # Connection resets, timeouts, bad responses
            reason = e
        except ValueError as e:  # Malformed URLs, and ones with characters the request cannot carry
            raise FetchError(f"Unable to fetch {url}: {e}") from e
        if attempt < FETCH_ATTEMPTS:
            sleep(FETCH_RETRY_DELAY * attempt)
    raise FetchError(f"Unable to fetch {url}: {reason}")
