"""Load a script from a file or URL and turn it into a list of roles."""
# Standard Library
from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import urlparse

# Third Party
import jsonschema
from rich import print
from rich.markup import escape

# Application Specific
from .role import normalize_id, Role
from .text_tools import format_filename
from .web import fetch, FetchError, is_data_uri, is_url
from .. import data_dir

SCHEMA_MESSAGE_LIMIT = 200


class ScriptError(RuntimeError):
    """Raised when a script cannot be loaded or understood."""


@dataclass
class ScriptSource:
    """The raw contents of a script and where it came from.

    Attributes:
        data: The decoded JSON.
        base_dir: The directory of the script file, or None if it came from a URL.
        fallback_name: A name to use if the script does not provide one.
    """
    data: object
    base_dir: Path | None
    fallback_name: str


@dataclass
class ParsedScript:
    """A parsed script.

    Attributes:
        name: The name of the script, if it provides one.
        roles: The roles in the script, in script order.
    """
    name: str | None
    roles: list[Role]


def load_script_source(location: str) -> ScriptSource:
    """Read and decode the JSON at a file path or URL."""
    base_dir: Path | None
    try:
        if is_url(location):
            raw = fetch(location)
            base_dir = None
            fallback_name = Path(urlparse(location).path).stem
        else:
            path = Path(location)
            raw = path.read_bytes()
            base_dir = path.parent.resolve()
            fallback_name = path.stem
        data = json.loads(raw.decode("utf-8"))
    except FetchError as e:
        raise ScriptError(str(e)) from e
    except OSError as e:
        raise ScriptError(f"Unable to read {location}: {e.strerror or e}") from e
    except UnicodeDecodeError as e:
        raise ScriptError(f"{location} is not valid UTF-8 text.") from e
    except json.JSONDecodeError as e:
        raise ScriptError(f"{location} is not valid JSON: {e}") from e
    return ScriptSource(data=data, base_dir=base_dir, fallback_name=fallback_name)


def parse_script(source: ScriptSource) -> ParsedScript:
    """Detect the format of a script and parse it."""
    data = source.data
    if isinstance(data, list):
        return parse_tpi(data, source.base_dir)
    if isinstance(data, dict) and "characterList" in data:
        return parse_bloodstar(data, source.base_dir)
    raise ScriptError(
        "Unrecognized script format: expected a JSON array (official format) "
        "or a Bloodstar save file with a 'characterList'."
    )


def _night_flag(number: object, reminder: object) -> bool | None:
    """Work out whether a role wakes, from its order number and reminder text."""
    if number is None and reminder is None:
        return None
    return (isinstance(number, (int, float)) and number > 0) or (isinstance(reminder, str) and bool(reminder))


def _resolve_image(image: object, base_dir: Path | None, role_id: str) -> str | None:
    """Work out the icon location for a role.

    URLs and data URIs are used as given. Local paths are only allowed for scripts read from a file, and relative ones
    are resolved against the script's directory.
    """
    if isinstance(image, list):
        image = image[0] if image else None
    if not isinstance(image, str) or not image:
        return None
    if is_url(image) or is_data_uri(image):
        return image
    if base_dir is None:
        print(f"[yellow]Warning:[/] Cannot use the local image '{escape(image)}' for {escape(role_id)} in a script "
              "from a URL.")
        return None
    if Path(image).is_absolute():
        return image
    return str((base_dir / image).resolve())


def _string_list(entry: dict, key: str) -> list[str] | None:
    """Return a list-of-strings field from an entry, or None if it is absent or malformed (with a warning)."""
    if key not in entry:
        return None
    value = entry[key]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    print(f"[yellow]Warning:[/] Ignoring '{key}' for {escape(entry['id'])}: expected a list of strings.")
    return None


def _tpi_reminders(entry: dict) -> list[str] | None:
    """Return the concatenated reminders of a TPI entry, or None if it specifies none."""
    reminders = _string_list(entry, "reminders")
    global_reminders = _string_list(entry, "remindersGlobal")
    if reminders is None and global_reminders is None:
        return None
    return (reminders or []) + (global_reminders or [])


