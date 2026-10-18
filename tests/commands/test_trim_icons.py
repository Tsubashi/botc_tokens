"""Trim it all!"""
# Standard Library
from shutil import copy
from unittest.mock import patch

# Third Party
import pytest
from testhelpers import check_output_folder
from wand.image import Image

# Application Specific
from botc_tokens.commands import trim_icons


@pytest.fixture()
def input_path(test_data_dir, tmp_path):
    """Create a temporary folder with some files in it."""
    input_folder = tmp_path / "input"
    input_folder.mkdir()

    # Create some files
    icon_dir = test_data_dir / "icons"
    copy(icon_dir / "8.png", input_folder / "8.png")
    copy(icon_dir / "9.png", input_folder / "9.png")
    copy(icon_dir / "9.untrimmed.png", input_folder / "9.untrimmed.png")

    return input_folder


def _run_cmd(arg_list):
    argv_patch = ["botc_tokens", "trim-icons"]
    argv_patch.extend(arg_list)

    with patch("sys.argv", argv_patch):
        trim_icons.run()


def test_standard_run(input_path):
    """Test the command with nothing special."""
    _run_cmd([str(input_path)])

    expected_files = [
        "8.png",
        "9.png",
        "9.untrimmed.png",
        "9.untrimmed_trimmed.png"
    ]

    check_output_folder(input_path, expected_files)

    with Image(filename=input_path / "9.untrimmed_trimmed.png") as trimmed:
        assert trimmed.size == (42, 63)


def test_in_place(input_path):
    """Test the command with the in-place option."""
    _run_cmd(["--in-place", str(input_path)])

    expected_files = [
        "8.png",
        "9.png",
        "9.untrimmed.png"
    ]

    check_output_folder(input_path, expected_files)

    with Image(filename=input_path / "9.untrimmed.png") as trimmed:
        assert trimmed.size == (42, 63)


def test_no_files(tmp_path, capsys):
    """Test the command with no files."""
    _run_cmd([str(tmp_path)])

    check_output_folder(tmp_path, [])

    captured = capsys.readouterr()
    assert "No icons found." in captured.out


def test_not_a_directory(tmp_path, capsys):
    """Test the command with a file instead of a directory."""
    target_dir = tmp_path / "not-a-dir"
    _run_cmd([str(target_dir)])

    check_output_folder(target_dir, [])

    captured = capsys.readouterr()
    out_text = " ".join(str(captured.out).split())  # Collapse whitespace in case the long path caused wrapping
    assert "is not a directory." in out_text
