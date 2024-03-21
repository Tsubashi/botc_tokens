"""Tests for the group command."""
# Standard Library
import json
import os
from shutil import copy
from unittest.mock import patch

# Third Party`
from pypdf import PdfReader
import pytest
from testhelpers import check_output_folder
from wand.image import Image

# Application Specific
from botc_tokens.commands import group


@pytest.fixture()
def example_script(tmp_path):
    """Write a simple script json."""
    script = tmp_path / "example_script.json"
    script_data = [{"id": "_meta"}, "1", "2", "3"]
    script.write_text(json.dumps(script_data))
    return script


@pytest.fixture()
def token_dir(tmp_path, test_data_dir):
    """Create a directory with some token images in it."""
    token_folder = tmp_path / "tokens"
    token_folder.mkdir()

    # Create some files
    for i in range(1, 9):
        token = token_folder / f"{i}.png"
        copy(test_data_dir / "icons" / f"{i}.png", token)
        reminder = token_folder / f"{i}-Reminder-Reminder_{i}.png"
        copy(test_data_dir / "icons" / f"{i}.png", reminder)

    return token_folder


def _run_cmd(arg_list):
    argv_patch = ["botc_tokens", "group"]
    argv_patch.extend(arg_list)

    with patch("sys.argv", argv_patch):
        return group.run()


def test_group(example_script, token_dir, tmp_path):
    """Run normally."""
    output_path = tmp_path / "output"
    _run_cmd([str(example_script), "--token-dir", str(token_dir), "-o", str(output_path)])

    expected_files = ["roles.pdf", "reminders.pdf"]
    check_output_folder(output_path, expected_files=expected_files)


@pytest.mark.skipif(os.getenv("GITHUB_ACTIONS") == "true", reason="Required delegate is not installed in GH Actions.")
def test_paper_sizes(example_script, token_dir, tmp_path):
    """Adjust the paper size."""
    output_path = tmp_path / "output"
    _run_cmd([
        str(example_script),
        "--token-dir", str(token_dir),
        "-o", str(output_path),
        "--paper-width", "256",
        "--paper-height", "512"
    ])

    with Image(filename=(output_path / "roles.pdf")) as img:
        assert img.size == (256, 512)


def test_missing_token_dir(example_script, tmp_path, capsys):
    """Alert the user if the token folder doesn't exist."""
    output_path = tmp_path / "output"
    _run_cmd([str(example_script), "--token-dir", "not-a-dir", "-o", str(output_path)])

    output = capsys.readouterr()
    assert "No token images found" in output.out


def test_missing_tokens(example_script, tmp_path, capsys):
    """Alert the user if the token folder is empty."""
    token_folder = tmp_path / "tokens"
    token_folder.mkdir()
    output_path = tmp_path / "output"
    _run_cmd([str(example_script), "--token-dir", str(token_folder), "-o", str(output_path)])

    output = capsys.readouterr()
    assert "No token found for" in output.out


def test_page_overflow(example_script, token_dir, tmp_path):
    """Test that the page overflow works."""
    output_path = tmp_path / "output"
    _run_cmd([
        str(example_script),
        "--token-dir", str(token_dir),
        "-o", str(output_path),
        "--paper-width", "256",
        "--paper-height", "128",
        "--padding", "0",
        "--fixed-role-size", "128",
        "--fixed-reminder-size", "256"
    ])

    role_reader = PdfReader(output_path / "roles.pdf")
    assert len(role_reader.pages) == 2

    reminder_reader = PdfReader(output_path / "reminders.pdf")
    assert len(reminder_reader.pages) == 3


def test_script_directory(token_dir, tmp_path):
    """Use a directory as a script."""
    output_path = tmp_path / "output"
    _run_cmd([str(token_dir), "--token-dir", str(token_dir), "-o", str(output_path)])

    expected_files = ["roles.pdf", "reminders.pdf"]
    check_output_folder(output_path, expected_files=expected_files)


