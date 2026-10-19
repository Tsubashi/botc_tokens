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
    # Create the token components
    token_components = TokenComponents()

    # Dump the token components
    dump_path = tmp_path / "dump"
    token_components.dump(dump_path)
    return dump_path


@pytest.fixture()
def fake_web(monkeypatch):
    """Replace network access in the web helper with a FakeWeb."""
    from testhelpers import FakeWeb  # Imported late so assert rewriting applies

    web = FakeWeb()
    monkeypatch.setattr("botc_tokens.helpers.web.urlopen", web.urlopen)
    monkeypatch.setattr("botc_tokens.helpers.web.sleep", lambda seconds: None)
    return web
