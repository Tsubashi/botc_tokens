"""Read option defaults for the commands from botc_tokens.conf files.

Defaults come from a global file, then a local file, and real command line arguments beat both.
"""
# Standard Library
import argparse
import configparser
import os
from pathlib import Path
import sys

CONFIG_FILENAME = "botc_tokens.conf"
APP_DIR_NAME = "botc_tokens"
COMMAND_SECTIONS: frozenset[str] = frozenset({"create", "dump", "migrate", "pad-icons"})

TRUE_WORDS = frozenset({"true", "yes", "on", "1"})
FALSE_WORDS = frozenset({"false", "no", "off", "0"})


class ConfigError(Exception):
    """A config file could not be read or holds something invalid. str() is the full user-facing message."""


def config_path(text: str) -> str:
    """Mark an option as path-valued. On the command line it is a plain string; from a config file it is rebased."""
    return text


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


def _read_ini(path: Path) -> configparser.ConfigParser:
    """Read a config file, turning read and parse failures into ConfigErrors."""
    # The default section is given a name no file will use, so a real [DEFAULT] is an ordinary (unknown) section
    # instead of leaking its keys into every other section.
    ini = configparser.ConfigParser(interpolation=None, default_section="\0")
    try:
        ini.read_string(path.read_text(encoding="utf-8"), source=str(path))
    except (OSError, UnicodeDecodeError, configparser.Error) as e:
        raise ConfigError(f"{path}: {e}") from None
    return ini


def _option_actions(parser: argparse.ArgumentParser) -> dict[str, argparse.Action]:
    """Map each configurable key (long option name without the dashes) to its action."""
    actions = {}
    for action in parser._actions:
        if action.dest == "help":
            continue
        for option in action.option_strings:
            if option.startswith("--"):
                actions[option[2:]] = action
                break
    return actions


def _convert_bool(raw: str) -> bool:
    """Convert a boolean word."""
    word = raw.lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise ConfigError(f"'{raw}' is not a boolean (use true or false)")


def _convert_one(action: argparse.Action, raw: str, config_dir: Path):
    """Convert a single value through the action's type, rebasing config paths onto the file's directory."""
    if action.type is config_path:
        value = Path(raw).expanduser()
        return str(value if value.is_absolute() else config_dir / value)
    if action.type is None:
        return raw
    try:
        return action.type(raw)
    except argparse.ArgumentTypeError as e:
        raise ConfigError(str(e)) from None
    except ValueError:
        name = getattr(action.type, "__name__", repr(action.type))
        raise ConfigError(f"'{raw}' is not a valid {name}") from None


def _convert_value(action: argparse.Action, raw: str, config_dir: Path):
    """Convert a config value the way argparse would convert the same text on the command line."""
    if not raw.strip():
        raise ConfigError("empty value (give a value or remove the key)")
    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        return _convert_bool(raw.strip())
    if action.nargs is None or action.nargs == "?":
        value = _convert_one(action, raw.strip(), config_dir)
        values = [value]
    else:
        pieces = raw.split()
        if isinstance(action.nargs, int) and len(pieces) != action.nargs:
            raise ConfigError(f"expected {action.nargs} values, got {len(pieces)}")
        value = values = [_convert_one(action, piece, config_dir) for piece in pieces]
    if action.choices is not None:
        for item in values:
            if item not in action.choices:
                raise ConfigError(f"invalid choice: '{item}' (choose from {', '.join(map(str, action.choices))})")
    return value


def _check_group_conflicts(parser: argparse.ArgumentParser, dests: set[str], path: Path, section: str) -> None:
    """Reject a section that sets more than one member of a mutually exclusive group."""
    for group in parser._mutually_exclusive_groups:
        conflicting = [action for action in group._group_actions if action.dest in dests]
        if len(conflicting) > 1:
            names = " and ".join(action.option_strings[-1] for action in conflicting)
            raise ConfigError(f"{path} [{section}]: {names} cannot both be set")


def load_config_values(path: Path, section: str, parser: argparse.ArgumentParser) -> dict[str, object]:
    """Return {dest: value} for the keys a config file sets under `section`, validated against `parser`.

    Every section name in the file must be a command name. Only `section` is validated in depth.
    """
    ini = _read_ini(path)
    for name in ini.sections():
        if name not in COMMAND_SECTIONS:
            raise ConfigError(f"{path} [{name}]: unknown section")
    if not ini.has_section(section):
        return {}
    actions = _option_actions(parser)
    values = {}
    for key, raw in ini.items(section):
        action = actions.get(key)
        if action is None:
            raise ConfigError(f"{path} [{section}] {key}: unknown option")
        try:
            values[action.dest] = _convert_value(action, raw, path.parent)
        except ConfigError as e:
            raise ConfigError(f"{path} [{section}] {key}: {e}") from None
    _check_group_conflicts(parser, set(values), path, section)
    return values
