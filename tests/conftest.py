"""General configuration for tests."""
# Standard Library
from pathlib import Path
from types import SimpleNamespace

# Third Party
import pytest

# Application Specific
from botc_tokens.helpers import config as config_helper
from botc_tokens.helpers.token_components import TokenComponents

# Let pytest know we would like them to handle asserts in our helper code
pytest.register_assert_rewrite("testhelpers")


@pytest.fixture(autouse=True)
def wide_console(monkeypatch):
    """Keep rich from word-wrapping captured output at the 80-column non-TTY default.

    Where the wrap lands depends on the length of tmp_path, which differs between CI and
    local machines, so substring assertions on multi-word messages would otherwise be flaky.
    """
    monkeypatch.setenv("COLUMNS", "500")


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path_factory):
    """Point the config helper at empty temp locations so no real botc_tokens.conf leaks into a test.

    Returns the (nonexistent) global config path and the directory the local search starts from, so tests that
    want config files can write them there. Uses its own temp directory rather than tmp_path so tests that assert
    on the exact contents of tmp_path are unaffected.
    """
    root = tmp_path_factory.mktemp("config")
    cwd = root / "cwd"
    cwd.mkdir()
    global_path = root / "global" / config_helper.CONFIG_FILENAME
    monkeypatch.setattr(config_helper, "global_config_path", lambda: global_path)
    monkeypatch.setattr(config_helper, "local_start_dir", lambda: cwd)
    return SimpleNamespace(global_path=global_path, cwd=cwd)


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
