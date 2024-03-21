"""Tests for the update command."""
# Standard Library
from contextlib import contextmanager
from io import StringIO
import json
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

# Third Party
from testhelpers import check_output_folder, expected_role_json, webmock_list

# Application Specific
from botc_tokens.commands import update
from botc_tokens.helpers.role import Role


@contextmanager
def web_mock():
    """Mock out actual web access."""
    # First create the return data we would expect from the web, in the order we expect it.
    wiki_read_mock = mock.MagicMock()
    wiki_read_mock.read.side_effect = webmock_list
    image_read_mock = mock.MagicMock()
    image_read_mock.read.return_value = (Path(__file__).parent.parent / "data" / "icons" / "1.png").read_bytes()

    # Now mock out all the web calls to instead return the data we created
    with mock.patch("botc_tokens.helpers.wiki_soup.urlopen") as wiki_soup_urlopen_mock:
        wiki_soup_urlopen_mock.return_value.__enter__.return_value.read = wiki_read_mock
        wiki_soup_urlopen_mock.return_value = wiki_read_mock
        # Make sure to patch out urlretrieve, as we don't want to actually download the images
        with mock.patch("botc_tokens.commands.update.urlopen") as update_urlopen_mock:
            update_urlopen_mock.return_value.__enter__.return_value.read = image_read_mock
            update_urlopen_mock.return_value = image_read_mock
            fake_image = Path(__file__).parent.parent / "data" / "icons" / "1.png"
            update_urlopen_mock.read.return_value = fake_image.read_bytes()
            yield


def check_expected_json(input_file_path):
    """Ensure each file exists and, if it is a json file, matches what we expect."""
    assert input_file_path.is_file()
    if input_file_path.suffix == ".json":
        assert input_file_path.name in expected_role_json
        with open(input_file_path, "r") as f:
            j = json.load(f)
        assert j == expected_role_json.get(input_file_path.name)


def test_update_command(tmp_path):
    """Test the update command in its normal configuration."""
    output_path = tmp_path / "roles"
    with mock.patch("sys.argv", ["botc_tokens", "update", "--output", str(output_path)]):
        with web_mock():
            update.run()

    # Verify that it worked
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "First.json"),
        str(Path("54 - Unreal Experimental") / "townsfolk" / "First.png"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.png"),
    ]
    check_output_folder(output_path, expected_files=expected_files, check_func=check_expected_json)


def test_update_existing_folder(tmp_path):
    """Test when a file in the output folder already exists."""
    output_path = tmp_path / "roles"
    output_path.mkdir()
    first_file = output_path / "54 - Unreal Experimental" / "townsfolk" / "First.json"
    first_file.parent.mkdir(parents=True, exist_ok=True)
    with open(first_file, "w") as f:
        json.dump(expected_role_json.get("First.json"), f)
    with mock.patch("sys.argv", ["botc_tokens", "update", "--output", str(output_path)]):
        with web_mock():
            update.run()

    # Verify that it worked
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "First.json"),
        str(Path("54 - Unreal Experimental") / "townsfolk" / "First.png"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.png"),
    ]
    check_output_folder(output_path, expected_files=expected_files, check_func=check_expected_json)


def test_update_bad_json(tmp_path, capsys):
    """Test when a file in the output folder exists, but isn't in the format we expect."""
    output_path = tmp_path / "roles"
    output_path.mkdir()
    first_file = output_path / "54 - Unreal Experimental" / "townsfolk" / "First.json"
    first_file.parent.mkdir(parents=True, exist_ok=True)
    with open(first_file, "w") as f:
        f.write("This is not json")
    with mock.patch("sys.argv", ["botc_tokens", "update", "--output", str(output_path)]):
        with web_mock():
            update.run()

    # Verify that we got the files we expected
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "First.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.png"),
    ]
    check_output_folder(output_path, expected_files=expected_files)

    # Make sure the file we wrote is still there, unmodified
    with open(first_file, "r") as f:
        assert f.read() == "This is not json"

    # Make sure we notified the user that the file was bad
    output = capsys.readouterr()
    assert "Could not read" in output.out


def test_update_script_filter(tmp_path):
    """Test the script filter option."""
    output_path = tmp_path / "roles"
    with mock.patch("sys.argv",
                    ["botc_tokens", "update", "--output", str(output_path), "--script-filter", "99 - Ignored"]
                    ):
        with web_mock():
            update.run()

    # Verify that it worked
    expected_files = [
        str(Path("99 - Ignored") / "outsider" / "Third.json"),
        str(Path("99 - Ignored") / "outsider" / "Third.png"),
    ]
    check_output_folder(output_path, expected_files=expected_files)


