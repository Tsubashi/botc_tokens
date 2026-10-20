"""Tests for the config file helper."""
# Standard Library
import argparse
from pathlib import Path
import sys

# Third Party
import pytest

# Application Specific
from botc_tokens.helpers import config
from botc_tokens.helpers.config import COMMAND_SECTIONS, config_file_paths, CONFIG_FILENAME, config_path, \
    ConfigError, find_local_config, global_config_path, load_config_values, local_start_dir


def _parser():
    """Build a parser exercising every kind of option the config layer must handle."""
    p = argparse.ArgumentParser(prog="x")
    p.add_argument("--name", type=str, default="builtin")
    p.add_argument("--plain", default=None)
    p.add_argument("-c", "--count", type=int, default=1)
    p.add_argument("-q", action="store_true", dest="quiet")
    p.add_argument("--flag", action="store_true")
    p.add_argument("--where", type=config_path, default=None)
    p.add_argument("--many", nargs="+", type=int, default=None)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--size", nargs=2, type=float, default=None)
    group.add_argument("--kind", type=str, choices=["a", "b"], default=None)
    p.add_argument("pos", nargs="?")
    return p


def _conf(tmp_path, text, name=CONFIG_FILENAME):
    """Write a config file and return its path."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_global_path_uses_xdg_config_home(monkeypatch, tmp_path):
    """XDG_CONFIG_HOME relocates the global config directory."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert global_config_path() == tmp_path / "xdg" / "botc_tokens" / CONFIG_FILENAME


def test_global_path_defaults_to_dot_config(monkeypatch, tmp_path):
    """Without XDG_CONFIG_HOME the global config lives under ~/.config."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert global_config_path() == tmp_path / ".config" / "botc_tokens" / CONFIG_FILENAME


def test_global_path_on_windows_uses_appdata(monkeypatch, tmp_path):
    """Windows keeps the global config under APPDATA."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert global_config_path() == tmp_path / "Roaming" / "botc_tokens" / CONFIG_FILENAME


def test_global_path_on_windows_without_appdata_falls_back(monkeypatch, tmp_path):
    """Windows without APPDATA falls back to ~/.config rather than failing."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert global_config_path() == tmp_path / ".config" / "botc_tokens" / CONFIG_FILENAME


def test_local_start_dir_is_cwd():
    """The local search starts from the current working directory (the real function, bound before patching)."""
    assert local_start_dir() == Path.cwd()


def test_find_local_config_prefers_nearest(tmp_path):
    """Only the nearest config file up the tree is used."""
    (tmp_path / CONFIG_FILENAME).write_text("")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (tmp_path / "a" / CONFIG_FILENAME).write_text("")
    assert find_local_config(nested) == tmp_path / "a" / CONFIG_FILENAME


def test_find_local_config_returns_none_when_absent(tmp_path):
    """No config file anywhere up the tree gives None."""
    assert find_local_config(tmp_path / "nowhere") is None


def test_config_file_paths_lists_existing_in_order(isolated_config):
    """Existing files are listed global first, then local."""
    isolated_config.global_path.parent.mkdir(parents=True)
    isolated_config.global_path.write_text("")
    local = isolated_config.cwd / CONFIG_FILENAME
    local.write_text("")
    assert config_file_paths() == [isolated_config.global_path, local]


def test_config_file_paths_skips_missing(isolated_config):
    """Missing files are silently left out."""
    assert config_file_paths() == []


def test_config_file_paths_dedupes_same_file(isolated_config, monkeypatch):
    """When the local search finds the global file, it is listed once."""
    isolated_config.global_path.parent.mkdir(parents=True)
    isolated_config.global_path.write_text("")
    monkeypatch.setattr(config, "local_start_dir", lambda: isolated_config.global_path.parent)
    assert config_file_paths() == [isolated_config.global_path]


def test_command_sections_match_commands():
    """The valid section names are exactly the commands that take arguments."""
    assert COMMAND_SECTIONS == frozenset({"create", "dump", "migrate", "pad-icons"})


def test_config_path_returns_text_unchanged():
    """On the command line the path type is a plain string."""
    assert config_path("rel/dir") == "rel/dir"


def test_load_scalar_flag_multi_and_group_values(tmp_path):
    """Every kind of option converts through its own type."""
    path = _conf(tmp_path, "[create]\nname = fred\nplain = as is\ncount = 7\nflag = Yes\nmany = 1 2 3\n"
                           "size = 10 20.5\n")
    assert load_config_values(path, "create", _parser()) == {
        "name": "fred", "plain": "as is", "count": 7, "flag": True, "many": [1, 2, 3], "size": [10.0, 20.5]}


@pytest.mark.parametrize("word, value", [("true", True), ("off", False), ("1", True), ("NO", False)])
def test_boolean_words(tmp_path, word, value):
    """Flags accept the usual boolean words in any case."""
    path = _conf(tmp_path, f"[create]\nflag = {word}\n")
    assert load_config_values(path, "create", _parser()) == {"flag": value}


def test_missing_section_gives_empty(tmp_path):
    """A file without the command's section contributes nothing."""
    path = _conf(tmp_path, "[migrate]\ninput = x\n")
    assert load_config_values(path, "create", _parser()) == {}


