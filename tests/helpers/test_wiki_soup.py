"""Put the WikiSoup class through its paces."""
# Standard Library
from contextlib import contextmanager
from io import StringIO
from unittest import mock
import urllib

# Third Party
import pytest
import testhelpers

# Application Specific
from botc_tokens.helpers.wiki_soup import WikiSoup


@contextmanager
def web_mock(response_list=testhelpers.webmock_list):
    """Mock out actual web access."""
    # First create the return data we would expect from the web, in the order we expect it.
    urlopen_read_mock = mock.MagicMock()
    urlopen_read_mock.read.side_effect = response_list

    # Now mock out all the web calls to instead return the data we created
    with mock.patch("botc_tokens.helpers.wiki_soup.urlopen") as urlopen_mock:
        urlopen_mock.return_value.__enter__.return_value.read = urlopen_read_mock
        urlopen_mock.return_value = urlopen_read_mock
        yield


def test_wiki_soup_creation():
    """Ensure we can create a WikiSoup object."""
    with web_mock():
        wiki_soup = WikiSoup()
        assert wiki_soup
        assert wiki_soup.role_data[0]["name"] == "First"
        assert wiki_soup.night_data["firstNight"] == ["DUSK", "First"]


def test_wiki_soup_get_ability_text():
    """Ensure we can get the ability text for a role."""
    with web_mock():
        wiki_soup = WikiSoup()
        ability = wiki_soup.get_ability_text("First")
        assert ability == "First ability description"


def test_wiki_soup_get_ability_summary_not_found():
    """Handle missing ability text."""
    response_list = testhelpers.webmock_list.copy()
    response_list[2] = b"<html><body></body></html>"
    with web_mock(response_list):
        wiki_soup = WikiSoup()
        with pytest.raises(RuntimeError) as e:
            wiki_soup.get_ability_text("First")
        assert "Could not find summary section for First" in str(e.value)


def test_wiki_soup_get_ability_text_not_found():
    """Handle missing ability text."""
    response_list = testhelpers.webmock_list.copy()
    response_list[2] = b"<html><body><div><h2 id=\"Summary\">First ability</h2></div></body></html>"
    with web_mock(response_list):
        wiki_soup = WikiSoup()
        with pytest.raises(RuntimeError) as e:
            wiki_soup.get_ability_text("First")
        assert "Could not find ability description for First" in str(e.value)


def test_wiki_soup_get_reminders():
    """Ensure we can get the reminders for a role."""
    with web_mock():
        wiki_soup = WikiSoup()
        first_reminders = wiki_soup.get_reminders("First")
        second_reminders = wiki_soup.get_reminders("Second")
        assert first_reminders == []
        assert second_reminders == ["SECOND REMINDER"]


def test_wiki_soup_get_reminders_not_found():
    """Handle reminder text."""
    response_list = testhelpers.webmock_list.copy()
    response_list[2] = b"<html><body></body></html>"
    with web_mock(response_list):
        wiki_soup = WikiSoup()
        with pytest.raises(RuntimeError) as e:
            wiki_soup.get_reminders("First")
        assert "Could not find 'How To Run' section for First" in str(e.value)


def test_wiki_soup_get_icon():
    """Ensure we can get the icon for a role."""
    with web_mock():
        wiki_soup = WikiSoup()
        icon = wiki_soup.get_big_icon_url("First")
        assert icon == "First.png"


def test_wiki_soup_get_icon_not_found():
    """Handle missing icons."""
    response_list = testhelpers.webmock_list.copy()
    response_list[2] = b"<html><body></body></html>"
    with web_mock(response_list):
        wiki_soup = WikiSoup()
        with pytest.raises(RuntimeError) as e:
            wiki_soup.get_big_icon_url("First")
        assert "Could not find icon for First" in str(e.value)


def test_wiki_soup_cache():
    """Cache multiple calls to the same wiki page."""
    with web_mock():
        wiki_soup = WikiSoup()
        first_soup = wiki_soup._get_wiki_soup("First")
        second_soup = wiki_soup._get_wiki_soup("First")
        assert first_soup is second_soup


def test_wiki_soup_404():
    """Handle 404 errors."""
    response_list = testhelpers.webmock_list.copy()
    fp = StringIO()  # This is necessary to avoid an issue when deconstructing urllib.error.HTTPError
    response_list[2] = urllib.error.HTTPError("test_url", 404, "Not Found", "hdrs", fp)
    with web_mock(response_list):
        wiki_soup = WikiSoup()
        with pytest.raises(RuntimeError) as e:
            wiki_soup._get_wiki_soup("First")
        assert "Could not find role First" in str(e.value)


def test_wiki_soup_500():
    """Pass on 500 errors."""
    response_list = testhelpers.webmock_list.copy()
    fp = StringIO()  # This is necessary to avoid an issue when deconstructing urllib.error.HTTPError
    response_list[2] = urllib.error.HTTPError("test_url", 500, "Problem!", "hdrs", fp)
    with web_mock(response_list):
        wiki_soup = WikiSoup()
        with pytest.raises(urllib.error.HTTPError) as e:
            wiki_soup._get_wiki_soup("First")
        assert "Problem!" in str(e.value)


def test_wiki_soup_reminder_overrides():
    """Ensure we can get the reminders for a role."""
    with web_mock():
        wiki_soup = WikiSoup()
        # Test the known reminder system
        wiki_soup.reminders["First"] = ["KNOWN REMINDER"]
        reminders = wiki_soup.get_reminders("First")
        assert reminders == ["KNOWN REMINDER"]

        # Test the override reminder system
        wiki_soup.reminder_overrides["First"] = ["OVERRIDE REMINDER"]
        reminders = wiki_soup.get_reminders("First")
        assert reminders == ["OVERRIDE REMINDER"]


def test_disallowed_reminders():
    """Don't filter out disallowed reminders if they come from the user's reminder file."""
    with web_mock():
        wiki_soup = WikiSoup()
        wiki_soup.reminders["First"] = ["YOU ARE"]
        reminders = wiki_soup.get_reminders("First")
        assert reminders == ["YOU ARE"]