def test_multi_row(example_script, token_dir, tmp_path):
    """Test that the page overflow works."""
    output_path = tmp_path / "output"
    _run_cmd([
        str(example_script),
        "--token-dir", str(token_dir),
        "-o", str(output_path),
        "--paper-width", "256",
        "--paper-height", "256",
        "--padding", "0",
        "--fixed-role-size", "128"
    ])

    expected_files = ["roles.pdf", "reminders.pdf"]
    check_output_folder(output_path, expected_files=expected_files)


def test_no_input(tmp_path, capsys):
    """Alert the user if the input doesn't exist."""
    assert _run_cmd([str(tmp_path / "Not-a-real-file.json")]) == 1
    output = capsys.readouterr()
    assert ("Unable to load script" in output.out)


def test_script_dir(token_dir, tmp_path):
    """Use a directory for the script argument."""
    output_path = tmp_path / "output"
    _run_cmd([str(token_dir), "-o", str(output_path)])

    expected_files = ["roles.pdf", "reminders.pdf"]
    check_output_folder(output_path, expected_files=expected_files)


def test_reminders_with_spaces(token_dir, tmp_path, test_data_dir):
    """Test for issue #5."""
    output_path = tmp_path / "output"
    icon = test_data_dir / "icons" / "1.png"
    copy(icon, token_dir / "role_with_spaces.png")
    copy(icon, token_dir / "role_with_spaces-Reminder-This_has_spaces.png")
    with patch("botc_tokens.commands.group.Printable") as printable_mock:
        _run_cmd([str(token_dir), "-o", str(output_path)])
        printable_mock().add_token.assert_any_call(token_dir / "role_with_spaces.png")
        printable_mock().add_token.assert_any_call(token_dir / "role_with_spaces-Reminder-This_has_spaces.png")


def test_roles_with_same_start(token_dir, tmp_path, test_data_dir):
    """Group roles that begin the same way correctly."""
    output_path = tmp_path / "output"
    icon = test_data_dir / "icons" / "1.png"
    copy(icon, token_dir / "12.png")
    with patch("botc_tokens.commands.group.Printable") as printable_mock:
        _run_cmd([str(token_dir), "-o", str(output_path)])
        printable_mock().add_token.assert_any_call(token_dir / "1.png")


def test_known_duplicates_file(token_dir, tmp_path, test_data_dir):
    """Use a duplicates file."""
    output_path = tmp_path / "printables"
    icon = test_data_dir / "icons" / "1.png"
    copy(icon, token_dir / "Legion.png")
    _run_cmd([
        str(token_dir),
        "-o", str(output_path),
        "--paper-width", "256",
        "--paper-height", "256",
        "--padding", "0",
        "--fixed-role-size", "128"
    ])
    with open(output_path / "roles.pdf", "rb") as f:
        reader = PdfReader(f)
        assert len(reader.pages) == 7


def test_valid_duplicates_file(token_dir, tmp_path):
    """Use a duplicates file."""
    duplicates_file = tmp_path / "duplicates.json"
    with open(duplicates_file, "w") as f:
        f.write('{"1": 3}')
    output_path = tmp_path / "printables"
    _run_cmd([
        str(token_dir),
        "-o", str(output_path),
        "--paper-width", "256",
        "--paper-height", "256",
        "--padding", "0",
        "--fixed-role-size", "128",
        "--duplicates", str(duplicates_file)
    ])
    with open(output_path / "roles.pdf", "rb") as f:
        reader = PdfReader(f)
        assert len(reader.pages) == 4


def test_invalid_duplicates_file(token_dir, tmp_path, capsys):
    """Alert the user if the duplicates file doesn't match the schema."""
    duplicates_file = tmp_path / "duplicates.json"
    with open(duplicates_file, "w") as f:
        f.write('{"Librarian": ["REMINDER"]}')
    output_path = tmp_path / "printables"
    _run_cmd([str(token_dir), "-o", str(output_path), "--duplicates", str(duplicates_file)])
    output = capsys.readouterr()
    assert "does not match the schema:" in output.out
