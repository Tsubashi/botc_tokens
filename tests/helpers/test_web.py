"""Tests for the web helper."""
# Standard Library
import base64
import http.client
import io
from unittest.mock import patch
from urllib.error import HTTPError, URLError

# Third Party
import pytest

# Application Specific
from botc_tokens.helpers.web import decode_data_uri, fetch, FETCH_TIMEOUT, FetchError, is_data_uri, is_url


def ok_response(body=b"ok"):
    """Build a fake successful response."""
    return io.BytesIO(body)


def test_fetch_returns_body(fake_web):
    """A routed URL returns its bytes."""
    fake_web.routes["https://example.com/a"] = b"hello"
    assert fetch("https://example.com/a") == b"hello"
    assert fake_web.calls == ["https://example.com/a"]


def test_fetch_sends_honest_user_agent():
    """The request identifies itself honestly."""
    with patch("botc_tokens.helpers.web.urlopen", return_value=ok_response()) as mock_urlopen:
        fetch("https://example.com/a")
    request = mock_urlopen.call_args.args[0]
    assert request.headers["User-agent"].startswith("botc_tokens/")
    assert "github.com/Tsubashi/botc_tokens" in request.headers["User-agent"]


def test_fetch_uses_timeout():
    """Every request is made with a 30 second timeout."""
    with patch("botc_tokens.helpers.web.urlopen", return_value=ok_response()) as mock_urlopen:
        fetch("https://example.com/a")
    assert FETCH_TIMEOUT == 30
    assert mock_urlopen.call_args.kwargs["timeout"] == 30


def test_fetch_retries_connection_reset():
    """A dropped connection is retried."""
    with patch("botc_tokens.helpers.web.urlopen", side_effect=[ConnectionResetError(), ok_response(b"yes")]), \
            patch("botc_tokens.helpers.web.sleep") as mock_sleep:
        assert fetch("https://example.com/a") == b"yes"
    mock_sleep.assert_called_once_with(1.5)


def test_fetch_gives_up_on_remote_disconnects():
    """A server that keeps hanging up raises a FetchError after every attempt is used."""
    errors = [http.client.RemoteDisconnected("closed")] * 3
    with patch("botc_tokens.helpers.web.urlopen", side_effect=errors) as mock_urlopen, \
            patch("botc_tokens.helpers.web.sleep"):
        with pytest.raises(FetchError, match="closed"):
            fetch("https://example.com/a")
    assert mock_urlopen.call_count == 3


def test_fetch_retries_bad_status_line():
    """An HTTP protocol error that is not an OSError is retried."""
    with patch("botc_tokens.helpers.web.urlopen", side_effect=[http.client.BadStatusLine("x"), ok_response(b"ok")]), \
            patch("botc_tokens.helpers.web.sleep"):
        assert fetch("https://example.com/a") == b"ok"


def test_fetch_retries_then_succeeds():
    """A transient HTTP error is retried after a delay."""
    error = HTTPError("https://example.com/a", 503, "Unavailable", {}, None)
    with patch("botc_tokens.helpers.web.urlopen", side_effect=[error, ok_response(b"yes")]), \
            patch("botc_tokens.helpers.web.sleep") as mock_sleep:
        assert fetch("https://example.com/a") == b"yes"
    mock_sleep.assert_called_once_with(1.5)


def test_fetch_gives_up_after_attempts():
    """Repeated failures raise a FetchError."""
    errors = [URLError("down")] * 3
    with patch("botc_tokens.helpers.web.urlopen", side_effect=errors), \
            patch("botc_tokens.helpers.web.sleep") as mock_sleep:
        with pytest.raises(FetchError, match="Unable to fetch https://example.com/a"):
            fetch("https://example.com/a")
    assert mock_sleep.call_count == 2


def test_fetch_404_does_not_retry(fake_web):
    """A 404 fails immediately."""
    with patch("botc_tokens.helpers.web.sleep") as mock_sleep:
        with pytest.raises(FetchError, match="not found"):
            fetch("https://example.com/missing")
    mock_sleep.assert_not_called()
    assert len(fake_web.calls) == 1


def test_fake_web_raises_routed_exception(fake_web):
    """A routed exception is raised by the fake."""
    fake_web.routes["https://example.com/a"] = URLError("boom")
    with pytest.raises(FetchError, match="boom"):
        fetch("https://example.com/a")
    assert len(fake_web.calls) == 3


def test_is_url():
    """Only http and https locations are URLs."""
    assert is_url("https://x")
    assert is_url("HTTP://x")
    assert not is_url("/tmp/x")
    assert not is_url("data:text/plain,hi")


def test_is_data_uri():
    """Only data: locations are data URIs."""
    assert is_data_uri("data:image/png;base64,AAAA")
    assert not is_data_uri("https://x")


def test_decode_data_uri_round_trip():
    """A base64 data URI decodes to its bytes."""
    uri = "data:image/png;base64," + base64.b64encode(b"abc").decode()
    assert decode_data_uri(uri) == b"abc"


@pytest.mark.parametrize("uri", ["data:text/plain,hello", "data:nocomma"])
def test_decode_data_uri_rejects_non_base64(uri):
    """Data URIs without a base64 payload are rejected."""
    with pytest.raises(ValueError):
        decode_data_uri(uri)


@pytest.mark.parametrize("url", ["http://[::1", "https://example.com/é.json", "https://example.com/x?q=é"])
def test_fetch_rejects_urls_the_client_cannot_send(url):
    """A URL that urllib cannot parse or encode is a FetchError, raised without retrying."""
    with patch("botc_tokens.helpers.web.sleep") as mock_sleep:
        with pytest.raises(FetchError, match="Unable to fetch"):
            fetch(url)
    mock_sleep.assert_not_called()