def test_update_missing(tmp_path, capsys):
    """Test when the wiki doesn't return the expected data."""
    output_path = tmp_path / "roles"
    with mock.patch("sys.argv", ["botc_tokens", "update", "--output", str(output_path), "--script-filter", ""]):
        with web_mock():
            update.run()

    # Check if we alerted to user to not being able to find the role info
    output = capsys.readouterr()
    assert "No ability found" in output.out
    assert "No icon found" in output.out
    assert "No reminder info found" in output.out


def test_update_icon_already_exists(tmp_path):
    """Test when the icon already exists."""
    output_path = tmp_path / "roles"
    output_path.mkdir()
    icon_path = output_path / "54 - Unreal Experimental" / "townsfolk" / "First.png"
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    icon_path.touch()
    with mock.patch("sys.argv", ["botc_tokens", "update", "--output", str(output_path)]):
        with web_mock():
            update.run()

    # Verify that it worked
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "First.json"),
        str(Path("54 - Unreal Experimental") / "townsfolk" / "First.png"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.png"),
    ]
    check_output_folder(output_path, expected_files=expected_files)


def test_update_custom_reminders_file(tmp_path):
    """Test when the reminders file is specified."""
    reminders_file = tmp_path / "reminders.json"
    with open(reminders_file, "w") as f:
        json.dump({"First": ["Custom reminder"]}, f)
    output_path = tmp_path / "roles"
    with mock.patch("sys.argv",
                    ["botc_tokens", "update", "--output", str(output_path), "--reminders", str(reminders_file)]
                    ):
        with web_mock():
            update.run()

    # Verify that it worked
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "First.json"),
        str(Path("54 - Unreal Experimental") / "townsfolk" / "First.png"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.png"),
    ]
    check_output_folder(output_path, expected_files=expected_files)
    with open(output_path / "54 - Unreal Experimental" / "townsfolk" / "First.json", "r") as f:
        j = json.load(f)
    assert j["reminders"] == ["Custom reminder"]
    with open(output_path / "54 - Unreal Experimental" / "demon" / "Second.json", "r") as f:
        j = json.load(f)
    assert j["reminders"] == ["SECOND REMINDER"]


def test_update_existing_icon_and_json(tmp_path):
    """Test when the icon and json file already exist."""
    output_path = tmp_path / "roles"
    output_path.mkdir()
    icon_path = output_path / "54 - Unreal Experimental" / "townsfolk" / "First.png"
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    icon_path.touch()
    json_path = output_path / "54 - Unreal Experimental" / "townsfolk" / "First.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as f:
        json.dump(expected_role_json.get("First.json"), f)
    with mock.patch("sys.argv", ["botc_tokens", "update", "--output", str(output_path)]):
        with web_mock():
            update.run()

    # Verify that it worked
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "First.json"),
        str(Path("54 - Unreal Experimental") / "townsfolk" / "First.png"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "Second.png"),
    ]
    check_output_folder(output_path, expected_files=expected_files)


def test_web_error_getting_icon(tmp_path, capsys):
    """Alert the user if we fail to get the icon."""
    output_path = tmp_path / "roles"
    wiki = mock.MagicMock()
    wiki.get_big_icon_url.return_value = "First.png"
    found_role = Role(name="First")
    with mock.patch("botc_tokens.commands.update.urlopen") as urlopen_mock:
        image_read_mock = mock.MagicMock()
        fp = StringIO()  # This is necessary to avoid an issue when deconstructing urllib.error.HTTPError
        image_read_mock.read.side_effect = HTTPError("First.png", 404, "Failed to get icon", "hdrs", fp)
        urlopen_mock.return_value.__enter__.return_value.read = image_read_mock
        urlopen_mock.return_value = image_read_mock
        update.get_role_icon(found_role, output_path, wiki)
    output = capsys.readouterr()
    assert "Unable to download icon" in output.out


def test_invalid_reminder_file(tmp_path, capsys):
    """Alert the user if the reminders file doesn't match the schema."""
    reminders_file = tmp_path / "reminders.json"
    with open(reminders_file, "w") as f:
        f.write('{"Librarian": 2}')
    output_path = tmp_path / "roles"
    with mock.patch("sys.argv",
                    ["botc_tokens", "update", "--output", str(output_path), "--reminders", str(reminders_file)]
                    ):
        with web_mock():
            update.run()
    output = capsys.readouterr()
    assert "does not match the schema:" in output.out
