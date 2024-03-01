import pytest
from pathlib import Path


@pytest.fixture
def example_path():
    return Path(__file__).parent / "example"
