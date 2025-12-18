"""Tests for the update command."""
# Standard Library
from contextlib import contextmanager
from io import StringIO
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

# Third Party
from testhelpers import check_output_folder, expected_role_json, webmock_list

# Application Specific
from botc_tokens.commands import update
from botc_tokens.helpers.role import Role


def web_response(url):
    """Routes mock response based on URL.

    Args:
        url (str): The URL on which the call has been made.
    """
    web_read_mock = MagicMock()
    if url.find('roles.json') != -1:
        web_read_mock.read.return_value = webmock_list[0]
    elif url.find('nightsheet.json') != -1:
        web_read_mock.read.return_value = webmock_list[1]
    elif url.find('/First') != -1:
        web_read_mock.read.return_value = webmock_list[2]
    elif url.find('/Second') != -1:
        web_read_mock.read.return_value = webmock_list[3]
    elif url.find('/Third') != -1:
        web_read_mock.read.return_value = webmock_list[4]
    elif url.find('bloodstar') != -1:
        web_read_mock.read.return_value = webmock_list[5]
    return web_read_mock


@contextmanager
def web_mock():
    """Mock out actual web access."""
    # First create the return data we would expect from the web, in the order we expect it.
    image_read_mock = MagicMock()
    image_read_mock.read.return_value = (Path(__file__).parent.parent / "data" / "icons" / "1.png").read_bytes()

    # Now mock out all the web calls to instead return the data we created
    with patch("botc_tokens.helpers.wiki_soup.urlopen") as wiki_soup_urlopen_mock:
        wiki_soup_urlopen_mock.return_value.__enter__.reuturn_value.read = web_response
        wiki_soup_urlopen_mock.side_effect = web_response
        # Make sure to patch it in the update command as well, since we don't want to actually download the images
        with patch("botc_tokens.commands.update.urlopen") as update_urlopen_mock:
            update_urlopen_mock.return_value.__enter__.return_value.read = image_read_mock
            update_urlopen_mock.return_value = image_read_mock
            fake_image = Path(__file__).parent.parent / "data" / "icons" / "1.png"
            update_urlopen_mock.read.return_value = fake_image.read_bytes()
            yield


def _run_cmd(arg_list):
    argv_patch = ["botc_tokens", "update"]
    argv_patch.extend(arg_list)

    with patch("sys.argv", argv_patch):
        with web_mock():
            update.run()


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
    _run_cmd(["--output", str(output_path)])

    # Verify that it worked
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.json"),
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.png"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.png"),
        str(Path("99 - Ignored") / "outsider" / "third.json"),
    ]
    check_output_folder(output_path, expected_files=expected_files, check_func=check_expected_json)


def test_update_command_custom_json_url(tmp_path):
    """Test the update command with web hosted custom json url roles."""
    reminders_file = tmp_path / "reminders.json"
    with open(reminders_file, "w") as f:
        json.dump({"Second": ["SECOND REMINDER"]}, f)
    output_path = tmp_path / "roles"
    _run_cmd(["--output", str(output_path), "-c", "https://bloodstar.xyz/p/user/script/script.json?1", "--reminders",
              str(reminders_file)])

    # Verify that it worked
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.json"),
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.png"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.png"),
        str(Path("99 - Ignored") / "outsider" / "third.json"),
    ]
    check_output_folder(output_path, expected_files=expected_files, check_func=check_expected_json)


def test_update_existing_folder(tmp_path):
    """Test when a file in the output folder already exists."""
    output_path = tmp_path / "roles"
    output_path.mkdir()
    first_file = output_path / "54 - Unreal Experimental" / "townsfolk" / "first.json"
    first_file.parent.mkdir(parents=True, exist_ok=True)
    with open(first_file, "w") as f:
        json.dump(expected_role_json.get("first.json"), f)

    _run_cmd(["--output", str(output_path)])

    # Verify that it worked
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.json"),
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.png"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.png"),
        str(Path("99 - Ignored") / "outsider" / "third.json"),
    ]
    check_output_folder(output_path, expected_files=expected_files, check_func=check_expected_json)


