"""Tests for the script loader."""
# Standard Library
from urllib.error import HTTPError

# Third Party
import pytest

# Application Specific
from botc_tokens.helpers.script_loader import (
    load_script_source, parse_bloodstar, parse_script, parse_tpi, ParsedScript, script_slug, ScriptError, ScriptSource,
)


def test_load_local_file(test_data_dir):
    """A local file loads with its directory and stem."""
    source = load_script_source(str(test_data_dir / "scripts" / "tpi_script.json"))
    assert isinstance(source.data, list)
    assert source.base_dir == (test_data_dir / "scripts").resolve()
    assert source.fallback_name == "tpi_script"


def test_load_url(fake_web):
    """A URL loads without a base directory."""
    fake_web.routes["https://h/p/script.json"] = b'[{"id": "imp"}]'
    source = load_script_source("https://h/p/script.json")
    assert source.data == [{"id": "imp"}]
    assert source.base_dir is None
    assert source.fallback_name == "script"


def test_load_errors(tmp_path, fake_web):
    """Each way loading can fail becomes a ScriptError."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{nope")
    bad_utf8 = tmp_path / "utf8.json"
    bad_utf8.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(ScriptError, match="Unable to read"):
        load_script_source(str(tmp_path / "missing.json"))
    with pytest.raises(ScriptError, match="not valid JSON"):
        load_script_source(str(bad_json))
    with pytest.raises(ScriptError, match="UTF-8"):
        load_script_source(str(bad_utf8))
    with pytest.raises(ScriptError, match="not found"):
        load_script_source("https://h/missing.json")
    fake_web.routes["https://h/err.json"] = HTTPError("https://h/err.json", 404, "Not Found", {}, None)
    with pytest.raises(ScriptError):
        load_script_source("https://h/err.json")


def test_parse_tpi_entries(test_data_dir, capsys):
    """TPI entries map onto roles, leaving unspecified fields as None."""
    source = load_script_source(str(test_data_dir / "scripts" / "tpi_script.json"))
    parsed = parse_script(source)
    assert parsed.name == "Test Script"
    assert [r.id for r in parsed.roles] == ["washerwoman", "imp", "homebrew_one", "homebrew_two", "drunk"]
    washerwoman, imp, one, two, drunk = parsed.roles
    assert washerwoman.is_reference() and imp.is_reference()
    assert washerwoman == type(washerwoman)("washerwoman")
    assert one.name == "Homebrew One"
    assert one.team == "townsfolk"
    assert one.reminders == ["ONE", "IS ONE"]
    assert one.first_night is True
    assert one.other_nights is False
    assert one.affects_setup is None
    assert one.icon == str((test_data_dir / "scripts" / "icons" / "one.png").resolve())
    assert two.team == "traveler"
    assert two.reminders is None
    assert two.first_night is True
    assert two.other_nights is None
    assert two.affects_setup is False
    assert two.icon == "https://example.test/two.png"
    assert drunk.team == "outsider"
    assert drunk.is_reference()
    # The fixture deliberately uses homebrew ids and a partial override, which the official schema rejects.
    assert capsys.readouterr().out.count("Warning") == 1


def test_parse_tpi_images(tmp_path):
    """Absolute paths, URLs, data URIs, empty lists, and odd values are handled."""
    absolute = str(tmp_path / "a.png")
    entries = [
        {"id": "a", "name": "A", "image": absolute},
        {"id": "b", "name": "B", "image": "data:image/png;base64,AAAA"},
        {"id": "c", "name": "C", "image": []},
        {"id": "d", "name": "D", "image": 5},
        {"id": "e", "name": "E", "reminders": ["R"], "otherNight": 2.5},
    ]
    roles = parse_tpi(entries, tmp_path).roles
    assert roles[0].icon == absolute
    assert roles[1].icon == "data:image/png;base64,AAAA"
    assert roles[2].icon is None
    assert roles[3].icon is None
    assert roles[4].reminders == ["R"]
    assert roles[4].other_nights is True


def test_parse_tpi_relative_image_from_url_warns(capsys):
    """A relative image from a URL script cannot be resolved."""
    roles = parse_tpi([{"id": "x", "name": "x", "team": "minion", "ability": "", "image": "a.png"}], None).roles
    assert roles[0].icon is None
    assert "Warning" in capsys.readouterr().out


def test_parse_tpi_schema_warning(capsys):
    """Schema failures warn but the role is still returned."""
    roles = parse_tpi([{"id": "x", "name": "x", "team": "nope", "ability": ""}], None).roles
    assert "Warning" in capsys.readouterr().out
    assert [r.id for r in roles] == ["x"]


def test_parse_tpi_skips_junk(capsys):
    """Entries that are not roles are skipped with a warning."""
    assert parse_tpi([42, {"name": "no id"}], None).roles == []
    assert capsys.readouterr().out.count("Warning") >= 2


def test_parse_bloodstar(test_data_dir, capsys):
    """Bloodstar characters map onto roles."""
    parsed = parse_script(load_script_source(str(test_data_dir / "scripts" / "bloodstar_save.json")))
    assert parsed.name == "Blood Script"
    assert [r.id for r in parsed.roles] == ["alpha", "gamma"]
    alpha, gamma = parsed.roles
    assert alpha.team == "traveler"
    assert alpha.reminders == ["A ONE", "A TWO"]
    assert alpha.first_night is True
    assert alpha.other_nights is False
    assert alpha.affects_setup is True
    assert alpha.icon.startswith("data:")
    assert gamma.icon is None
    assert gamma.reminders == []
    assert gamma.first_night is False
    assert "Warning" not in capsys.readouterr().out


def test_parse_bloodstar_bad_shapes(capsys):
    """Structural problems are errors or skipped entries."""
    with pytest.raises(ScriptError):
        parse_bloodstar({"characterList": "nope"})
    parsed = parse_bloodstar({
        "meta": "odd",
        "characterList": [{"name": "no id"}, "junk", {"id": "ok", "team": "minion"}],
        "firstNightOrder": ["ok", 5],
        "otherNightOrder": [None],
    })
    assert parsed.name is None
    assert [r.id for r in parsed.roles] == ["ok"]
    assert parsed.roles[0].first_night is False
    assert capsys.readouterr().out.count("Warning") == 2


def test_parse_script_dispatch(tmp_path):
    """The format is detected from the shape of the JSON."""
    assert parse_script(ScriptSource([{"id": "imp"}], None, "s")).roles[0].id == "imp"
    assert parse_script(ScriptSource({"characterList": []}, None, "s")).roles == []
    with pytest.raises(ScriptError, match="Unrecognized script format"):
        parse_script(ScriptSource({"other": 1}, None, "s"))
    with pytest.raises(ScriptError, match="Unrecognized script format"):
        parse_script(ScriptSource("string", None, "s"))


def test_script_slug():
    """The slug prefers the script name, then the fallback, then 'script'."""
    assert script_slug(ParsedScript("My Script!", []), ScriptSource([], None, "x")) == "My_Script"
    assert script_slug(ParsedScript(None, []), ScriptSource([], None, "script")) == "script"
    assert script_slug(ParsedScript(None, []), ScriptSource([], None, "")) == "script"
