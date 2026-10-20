"""Tests for the built-in overrides helper."""
# Standard Library
import json

# Third Party
import jsonschema
import pytest

# Application Specific
from botc_tokens.helpers.overrides import load_duplicates, load_icon_lookup, official_ids


def test_load_duplicates_builtin():
    """The built-in duplicates are returned when no user file is given."""
    duplicates = load_duplicates(None)
    assert duplicates["legion"] == 12
    assert duplicates["imp"] == 4


def test_load_duplicates_user_override(tmp_path):
    """User entries are normalized and merged over the built-ins."""
    user_file = tmp_path / "dups.json"
    user_file.write_text(json.dumps({"imp": 2, "new_role": 3}))
    duplicates = load_duplicates(str(user_file))
    assert duplicates["imp"] == 2
    assert duplicates["newrole"] == 3
    assert duplicates["legion"] == 12


def test_load_duplicates_invalid(tmp_path):
    """A user file that violates the schema raises a validation error."""
    user_file = tmp_path / "dups.json"
    user_file.write_text(json.dumps({"imp": "two"}))
    with pytest.raises(jsonschema.ValidationError):
        load_duplicates(str(user_file))


def test_load_duplicates_missing_file(tmp_path):
    """A missing user file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_duplicates(str(tmp_path / "nope.json"))


def test_load_duplicates_bad_json(tmp_path):
    """A malformed user file raises JSONDecodeError."""
    user_file = tmp_path / "dups.json"
    user_file.write_text("{")
    with pytest.raises(json.JSONDecodeError):
        load_duplicates(str(user_file))


def test_load_icon_lookup_builtin():
    """The built-in lookup maps official ids to icon URLs."""
    lookup = load_icon_lookup(None)
    assert lookup["washerwoman"].startswith("https://")
    assert lookup["washerwoman"].endswith("/tb/washerwoman_g.webp")


def test_load_icon_lookup_user_paths(tmp_path):
    """Relative user paths resolve against the user file; URLs and data URIs are unchanged."""
    user_file = tmp_path / "icons.json"
    data = {
        "homebrew": "icons/h.png",
        "abs": "/abs/x.png",
        "web": "https://x/y.png",
        "data": "data:image/png;base64,AA==",
    }
    user_file.write_text(json.dumps(data))
    lookup = load_icon_lookup(str(user_file))
    assert lookup["homebrew"] == str((tmp_path / "icons/h.png").resolve())
    assert lookup["abs"] == "/abs/x.png"
    assert lookup["web"] == "https://x/y.png"
    assert lookup["data"] == "data:image/png;base64,AA=="
    assert "washerwoman" in lookup


def test_official_ids():
    """Official ids come from the built-in lookup."""
    assert "imp" in official_ids()
    assert "homebrew" not in official_ids()


def test_load_icon_lookup_relative_user_file(tmp_path, monkeypatch):
    """A relative user file path still yields absolute resolved icon paths."""
    (tmp_path / "icons.json").write_text(json.dumps({"homebrew": "icons/h.png"}))
    monkeypatch.chdir(tmp_path)
    lookup = load_icon_lookup("icons.json")
    assert lookup["homebrew"] == str((tmp_path / "icons/h.png").resolve())


def test_load_duplicates_integral_floats_become_ints(tmp_path):
    """A count written as 2.0 is accepted by the schema and returned as an int."""
    user_file = tmp_path / "dups.json"
    user_file.write_text(json.dumps({"imp": 2.0}))
    duplicates = load_duplicates(str(user_file))
    assert duplicates["imp"] == 2
    assert type(duplicates["imp"]) is int


@pytest.mark.parametrize("count", [-1, 101])
def test_load_duplicates_rejects_out_of_range_counts(tmp_path, count):
    """Counts must be between 0 and 100."""
    user_file = tmp_path / "dups.json"
    user_file.write_text(json.dumps({"imp": count}))
    with pytest.raises(jsonschema.ValidationError):
        load_duplicates(str(user_file))
