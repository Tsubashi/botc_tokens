"""Read option defaults for the commands from botc_tokens.conf files.

Defaults come from a global file, then a local file, and real command line arguments beat both.
"""
# Standard Library
import os
from pathlib import Path
import sys

CONFIG_FILENAME = "botc_tokens.conf"
APP_DIR_NAME = "botc_tokens"


def global_config_path() -> Path:
    """Return where the global config file lives on this platform, whether or not it exists."""
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"])
    elif os.environ.get("XDG_CONFIG_HOME"):
        base = Path(os.environ["XDG_CONFIG_HOME"])
    else:
        base = Path.home() / ".config"
    return base / APP_DIR_NAME / CONFIG_FILENAME


def local_start_dir() -> Path:
    """Return the directory the local config search starts from. Exists so tests can redirect it."""
    return Path.cwd()


def find_local_config(start: Path) -> Path | None:
    """Return the nearest config file in `start` or any of its parents, or None if there is none."""
    for directory in (start, *start.parents):
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def config_file_paths() -> list[Path]:
    """Return the existing config files to load, global first then local, listing a shared file once."""
    paths = []
    seen = set()
    local = find_local_config(local_start_dir())
    for candidate in (global_config_path(), local):
        if candidate is None or not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            paths.append(candidate.absolute())
    return paths