def test_update_bad_json(tmp_path, capsys):
    """Test when a file in the output folder exists, but isn't in the format we expect."""
    output_path = tmp_path / "roles"
    output_path.mkdir()
    first_file = output_path / "54 - Unreal Experimental" / "townsfolk" / "first.json"
    first_file.parent.mkdir(parents=True, exist_ok=True)
    with open(first_file, "w") as f:
        f.write("This is not json")
    _run_cmd(["--output", str(output_path)])

    # Verify that we got the files we expected
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.png"),
        str(Path("99 - Ignored") / "outsider" / "third.json"),
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
    _run_cmd(["--output", str(output_path), "--script-filter", "99 - Ignored"])

    # Verify that it worked
    expected_files = [
        str(Path("99 - Ignored") / "outsider" / "third.json"),
    ]
    check_output_folder(output_path, expected_files=expected_files)


def test_update_missing(tmp_path, capsys):
    """Test when the wiki doesn't return the expected data."""
    output_path = tmp_path / "roles"
    _run_cmd(["--output", str(output_path), "--script-filter", ""])

    # Check if we alerted to user to not being able to find the role info
    output = capsys.readouterr()
    assert "No ability found" in output.out
    assert "No icon found" in output.out
    assert "No reminder info found" in output.out


def test_update_icon_already_exists(tmp_path):
    """Test when the icon already exists."""
    output_path = tmp_path / "roles"
    output_path.mkdir()
    icon_path = output_path / "54 - Unreal Experimental" / "townsfolk" / "first.png"
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    icon_path.touch()
    _run_cmd(["--output", str(output_path)])

    # Verify that it worked
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.json"),
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.png"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.png"),
        str(Path("99 - Ignored") / "outsider" / "third.json"),
    ]
    check_output_folder(output_path, expected_files=expected_files)


def test_update_custom_reminders_file(tmp_path):
    """Test when the reminders file is specified."""
    reminders_file = tmp_path / "reminders.json"
    with open(reminders_file, "w") as f:
        json.dump({"First": ["Custom reminder"]}, f)
    output_path = tmp_path / "roles"
    _run_cmd(["--output", str(output_path), "--reminders", str(reminders_file)])

    # Verify that it worked
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.json"),
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.png"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.png"),
        str(Path("99 - Ignored") / "outsider" / "third.json"),
    ]
    check_output_folder(output_path, expected_files=expected_files)
    with open(output_path / "54 - Unreal Experimental" / "townsfolk" / "first.json", "r") as f:
        j = json.load(f)
    assert j["reminders"] == ["Custom reminder"]
    with open(output_path / "54 - Unreal Experimental" / "demon" / "second.json", "r") as f:
        j = json.load(f)
    assert j["reminders"] == ["SECOND REMINDER"]


