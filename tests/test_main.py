"""Test the command interface."""
from unittest.mock import patch

import testhelpers

from botc_tokens.__main__ import allowed_commands, main as botc_tokens_main


def _run_main_cmd(arg_list, expected_exit=0):
    argv_patch = ["botc_tokens"]
    argv_patch.extend(arg_list)

    with patch("sys.argv", argv_patch):
        with testhelpers.expect_exit(expected_exit):
            botc_tokens_main()


def test_print_version(capsys):
    """Show the order the files would be bound in, if asked."""
    _run_main_cmd(["version"])

    output = capsys.readouterr()
    expected_output = "botc_tokens, Version"  # Skip the details, so it will match any version
    assert expected_output in output.out


def test_unrecognized_command(capsys):
    """Throw an error on an unrecognized sub-command."""
    _run_main_cmd(["definitely-not-a-real-command"], -1)

    output = capsys.readouterr()
    expected_output = "Unrecognized command"
    assert expected_output in output.out


def test_all_commands_help(capsys):
    """Display help menu from all commands."""
    for command in allowed_commands:
        _run_main_cmd([command, "--help"])
