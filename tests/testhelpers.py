"""Various helper utilities for testing."""
from contextlib import contextmanager

import pytest


def check_output_folder(output_path, expected_files, check_func=None):
    """Check that expected output exists.

    :param output_path: Path to the directory to check.
    :param expected_files: Files we expect to find in output_path.
    :param check_func: Function for checking each file in expected_files. Defaults to checking that the file exists.

    """
    # Default check function, in case one isn't passed in.
    def default_check(input_file_path):
        """Ensure each file exists and is a file."""
        assert input_file_path.is_file()

    # Set defaults
    if not check_func:
        check_func = default_check

    # Check the output
    for file_name in expected_files:
        file_path = output_path / file_name
        check_func(file_path)

    # Make sure there aren't any extra files in the directory
    for file in output_path.rglob("*"):
        if file.is_dir():
            continue
        assert (str(file.relative_to(output_path)) in expected_files)


@contextmanager
def expect_exit(expected_code=1):
    """Ensure a function exits, and writes an expected string to stdout or stderr."""
    with pytest.raises(SystemExit) as e:
        yield
    assert e.value.code == expected_code


@contextmanager
def expect_exit_with_output(capsys, expected_text, expected_code=1):
    """Ensure a function exits, and writes an expected string to stdout or stderr."""
    with expect_exit(expected_code):
        yield
    output = capsys.readouterr()
    assert (expected_text in output.out) or (expected_text in output.err)


webmock_list = [
    # The first call is for the role data
    b"""[
         {
            "id": "First",
            "name": "First",
            "roleType": "townsfolk",
            "print": "unused",
            "icon": "unused",
            "version": "54 - Unreal Experimental",
            "isDisabled": false
          },
          {
            "id": "Second",
            "name": "Second",
            "roleType": "demon",
            "print": "unused",
            "icon": "unused",
            "version": "54 - Unreal Experimental",
            "isDisabled": false
          },
          {
            "id": "Third",
            "name": "Third",
            "roleType": "outsider",
            "print": "unused",
            "icon": "unused",
            "version": "99 - Ignored",
            "isDisabled": false
          }
        ]""",
    # The second call is for the night data
    b"""{
          "firstNight": [
            "DUSK",
            "First"
          ],
          "otherNight": [
            "DUSK",
            "First",
            "Second"
          ]
        }""",
    # The third call is for the first role's wiki page
    b"""<html>
          <body>
            <div><h2 id="Summary">First ability</h2></div>
            <p>First ability description</p>
            <div><h2 id="How_to_Run">How To Run</h2></div>
            <p><b>not a reminder</b></p>
            <div id="character-details"><img src="First.png" /></div>
          </body>
        </html>""",
    # The fourth call is for the second role's wiki page
    b"""<html>
          <body>
            <div><h2 id="Summary">Second ability</h2></div>
            <p>Second ability description [Affects Setup]</p>
            <div><h2 id="How_to_Run">How To Run</h2></div>
            <p><b>YOU ARE</b></p>
            <p><b>SECOND REMINDER</b></p>
            <div id="character-details"><img src="Second.png" /></div>
          </body>
        </html>""",
    # The fifth call is for the third role's wiki page, which we will show as blank
    b"""<html>
          <body>
          </body>
        </html>""",
]


expected_role_json = {
    "First.json": {
        'ability': 'First ability description',
        'affects_setup': False,
        'first_night': True,
        'home_script': '54 - Unreal Experimental',
        'icon': 'First.png',
        'name': 'First',
        'other_nights': True,
        'reminders': [],
        'type': 'townsfolk'
    },
    "Second.json": {
        'ability': 'Second ability description [Affects Setup]',
        'affects_setup': True,
        'first_night': False,
        'home_script': '54 - Unreal Experimental',
        'icon': 'Second.png',
        'name': 'Second',
        'other_nights': True,
        'reminders': ["SECOND REMINDER"],
        'type': 'demon'
    }
}
