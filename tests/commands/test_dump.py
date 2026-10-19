"""Test the dump command."""
# Standard Library
from unittest.mock import patch

# Third Party
import pytest
from testhelpers import check_output_folder

# Application Specific
from botc_tokens import component_path
from botc_tokens.commands import dump

COMPONENT_FILES = sorted(p.name for p in component_path.iterdir())


def _run_cmd(arg_list):
    argv_patch = ["botc_tokens", "dump"]
    argv_patch.extend(arg_list)

    with patch("sys.argv", argv_patch):
        return dump.run()


def test_dump_components(tmp_path):
    """Dumping components writes the component files directly into the output directory."""
    output = tmp_path / "output"
    assert _run_cmd(["components", str(output)]) == 0

    check_output_folder(output, COMPONENT_FILES)


def test_dump_duplicates(tmp_path):
    """Dumping duplicates writes duplicates.json."""
    output = tmp_path / "output"
    _run_cmd(["duplicates", str(output)])

    check_output_folder(output, ["duplicates.json"])


def test_dump_icon_lookup(tmp_path):
    """Dumping the icon lookup writes icon_lookup.json."""
    output = tmp_path / "output"
    _run_cmd(["icon-lookup", str(output)])

    check_output_folder(output, ["icon_lookup.json"])


def test_dump_all(tmp_path):
    """Dumping all writes both JSON files and a components subdirectory."""
    output = tmp_path / "output"
    _run_cmd(["all", str(output)])

    check_output_folder(output, ["duplicates.json", "icon_lookup.json"] + [f"components/{n}" for n in COMPONENT_FILES])


def test_dump_default_dir(tmp_path, monkeypatch):
    """Without an output directory, botc_tokens_defaults is created in the working directory."""
    monkeypatch.chdir(tmp_path)
    _run_cmd(["duplicates"])

    check_output_folder(tmp_path / "botc_tokens_defaults", ["duplicates.json"])


def test_dump_bad_choice(tmp_path):
    """An unknown 'what' is an argparse error."""
    with pytest.raises(SystemExit) as exc:
        _run_cmd(["bogus", str(tmp_path)])

    assert exc.value.code == 2
