"""Tests for the create command."""
# Standard Library
import json
from pathlib import Path
from shutil import copy
from unittest.mock import patch

# Third Party
import pytest
from testhelpers import check_output_folder
from wand.image import Image

# Application Specific
from botc_tokens.commands import create


@pytest.fixture()
def input_path(test_data_dir, tmp_path):
    """Create a temporary folder with some files in it."""
    input_folder = tmp_path / "input"
    input_folder.mkdir()

    # Create some files
    for i in range(1, 9):
        icon = input_folder / f"{i}.png"
        copy(test_data_dir / "icons" / f"{i}.png", icon)

        file = input_folder / f"{i}.json"
        fake_role = {
            "name": f"{i}",
            "ability": f"Ability {i}",
            "type": "Not-In-Play",
            "icon": f"{i}.png",
            "first_night": i % 2 == 0,
            "other_nights": i % 3 == 0,
            "reminders": [f"Reminder {i}"],
            "affects_setup": i % 4 == 0,
            "home_script": "999 - Tests"
        }
        file.write_text(json.dumps(fake_role))
    # Add a role with a space in the name
    file = input_folder / "Space Role.json"
    fake_role = {
        "name": "Space Role",
        "ability": "Ability 10",
        "type": "Not-In-Play",
        "icon": "1.png",
        "first_night": False,
        "other_nights": False,
        "reminders": ["This has spaces"],
        "affects_setup": False,
        "home_script": "999 - Tests"
    }
    file.write_text(json.dumps(fake_role))

    return input_folder


@pytest.fixture()
def default_expected_files():
    """Make a list of all the files we expect to be output by default."""
    expected_files = []
    for i in range(1, 9):
        expected_files.append(str(Path("999 - Tests") / "Not-In-Play" / f"{i}.png"))
        expected_files.append(str(Path("999 - Tests") / "Not-In-Play" / f"{i}-Reminder-Reminder_{i}.png"))
    # Add the space role
    expected_files.append(str(Path("999 - Tests") / "Not-In-Play" / "Space_Role.png"))
    expected_files.append(str(Path("999 - Tests") / "Not-In-Play" / "Space_Role-Reminder-This_has_spaces.png"))
    return expected_files


def _run_cmd(arg_list):
    argv_patch = ["botc_tokens", "create"]
    argv_patch.extend(arg_list)

    with patch("sys.argv", argv_patch):
        create.run()


def test_no_input(tmp_path, capsys):
    """Alert the user if the input folder doesn't exist."""
    _run_cmd([str(tmp_path)])

    output = capsys.readouterr()
    assert ("No JSON files found in the search directory" in output.out)


def test_standard_run(input_path, default_expected_files):
    """Run normally."""
    output_path = input_path.parent / "output"
    _run_cmd([str(input_path), "-o", str(output_path)])

    # Check that the output folder was created
    assert output_path.exists()

    # Check that the tokens were created
    check_output_folder(output_path, expected_files=default_expected_files)


def test_existing_token(input_path, default_expected_files):
    """Don't overwrite an existing token."""
    output_path = input_path.parent / "output"
    output_path.mkdir(parents=True, exist_ok=True)

    # Create a token
    token = output_path / "999 - Tests" / "Not-In-Play" / "1.png"
    token.parent.mkdir(parents=True, exist_ok=True)
    fake_token_content = "Not a real token, but good enough to fool the tool."
    with open(token, "w") as f:
        f.write(fake_token_content)

    _run_cmd([str(input_path), "-o", str(output_path)])

    # Check that the tokens were created, but no reminders were created for the existing role token
    reminder = str(Path("999 - Tests") / "Not-In-Play" / "1-Reminder-Reminder_1.png")
    default_expected_files.remove(reminder)
    check_output_folder(output_path, expected_files=default_expected_files)

    # Check that the existing token was not overwritten
    with open(token, "r") as f:
        assert f.read() == fake_token_content


def test_duplicate_reminder(input_path):
    """Increment the count if there are reminders with the same text."""
    output_path = input_path.parent / "output"
    output_path.mkdir(parents=True, exist_ok=True)

    # Add an existing reminder token image, without a corresponding role token image
    # This will cause the utility to believe that there are multiple of the same reminder
    reminder = output_path / "999 - Tests" / "Not-In-Play" / "1-Reminder-Reminder_1.png"
    reminder.parent.mkdir(parents=True, exist_ok=True)
    reminder.touch()

    _run_cmd([str(input_path), "-o", str(output_path)])
    assert (output_path / "999 - Tests" / "Not-In-Play" / "1-Reminder-Reminder_1-2.png").exists()


def test_componets_error_handling(input_path, capsys):
    """Alert the user if there is an error loading the components."""
    # Try a non-existent package
    output_path = input_path.parent / "output"
    _run_cmd([str(input_path), "-o", str(output_path), "--components", "not-a-real-file"])

    output = capsys.readouterr()
    assert "Unable to load components from" in output.out

    # Try a non-zip file
    non_zip = output_path / "not-a-zip.zip"
    non_zip.touch()
    _run_cmd([str(input_path), "-o", str(output_path), "--components", str(non_zip)])
    output = capsys.readouterr()
    assert "valid components package" in output.out

    # Simulate a package with bad files
    with patch("botc_tokens.commands.create.TokenComponents") as mock:
        mock.side_effect = create.BlobError("Bad file")
        _run_cmd([str(input_path), "-o", str(output_path)])
    output = capsys.readouterr()
    assert "Could not load component:" in output.out


def test_diameter_options(input_path, default_expected_files):
    """Test the reminder_diameter argument."""
    output_path = input_path.parent / "output"
    _run_cmd([str(input_path), "-o", str(output_path), "--reminder-diameter", "100", "--role-diameter", "200"])

    # Check that the tokens were created
    check_output_folder(output_path, expected_files=default_expected_files)

    # Check that the reminder tokens were created with the correct size
    for i in range(1, 9):
        token = output_path / "999 - Tests" / "Not-In-Play" / f"{i}.png"
        with Image(filename=token) as img:
            assert img.size == (200, 200)
        reminder = output_path / "999 - Tests" / "Not-In-Play" / f"{i}-Reminder-Reminder_{i}.png"
        with Image(filename=reminder) as img:
            assert img.size == (100, 100)
