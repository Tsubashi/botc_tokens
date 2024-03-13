"""Tests for the group command."""
# Standard Library
import json
from shutil import copy
from unittest.mock import patch

# Third Party`
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
        group.run()


def test_group(example_script, token_dir, tmp_path):
    """Run normally."""
    output_path = tmp_path / "output"
    _run_cmd([str(example_script), "--token-dir", str(token_dir), "-o", str(output_path)])

    expected_files = ["roles_1.pdf", "reminders_1.pdf"]
    check_output_folder(output_path, expected_files=expected_files)


@pytest.mark.skip("Disabled because delagate is not installed on GH Actions runner.")
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

    with Image(filename=(output_path / "roles_1.pdf")) as img:
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
        "--fixed-role-size", "128"
    ])

    expected_files = ["roles_1.pdf", "roles_2.pdf", "reminders_1.pdf", "reminders_2.pdf"]
    check_output_folder(output_path, expected_files=expected_files)


def test_script_directory(token_dir, tmp_path):
    """Use a directory as a script."""
    output_path = tmp_path / "output"
    _run_cmd([str(token_dir), "--token-dir", str(token_dir), "-o", str(output_path)])

    expected_files = ["roles_1.pdf", "reminders_1.pdf"]
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

    expected_files = ["roles_1.pdf", "reminders_1.pdf"]
    check_output_folder(output_path, expected_files=expected_files)
