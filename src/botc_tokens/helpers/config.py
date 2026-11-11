"""Read option defaults for the commands from botc_tokens.conf files.

Defaults come from a global file, then a local file, and real command line arguments beat both.
"""
# Standard Library
import argparse
import configparser
import os
from pathlib import Path
import sys

# Third Party
from rich import print
from rich.markup import escape

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
        if candidate.exists():
            return candidate
    return None


def config_file_paths() -> list[Path]:
    """Return the existing config files to load, global first then local, listing a shared file once.

    Anything that exists under the config name is returned, so a directory with that name is reported as an error
    when read rather than silently skipped for a file higher up the tree.
    """
    paths = []
    seen = set()
    local = find_local_config(local_start_dir())
    for candidate in (global_config_path(), local):
        if candidate is None or not candidate.exists():
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
        ini.read_string(path.read_text(encoding="utf-8-sig"), source=str(path))
    except (OSError, UnicodeDecodeError, configparser.Error) as e:
        raise ConfigError(f"{path}: {e}") from None
    return ini


SUPPORTED_ACTIONS = (argparse._StoreAction, argparse._StoreTrueAction, argparse._StoreFalseAction)


def _option_actions(parser: argparse.ArgumentParser) -> dict[str, argparse.Action]:
    """Map each configurable key (long option name without the dashes) to its action.

    Raises NotImplementedError for an option whose action the config layer cannot represent, so adding such an
    option to a command fails the test suite instead of misbehaving for users.
    """
    actions = {}
    for action in parser._actions:
        if action.dest == "help" or not action.option_strings:
            continue
        if not isinstance(action, SUPPORTED_ACTIONS):
            raise NotImplementedError(
                f"{action.option_strings[-1]} uses an action the config layer does not support "
                f"({type(action).__name__}); supported: store, store_true, store_false")
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
        try:
            value = Path(raw).expanduser()
        except RuntimeError as e:
            raise ConfigError(str(e)) from None
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
    if isinstance(action, argparse._StoreTrueAction):
        return _convert_bool(raw.strip())
    if isinstance(action, argparse._StoreFalseAction):
        # A true value means "as if the flag was given", which stores False.
        return not _convert_bool(raw.strip())
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


def merge_config_values(parser: argparse.ArgumentParser, layers: list[dict[str, object]]) -> dict[str, object]:
    """Merge config layers key by key, lowest priority first.

    A layer that sets any member of a mutually exclusive group replaces the whole group, so a local file choosing
    --paper-size discards a global --paper-type.
    """
    merged: dict[str, object] = {}
    for layer in layers:
        for group in parser._mutually_exclusive_groups:
            dests = [action.dest for action in group._group_actions]
            if any(dest in layer for dest in dests):
                for dest in dests:
                    merged.pop(dest, None)
        merged.update(layer)
    return merged


def _cli_given_group_members(parser: argparse.ArgumentParser, argv: list[str]) -> set[str]:
    """Return the dests of mutually exclusive group members that appear on the command line.

    Argparse does the parsing, so --opt=value and abbreviations count. The parse is a trial run with sentinel
    defaults; argparse errors (and help) exit here exactly as the real parse would.
    """
    sentinel = object()
    actions = [action for group in parser._mutually_exclusive_groups for action in group._group_actions]
    saved = [action.default for action in actions]
    for action in actions:
        action.default = sentinel
    try:
        namespace = parser.parse_intermixed_args(argv)
    finally:
        for action, default in zip(actions, saved):
            action.default = default
    return {action.dest for action in actions if getattr(namespace, action.dest) is not sentinel}


def _is_help_flag(arg: str) -> bool:
    """Tell whether a command line argument asks for help, including argparse's --he/--hel abbreviations."""
    return arg == "-h" or (len(arg) >= 3 and "--help".startswith(arg))


def parse_args_with_config(parser: argparse.ArgumentParser, command: str, argv: list[str]) -> argparse.Namespace:
    """Parse `argv` with the parser's defaults replaced by the values the config files set for `command`.

    Options and positional arguments may be mixed freely, so `create a.json -c pack_a b.json -c pack_b` works.
    """
    if any(_is_help_flag(arg) for arg in argv):
        return parser.parse_intermixed_args(argv)
    _option_actions(parser)  # Reject unsupported option kinds even when no config file exists.
    try:
        paths = config_file_paths()
        layers = [load_config_values(path, command, parser) for path in paths]
    except ConfigError as e:
        parser.error(str(e))
    except (OSError, RuntimeError) as e:
        parser.error(f"cannot look for config files: {e}")
    if paths:
        print(f"[bold]Using config:[/] {escape(', '.join(str(path) for path in paths))}")
    merged = merge_config_values(parser, layers)
    _relax_required(parser, merged)
    if parser._mutually_exclusive_groups:
        _drop_groups_given_on_cli(parser, argv, merged)
    parser.set_defaults(**merged)
    return parser.parse_intermixed_args(argv)


def _relax_required(parser: argparse.ArgumentParser, merged: dict[str, object]) -> None:
    """Let a config value satisfy a required option or a required mutually exclusive group."""
    for action in parser._actions:
        if action.required and action.dest in merged:
            action.required = False
    for group in parser._mutually_exclusive_groups:
        if group.required and any(action.dest in merged for action in group._group_actions):
            group.required = False


def _drop_groups_given_on_cli(parser: argparse.ArgumentParser, argv: list[str], merged: dict[str, object]) -> None:
    """Remove every config value for a mutually exclusive group that the command line sets a member of."""
    given = _cli_given_group_members(parser, argv)
    for group in parser._mutually_exclusive_groups:
        dests = [action.dest for action in group._group_actions]
        if any(dest in given for dest in dests):
            for dest in dests:
                merged.pop(dest, None)


def config_epilog() -> str:
    """Describe, for a command's --help, where option defaults can be set."""
    try:
        global_path = str(global_config_path())
    except (OSError, RuntimeError):
        global_path = f"{APP_DIR_NAME}/{CONFIG_FILENAME} in your user config directory"
    return (f"Defaults for any --option can be set in a config file: {global_path} applies to every run, "
            f"and the nearest {CONFIG_FILENAME} in the current directory or one of its parents overrides it. "
            "Command line arguments override both.")
