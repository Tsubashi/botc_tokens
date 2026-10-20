"""Tests for the config file helper."""
# Standard Library
from pathlib import Path
import sys

# Application Specific
from botc_tokens.helpers import config
from botc_tokens.helpers.config import config_file_paths, CONFIG_FILENAME, find_local_config, global_config_path, \
    local_start_dir


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