def test_path_rebases_relative_to_file_and_expands_home(tmp_path, monkeypatch):
    """Path options resolve against the config file's directory, after ~ expansion; absolute paths stay."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))  # Path.expanduser reads HOME, not Path.home
    path = _conf(tmp_path, "[create]\nwhere = cache\n")
    assert load_config_values(path, "create", _parser()) == {"where": str(tmp_path / "cache")}
    path = _conf(tmp_path, "[create]\nwhere = ~/c\n")
    assert load_config_values(path, "create", _parser()) == {"where": str(tmp_path / "home" / "c")}
    path = _conf(tmp_path, f"[create]\nwhere = {tmp_path / 'abs'}\n")
    assert load_config_values(path, "create", _parser()) == {"where": str(tmp_path / "abs")}


@pytest.mark.parametrize("text, expected", [
    ("[Create]\nname = x\n", "[Create]: unknown section"),
    ("[DEFAULT]\nname = x\n[create]\n", "[DEFAULT]: unknown section"),
    ("[create]\nnope = 1\n", "[create] nope: unknown option"),
    ("[create]\nq = true\n", "[create] q: unknown option"),
    ("[create]\nquiet = true\n", "[create] quiet: unknown option"),
    ("[create]\ncount =\n", "[create] count: empty value"),
    ("[create]\nflag = maybe\n", "[create] flag: 'maybe' is not a boolean"),
    ("[create]\ncount = x\n", "[create] count: 'x' is not a valid int"),
    ("[create]\nsize = 1\n", "[create] size: expected 2 values, got 1"),
    ("[create]\nkind = z\n", "[create] kind: invalid choice: 'z' (choose from a, b)"),
    ("[create]\nsize = 1 2\nkind = a\n", "[create]: --size and --kind cannot both be set"),
    ("[create]\ncount = 1\ncount = 2\n", "option 'count' in section 'create' already exists"),
    ("not an ini\n", "File contains no section headers"),
])
def test_value_and_file_errors(tmp_path, text, expected):
    """Every malformed file or value names the file and what is wrong."""
    path = _conf(tmp_path, text)
    with pytest.raises(ConfigError) as e:
        load_config_values(path, "create", _parser())
    assert str(e.value).startswith(str(path))
    assert expected in str(e.value)


def test_argument_type_error_is_reported(tmp_path):
    """A type callable's ArgumentTypeError message is passed through."""
    def positive(text):
        raise argparse.ArgumentTypeError(f"'{text}' must be greater than zero")
    p = argparse.ArgumentParser(prog="x")
    p.add_argument("--dpi", type=positive)
    path = _conf(tmp_path, "[create]\ndpi = 0\n")
    with pytest.raises(ConfigError, match="dpi: '0' must be greater than zero"):
        load_config_values(path, "create", p)


def test_unreadable_file_is_error(tmp_path):
    """A config path that cannot be read as a file is a config error, not a traceback."""
    path = tmp_path / CONFIG_FILENAME
    path.mkdir()
    with pytest.raises(ConfigError) as e:
        load_config_values(path, "create", _parser())
    assert str(e.value).startswith(str(path))


def test_non_utf8_file_is_error(tmp_path):
    """A config file that is not UTF-8 is a config error."""
    path = tmp_path / CONFIG_FILENAME
    path.write_bytes(b"[create]\nname = \xff\n")
    with pytest.raises(ConfigError, match="codec"):
        load_config_values(path, "create", _parser())
