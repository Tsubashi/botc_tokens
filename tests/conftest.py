"""General configuration for tests."""
from pathlib import Path

import pytest

# Let pytest know we would like them to handle asserts in our helper code
pytest.register_assert_rewrite("testhelpers")


@pytest.fixture
def example_path():
    """Return the path to the example directory."""
    return Path(__file__).parent / "example"
