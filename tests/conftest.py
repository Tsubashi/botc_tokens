"""General configuration for tests."""
# Standard Library
from pathlib import Path

# Third Party
import pytest

# Application Specific
from botc_tokens.helpers.token_components import TokenComponents

# Let pytest know we would like them to handle asserts in our helper code
pytest.register_assert_rewrite("testhelpers")


@pytest.fixture()
def test_data_dir():
    """Set the data directory for the tests."""
    return Path(__file__).parent / "data"


@pytest.fixture()
def component_package(tmp_path):
    """Create a token component package."""
    """Test that the token components are dumped as expected."""
    # Create the token components
    token_components = TokenComponents()

    # Dump the token components
    dump_path = tmp_path / "dump"
    token_components.dump(dump_path)
    return dump_path
