"""General configuration for tests."""
from pathlib import Path

import pytest


@pytest.fixture
def example_path():
    """Return the path to the example directory."""
    return Path(__file__).parent / "example"
