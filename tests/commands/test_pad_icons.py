"""Tests for the pad-icons command."""
# Standard Library
import shutil
from unittest.mock import patch

# Third Party
import pytest
from wand.color import Color
from wand.image import Image

# Application Specific
from botc_tokens.commands import pad_icons


def _run_cmd(arg_list):
    argv_patch = ["botc_tokens", "pad-icons"]
    argv_patch.extend(arg_list)

    with patch("sys.argv", argv_patch):
        return pad_icons.run()


@pytest.fixture
def input_dir(tmp_path, test_data_dir):
    """A directory holding a tight png, a tight webp, and an already padded png."""
    target = tmp_path / "icons"
    target.mkdir()
    shutil.copy(test_data_dir / "icons" / "1.png", target / "one.png")
    shutil.copy(test_data_dir / "icons" / "tight.webp", target / "tight.webp")
    shutil.copy(test_data_dir / "icons" / "padded.png", target / "padded.png")
    return target


def test_pads_to_sibling_file(input_dir):
    """Tight icons get a padded sibling file; originals and padded icons are untouched."""
    original = (input_dir / "one.png").read_bytes()
    assert _run_cmd([str(input_dir)]) == 0

    assert (input_dir / "one_padded.png").exists()
    assert (input_dir / "one.png").read_bytes() == original
    assert not (input_dir / "padded_padded.png").exists()


def test_in_place(input_dir):
    """The in-place flag rewrites the tight files without creating siblings."""
    original = (input_dir / "one.png").read_bytes()
    assert _run_cmd(["-i", str(input_dir)]) == 0

    assert (input_dir / "one.png").read_bytes() != original
    with Image(filename=str(input_dir / "one.png")) as image:
        assert image.width == image.height
    assert not list(input_dir.glob("*_padded*"))


def test_webp_kept_as_webp(input_dir):
    """A padded webp is written as webp."""
    assert _run_cmd([str(input_dir)]) == 0

    assert (input_dir / "tight_padded.webp").read_bytes().startswith(b"RIFF")


def test_fully_transparent_warns(input_dir, capsys):
    """A fully transparent icon produces a warning naming it and no output file."""
    with Image(width=20, height=20, background=Color("transparent")) as blank:
        blank.save(filename=str(input_dir / "blank.png"))

    assert _run_cmd([str(input_dir)]) == 0

    out = capsys.readouterr().out.replace("\n", "")
    assert "Warning" in out
    assert "blank.png" in out
    assert not (input_dir / "blank_padded.png").exists()


def test_corrupt_icon_warns_and_continues(input_dir, capsys):
    """An unreadable icon is warned about by name and the icons after it are still padded."""
    (input_dir / "[bold]corrupt.png").write_bytes(b"this is not a png")
    assert sorted(p.name for p in input_dir.iterdir())[0] == "[bold]corrupt.png"

    assert _run_cmd([str(input_dir)]) == 0

    out = capsys.readouterr().out.replace("\n", "")
    assert "Warning" in out
    assert "[bold]corrupt.png" in out
    assert (input_dir / "one_padded.png").exists()
    assert (input_dir / "tight_padded.webp").exists()


def test_no_icons(tmp_path, capsys):
    """An empty directory is an error."""
    assert _run_cmd([str(tmp_path)]) == 1
    assert "No icons found" in capsys.readouterr().out.replace("\n", "")


def test_not_a_directory(tmp_path, capsys):
    """A path that is not a directory is an error."""
    assert _run_cmd([str(tmp_path / "missing")]) == 1
    assert "Error" in capsys.readouterr().out
