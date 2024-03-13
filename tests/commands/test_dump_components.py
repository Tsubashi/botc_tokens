"""Dump everything!"""
# Standard Library
from unittest.mock import patch

# Third Party

# Application Specific
from botc_tokens.commands import dump_components


def _run_cmd(arg_list):
    argv_patch = ["botc_tokens", "dump-components"]
    argv_patch.extend(arg_list)

    with patch("sys.argv", argv_patch):
        dump_components.run()


def test_standard_run(tmp_path):
    """Test the command with nothing special."""
    output = tmp_path / "output"
    _run_cmd([str(output)])

    assert (output / "TokenBG.png").exists()


def test_bad_package(tmp_path, capsys):
    """Test the command with a bad package."""
    output = tmp_path / "output"
    with patch("botc_tokens.commands.dump_components.TokenComponents.dump") as mock:
        mock.side_effect = FileNotFoundError("Test Error")
        _run_cmd([str(output)])

    output = capsys.readouterr()
    assert ("missing a required component" in output.out)
