"""Built-in duplicate counts and icon lookup, merged with optional user override files."""
# Standard Library
import json
from pathlib import Path

# Third Party
import jsonschema

# Application Specific
from .role import normalize_id
from .web import is_data_uri, is_url
from .. import data_dir


def _load_with_schema(path: Path, schema_name: str) -> dict:
    """Load a JSON object from a file and validate it against a bundled schema."""
    data = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((data_dir / schema_name).read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)
    return data


def load_duplicates(user_file: str | None) -> dict[str, int]:
    """Return the duplicate counts, with an optional user file merged over the built-ins."""
    builtin = _load_with_schema(Path(str(data_dir / "known_duplicates.json")), "duplicate_schema.json")
    duplicates = {normalize_id(key): value for key, value in builtin.items()}
    if user_file:
        user = _load_with_schema(Path(user_file), "duplicate_schema.json")
        duplicates.update({normalize_id(key): value for key, value in user.items()})
    return duplicates


def load_icon_lookup(user_file: str | None) -> dict[str, str]:
    """Return the icon lookup, with an optional user file merged over the built-ins.

    Relative paths in the user file are resolved against the user file's directory.
    """
    lookup = _load_with_schema(Path(str(data_dir / "icon_lookup.json")), "icon_lookup_schema.json")
    if user_file:
        user_path = Path(user_file)
        for key, value in _load_with_schema(user_path, "icon_lookup_schema.json").items():
            if not (is_url(value) or is_data_uri(value)) and not Path(value).is_absolute():
                value = str(user_path.parent / value)
            lookup[normalize_id(key)] = value
    return lookup


def official_ids() -> frozenset[str]:
    """Return the ids of every official role with a built-in icon."""
    return frozenset(load_icon_lookup(None))
