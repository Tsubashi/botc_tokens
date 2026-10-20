"""Various helper utilities for testing."""
from contextlib import contextmanager
import io
from urllib.error import HTTPError

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


class FakeWeb:
    """A fake network layer that serves canned responses for urlopen."""

    def __init__(self):
        """Create an empty set of routes."""
        self.routes: dict[str, bytes | Exception] = {}
        self.calls: list[str] = []

    def urlopen(self, request, *args, **kwargs):
        """Stand in for urllib.request.urlopen, serving from the configured routes."""
        url = request.full_url
        self.calls.append(url)
        result = self.routes.get(url)
        if isinstance(result, Exception):
            raise result
        if result is None:
            raise HTTPError(url, 404, "Not Found", {}, None)
        return io.BytesIO(result)
