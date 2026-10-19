"""Guards for the bundled data files."""
# Standard Library
import json

# Application Specific
from botc_tokens import data_dir
from botc_tokens.helpers.role import normalize_id


def test_icon_lookup_guard(test_data_dir):
    """The icon lookup is well formed and covers the fixture roles."""
    lookup = json.loads((data_dir / "icon_lookup.json").read_text(encoding="utf-8"))
    assert lookup
    for key, value in lookup.items():
        assert key == normalize_id(key)
        assert value.startswith("https://release.botc.app/resources/characters/")
    roles = json.loads((test_data_dir / "official" / "roles.json").read_text(encoding="utf-8"))
    for role in roles:
        assert normalize_id(role["id"]) in lookup
