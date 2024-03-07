"""Tests for the update command."""
from unittest import mock
import pytest

from botc_tokens.commands import update


@pytest.fixture
def web_mock():
    """Mock out actual web access."""
    urlopen_read_mock = mock.MagicMock()
    urlopen_read_mock.read.side_effect = [
        # The first call is for the role data
        b"""[
             {
                "id": "First",
                "name": "First",
                "roleType": "townsfolk",
                "print": "unused",
                "icon": "unused",
                "version": "4b - Unreleased Experimental",
                "isDisabled": false
              },
              {
                "id": "Second",
                "name": "Second",
                "roleType": "townsfolk",
                "print": "unused",
                "icon": "unused",
                "version": "4b - Unreleased Experimental",
                "isDisabled": false
              }
            ]""",
        # The second call is for the night data
        b"""{
              "firstNight": [
                "DUSK",
                "First"
              ],
              "otherNight": [
                "DUSK",
                "First",
                "Second"
              ]
            }""",
        # The third call is for the first role's wiki page
        b"""<html>
              <body>
                <div>
                    <h2 id="Summary">First ability</h2>
                    <p>First ability description</p>
                </div>
                <div id="How_to_Run"><b>First reminder</b></div>
                <div id="character-details"><img src="First.png" /></div>
              </body>
            </html>""",
    ]
    return urlopen_read_mock


@mock.patch("botc_tokens.helpers.wiki_soup.urlopen")
def test_update_command(urlopen_mock, web_mock, tmp_path):
    """Test the update command."""
    # Start by building mocks that will handle web calls
    urlopen_mock.return_value = web_mock
    with mock.patch("botc_tokens.commands.update.urlretrieve"):
        # Now we can run the command
        output_path = tmp_path / "roles"
        with mock.patch("sys.argv", ["botc_tokens", "update", "--output", str(output_path)]):
            update.run()