def _role_from_tpi_entry(entry: object, base_dir: Path | None) -> Role | None:
    """Build a role from a TPI entry, or None if the entry is not a role."""
    if isinstance(entry, str):
        return Role(entry)
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
        print(f"[yellow]Warning:[/] Skipping script entry without an id: {escape(repr(entry))}")
        return None
    role = Role(entry["id"])
    if len(entry) == 1:
        return role
    role.name = entry.get("name")
    team = entry.get("team")
    role.team = "traveler" if team == "traveller" else team
    role.ability = entry.get("ability")
    role.reminders = _tpi_reminders(entry)
    role.first_night = _night_flag(entry.get("firstNight"), entry.get("firstNightReminder"))
    role.other_nights = _night_flag(entry.get("otherNight"), entry.get("otherNightReminder"))
    role.affects_setup = entry.get("setup")
    role.icon = _resolve_image(entry.get("image"), base_dir, role.id)
    return role


def parse_tpi(data: list, base_dir: Path | None) -> ParsedScript:
    """Parse the official script format."""
    schema = json.loads((data_dir / "role_schema.json").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        message = e.message if len(e.message) <= SCHEMA_MESSAGE_LIMIT else e.message[:SCHEMA_MESSAGE_LIMIT] + "..."
        print(f"[yellow]Warning:[/] The script does not match the official schema at {escape(e.json_path)}: "
              f"{escape(message)}")
    name = None
    roles = []
    for entry in data:
        if isinstance(entry, dict) and entry.get("id") == "_meta":
            name = entry.get("name")
            continue
        role = _role_from_tpi_entry(entry, base_dir)
        if role is not None:
            roles.append(role)
    return ParsedScript(name=name, roles=roles)


def _lines(text: object) -> list[str]:
    """Split text on newlines, stripping each line and dropping blanks."""
    if not isinstance(text, str):
        return []
    return [line.strip() for line in text.split("\n") if line.strip()]


def _night_order(order: object) -> list[str]:
    """Return the normalized ids of a Bloodstar night order, treating anything but a list as empty."""
    if not isinstance(order, list):
        return []
    return [normalize_id(i) for i in order if isinstance(i, str)]


def _role_from_bloodstar_entry(
        entry: object,
        first_order: list[str],
        other_order: list[str],
        base_dir: Path | None
) -> Role | None:
    """Build a role from a Bloodstar character, or None if it should not be exported."""
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
        print(f"[yellow]Warning:[/] Skipping Bloodstar character without an id: {escape(repr(entry))}")
        return None
    if entry.get("export") is False:
        return None
    first_reminder = entry.get("firstNightReminder")
    other_reminder = entry.get("otherNightReminder")
    normalized = normalize_id(entry["id"])
    team = entry.get("team")
    return Role(
        id=entry["id"],
        name=entry.get("name"),
        team="traveler" if team == "traveller" else team,
        ability=entry.get("ability"),
        reminders=_lines(entry.get("characterReminderTokens")) + _lines(entry.get("globalReminderTokens")),
        first_night=normalized in first_order and bool(first_reminder),
        other_nights=normalized in other_order and bool(other_reminder),
        affects_setup=entry.get("setup"),
        icon=_resolve_image(entry.get("styledImage"), base_dir, entry["id"]),
    )


def parse_bloodstar(data: dict, base_dir: Path | None) -> ParsedScript:
    """Parse a Bloodstar save file."""
    characters = data["characterList"]
    if not isinstance(characters, list):
        raise ScriptError("The Bloodstar 'characterList' must be a list.")
    meta = data.get("meta")
    name = meta.get("name") if isinstance(meta, dict) else None
    first_order = _night_order(data.get("firstNightOrder"))
    other_order = _night_order(data.get("otherNightOrder"))
    roles = []
    for entry in characters:
        role = _role_from_bloodstar_entry(entry, first_order, other_order, base_dir)
        if role is not None:
            roles.append(role)
    return ParsedScript(name=name, roles=roles)


def script_slug(parsed: ParsedScript, source: ScriptSource) -> str:
    """Return a filename-safe name for the script."""
    return format_filename(parsed.name or source.fallback_name) or "script"