def test_update_existing_icon_and_json(tmp_path):
    """Test when the icon and json file already exist."""
    output_path = tmp_path / "roles"
    output_path.mkdir()
    icon_path = output_path / "54 - Unreal Experimental" / "townsfolk" / "first.png"
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    icon_path.touch()
    json_path = output_path / "54 - Unreal Experimental" / "townsfolk" / "first.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as f:
        json.dump(expected_role_json.get("first.json"), f)
    _run_cmd(["--output", str(output_path), "--use-playtest"])

    # Verify that it worked
    expected_files = [
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.json"),
        str(Path("54 - Unreal Experimental") / "townsfolk" / "first.png"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.json"),
        str(Path("54 - Unreal Experimental") / "demon" / "second.png"),
        str(Path("99 - Ignored") / "outsider" / "third.json"),
        str(Path("99 - Ignored") / "outsider" / "third.png"),
    ]
    check_output_folder(output_path, expected_files=expected_files)


def test_web_error_getting_icon(tmp_path, capsys):
    """Alert the user if we fail to get the icon."""
    output_path = tmp_path / "roles"
    wiki = MagicMock()
    wiki.get_big_icon_url.return_value = "First.png"
    found_role = Role(id="first", name="First")
    with patch("botc_tokens.commands.update.urlopen") as urlopen_mock:
        image_read_mock = MagicMock()
        fp = StringIO()  # This is necessary to avoid an issue when deconstructing urllib.error.HTTPError
        image_read_mock.read.side_effect = HTTPError("First.png", 404, "Failed to get icon", "hdrs", fp)
        urlopen_mock.return_value.__enter__.return_value.read = image_read_mock
        urlopen_mock.return_value = image_read_mock
        update.get_role_icon(found_role, {}, output_path, wiki)
    output = capsys.readouterr()
    assert "Unable to download icon" in output.out


def test_invalid_reminder_file(tmp_path, capsys):
    """Alert the user if the reminders file doesn't match the schema."""
    reminders_file = tmp_path / "reminders.json"
    with open(reminders_file, "w") as f:
        f.write('{"Librarian": 2}')
    output_path = tmp_path / "roles"

    _run_cmd(["--output", str(output_path), "--reminders", str(reminders_file)])

    output = capsys.readouterr()
    assert "does not match the schema:" in output.out


def test_bloodstar_with_official(tmp_path, capsys):
    """Test a bloodstar json that uses multiple official roles."""
    custom_list = tmp_path / "custom.json"
    with open(custom_list, "w") as f:
        json.dump([
            "imp",
            "librarian",
            "virgin",
        ], f)

    output_path = tmp_path / "roles"
    _run_cmd(["--output", str(output_path), "--custom-list", str(custom_list)])

    check_output_folder(output_path, expected_files=[])

    output = capsys.readouterr()
    assert "does not have any data. Checking the official wiki" in output.out


def test_custom_list(tmp_path, capsys):
    """Test using a custom list instead of the wiki."""
    custom_list = tmp_path / "custom.json"
    with open(custom_list, "w") as f:
        json.dump([
            {"id": "_meta"},
            {
                "id": "First",
                "name": "First",
                "image": "First.png",
                "team": "townsfolk",
                "ability": "First Ability",
                "edition": "99 - Testing",
                "reminders": ["First Reminder"],
                "firstNight": 1,
                "otherNight": 0,
            },
            {
                "id": "Second",
                "name": "Second",
                "image": ["Second.png", "Second_evil.png"],
                "team": "townsfolk",
                "ability": "Second Ability",
                "edition": "99 - Testing",
                "remindersGlobal": ["SECOND REMINDER"],
                "firstNight": 0,
                "otherNight": 5,
            },
            {
                "id": "Third",
                "name": "Third",
                "image": ["Third.png", "Third_evil.png"],
                "team": "townsfolk",
                "ability": "Second Ability",
                "edition": "99 - Testing",
                "reminders": ["Third reminder"],
                "remindersGlobal": ["Fourth reminder"],
                "firstNight": 0,
                "otherNight": 5,
            },
            {"id": "bootlegger"},
        ], f)
    output_path = tmp_path / "roles"
    _run_cmd(["--output", str(output_path), "--custom-list", str(custom_list)])

    # Verify that it worked
    expected_files = [
        str(Path("99 - Testing") / "townsfolk" / "First.json"),
        str(Path("99 - Testing") / "townsfolk" / "First.png"),
        str(Path("99 - Testing") / "townsfolk" / "Second.json"),
        str(Path("99 - Testing") / "townsfolk" / "Second.png"),
        str(Path("99 - Testing") / "townsfolk" / "Third.json"),
        str(Path("99 - Testing") / "townsfolk" / "Third.png"),
    ]
    check_output_folder(output_path, expected_files=expected_files)

    # Verify the bootlegger skippage was show to the user
    output = capsys.readouterr()
    assert "because it has no name" in output.out


def test_nonexistent_custom_list(tmp_path, capsys):
    """Alert the user if the input doesn't exist."""
    output_path = tmp_path / "roles"
    _run_cmd(["--output", str(output_path), "--custom-list", str(tmp_path / "nope")])
    output = capsys.readouterr()
    assert "Could not find" in output.out


def test_bad_format_custom_list(tmp_path, capsys):
    """Alert the user if the custom list doesn't match the schema."""
    custom_list = tmp_path / "custom.json"
    with open(custom_list, "w") as f:
        f.write('{"Librarian": 2}')
    output_path = tmp_path / "roles"
    _run_cmd(["--output", str(output_path), "--custom-list", str(custom_list)])
    output = capsys.readouterr()
    assert "be warned that it might not work" in output.out


def test_forced_setup(tmp_path, capsys):
    """Roles are modified to affect setup if the show up in the force list."""
    output_path = tmp_path / "roles"
    _run_cmd(["--output", str(output_path), "--script-filter", "99 - Ignored"])

    # Verify that it worked
    with open(output_path / "99 - Ignored" / "outsider" / "Third.json", "r") as f:
        j = json.load(f)
    assert j["affects_setup"] is True


def test_use_playtest(tmp_path):
    """Use the playtest wiki instead of the main one."""
    output_path = tmp_path / "roles"
    _run_cmd(["--output", str(output_path), "--use-playtest"])
