"""Tests for the create command."""
# Standard Library
import json
from shutil import copy
from unittest.mock import patch
from urllib.error import URLError

# Third Party
from pypdf import PdfReader
import pytest

# Application Specific
from botc_tokens.commands import create
from botc_tokens.helpers.official_data import NIGHTSHEET_URL, ROLES_URL
from botc_tokens.helpers.overrides import load_icon_lookup

SOLO_ICON_URL = "https://example.test/solo.png"


def _run_cmd(arg_list):
    """Run the create command with the given arguments and return its exit code."""
    argv_patch = ["botc_tokens", "create"]
    argv_patch.extend(arg_list)

    with patch("sys.argv", argv_patch):
        return create.run()


def _output(capsys):
    """Return the captured stdout with rich's line wrapping removed."""
    return capsys.readouterr().out.replace("\n", "")


def _write_script(path, entries):
    """Write a TPI script to a file and return its path as a string."""
    path.write_text(json.dumps(entries))
    return str(path)


def _solo(role_id="solo", image=SOLO_ICON_URL):
    """Return a homebrew role definition with no reminders, so it renders a single token."""
    return {"id": role_id, "name": role_id.title(), "team": "townsfolk", "ability": "Does a thing.", "image": image}


def _mtimes(directory):
    """Return the modification times of every file in a directory, keyed by name."""
    return {file.name: file.stat().st_mtime_ns for file in directory.iterdir()}


@pytest.fixture()
def web(fake_web, test_data_dir):
    """Serve the official feeds and every icon the tests use."""
    icon = (test_data_dir / "icons" / "tight.webp").read_bytes()
    fake_web.routes.update({url: icon for url in load_icon_lookup(None).values()})
    fake_web.routes.update({
        ROLES_URL: (test_data_dir / "official" / "roles.json").read_bytes(),
        NIGHTSHEET_URL: (test_data_dir / "official" / "nightsheet.json").read_bytes(),
        SOLO_ICON_URL: icon,
        "https://example.test/two.png": icon,
    })
    return fake_web


@pytest.fixture()
def solo_script(tmp_path):
    """A script holding a single homebrew role with a URL icon and no reminders."""
    return _write_script(tmp_path / "solo.json", [_solo()])


def test_create_from_tpi_file(tmp_path, web, test_data_dir):
    """A TPI script yields sheets, padded icons, and tokens named after the script."""
    out = tmp_path / "out"
    cache = tmp_path / "cache"
    script = test_data_dir / "scripts" / "tpi_script.json"

    assert _run_cmd(["-o", str(out), "-m", str(cache), str(script)]) == 0

    assert (out / "roles.pdf").is_file()
    assert (out / "reminders.pdf").is_file()
    assert (cache / "icons" / "washerwoman.png").is_file()
    tokens = cache / "tokens_Test_Script"
    assert (tokens / "washerwoman.png").is_file()
    assert (tokens / "homebrewone-reminder-1.png").is_file()
    assert (tokens / "homebrewone-reminder-2.png").is_file()


def test_create_from_url(tmp_path, web):
    """A script fetched from a URL without a name is named after the URL's last path segment."""
    web.routes["https://h/p/script.json"] = json.dumps([_solo()]).encode()
    cache = tmp_path / "cache"

    assert _run_cmd(["-o", str(tmp_path / "out"), "-m", str(cache), "https://h/p/script.json"]) == 0

    assert (cache / "tokens_script" / "solo.png").is_file()


def test_create_from_bloodstar(tmp_path, web, test_data_dir, capsys):
    """A Bloodstar save yields tokens; a role with no icon is rendered without one and warned about."""
    cache = tmp_path / "cache"
    script = test_data_dir / "scripts" / "bloodstar_save.json"

    assert _run_cmd(["-o", str(tmp_path / "out"), "-m", str(cache), str(script)]) == 0

    tokens = cache / "tokens_Blood_Script"
    assert (tokens / "alpha.png").is_file()
    assert (tokens / "alpha-reminder-1.png").is_file()
    assert (tokens / "alpha-reminder-2.png").is_file()
    assert (tokens / "gamma.png").is_file()
    assert not (tokens / "beta.png").exists()
    out = _output(capsys)
    assert "Warning:" in out
    assert "Gamma has no icon" in out


def test_create_no_intermediate_dir_uses_temp(tmp_path, web, monkeypatch, test_data_dir):
    """Without -m, intermediate files go to a temporary directory and only the PDFs are left."""
    monkeypatch.chdir(tmp_path)
    script = _write_script(tmp_path / "script.json", ["imp"])

    assert _run_cmd(["-o", "out", script]) == 0

    assert sorted(p.name for p in tmp_path.rglob("*")) == ["out", "reminders.pdf", "roles.pdf", "script.json"]


def test_create_incremental_reuses(tmp_path, web, solo_script):
    """With --incremental, cached icons are not downloaded again and tokens are not rewritten."""
    cache = tmp_path / "cache"
    args = ["-o", str(tmp_path / "out"), "-m", str(cache), "--incremental", solo_script]
    assert _run_cmd(args) == 0
    assert SOLO_ICON_URL in web.calls
    before = _mtimes(cache / "tokens_solo")
    web.calls.clear()

    assert _run_cmd(args) == 0

    assert SOLO_ICON_URL not in web.calls
    assert _mtimes(cache / "tokens_solo") == before


def test_create_regenerates_without_incremental(tmp_path, web, solo_script):
    """Without --incremental, icons are downloaded again and tokens are rewritten."""
    cache = tmp_path / "cache"
    args = ["-o", str(tmp_path / "out"), "-m", str(cache), solo_script]
    assert _run_cmd(args) == 0
    before = _mtimes(cache / "tokens_solo")
    web.calls.clear()

    assert _run_cmd(args) == 0

    assert SOLO_ICON_URL in web.calls
    after = _mtimes(cache / "tokens_solo")
    assert after.keys() == before.keys()
    assert all(after[name] != before[name] for name in before)


def test_create_duplicate_role_ids(tmp_path, web, capsys):
    """A role listed twice is rendered once but placed on the sheet once per listing.

    The imp has a built-in duplicate count of 4, so two listings place 8 role tokens.
    """
    cache = tmp_path / "cache"
    script = _write_script(tmp_path / "dupes.json", ["imp", "imp"])

    assert _run_cmd(["-o", str(tmp_path / "out"), "-m", str(cache), script]) == 0

    assert sorted(p.name for p in (cache / "tokens_dupes").iterdir()) == ["imp-reminder-1.png", "imp.png"]
    assert "Created 8 role tokens" in _output(capsys)


def test_create_skips_unknown_reference(tmp_path, web, capsys):
    """A bare id that is not an official role is reported and skipped; the rest are still made."""
    cache = tmp_path / "cache"
    script = _write_script(tmp_path / "mixed.json", ["notarole", _solo()])

    assert _run_cmd(["-o", str(tmp_path / "out"), "-m", str(cache), script]) == 0

    out = _output(capsys)
    assert "Error:" in out
    assert "notarole" in out
    assert "Created 1 role tokens and 0 reminder tokens; skipped 1 roles." in out
    assert (cache / "tokens_mixed" / "solo.png").is_file()
    assert not (cache / "tokens_mixed" / "notarole.png").exists()


def test_create_all_roles_skipped_exits_1(tmp_path, web, capsys):
    """A run that leaves no roles to make tokens for is an error."""
    script = _write_script(tmp_path / "bad.json", ["notarole"])

    assert _run_cmd(["-o", str(tmp_path / "out"), script]) == 1

    assert "No roles" in _output(capsys)
    assert not (tmp_path / "out" / "roles.pdf").exists()


def test_create_official_feed_down_exits_1(tmp_path, web, capsys):
    """Unreachable official data is fatal for a script that needs it."""
    web.routes[ROLES_URL] = URLError("offline")
    script = _write_script(tmp_path / "script.json", ["imp"])

    assert _run_cmd(["-o", str(tmp_path / "out"), script]) == 1

    out = _output(capsys)
    assert "Error:" in out
    assert "offline" in out


def test_create_bad_script_exits_1(tmp_path, capsys):
    """A missing script file or invalid JSON is fatal."""
    assert _run_cmd(["-o", str(tmp_path / "out"), str(tmp_path / "missing.json")]) == 1
    assert "Error:" in _output(capsys)

    bad = tmp_path / "bad.json"
    bad.write_text("[not json")
    assert _run_cmd(["-o", str(tmp_path / "out"), str(bad)]) == 1
    assert "not valid JSON" in _output(capsys)


def test_create_components_errors(tmp_path, solo_script, capsys):
    """A components path that does not exist, or a file that is not a zip, is fatal."""
    assert _run_cmd(["-c", str(tmp_path / "nope"), solo_script]) == 1
    assert "Error:" in _output(capsys)

    not_a_zip = tmp_path / "components.txt"
    not_a_zip.write_text("hello")
    assert _run_cmd(["-c", str(not_a_zip), solo_script]) == 1
    assert "Error:" in _output(capsys)


def test_create_duplicates_and_lookup_overrides(tmp_path, web, test_data_dir, capsys):
    """User duplicate counts and icon lookups are merged over the built-ins."""
    cache = tmp_path / "cache"
    copy(test_data_dir / "icons" / "1.png", tmp_path / "noimage_icon.png")
    script = _write_script(tmp_path / "script.json", [
        "imp", {"id": "noimage", "name": "No Image", "team": "townsfolk", "ability": "Nothing."}
    ])
    duplicates = tmp_path / "duplicates.json"
    duplicates.write_text(json.dumps({"imp": 2}))
    lookup = tmp_path / "lookup.json"
    lookup.write_text(json.dumps({"noimage": "noimage_icon.png"}))

    assert _run_cmd([
        "-o", str(tmp_path / "out"), "-m", str(cache), "--duplicates", str(duplicates), "--icon-lookup", str(lookup),
        script
    ]) == 0

    out = _output(capsys)
    assert "Created 3 role tokens" in out
    assert "no icon" not in out
    assert (cache / "icons" / "noimage.png").is_file()


@pytest.mark.parametrize("option, content", [
    ("--duplicates", '{"imp": "two"}'),
    ("--duplicates", "{not json"),
    ("--icon-lookup", '{"imp": 3}'),
    ("--icon-lookup", None),
])
def test_create_invalid_override_file_exits_1(tmp_path, web, solo_script, capsys, option, content):
    """An override file that is missing, not JSON, or does not match its schema is fatal."""
    override = tmp_path / "override.json"
    if content is not None:
        override.write_text(content)

    assert _run_cmd(["-o", str(tmp_path / "out"), option, str(override), solo_script]) == 1

    assert "Error:" in _output(capsys)
    assert not (tmp_path / "out").exists()


def test_create_paper_options(tmp_path, web, solo_script):
    """Paper presets and custom sizes set the PDF page size; the two options are mutually exclusive."""
    assert _run_cmd(["-o", str(tmp_path / "a4"), "--paper-type", "a4", solo_script]) == 0
    box = PdfReader(tmp_path / "a4" / "roles.pdf").pages[0].mediabox
    assert (round(float(box.width) / 72 * 25.4), round(float(box.height) / 72 * 25.4)) == (210, 297)

    assert _run_cmd(["-o", str(tmp_path / "custom"), "--paper-size", "100", "100", solo_script]) == 0
    box = PdfReader(tmp_path / "custom" / "roles.pdf").pages[0].mediabox
    assert (round(float(box.width) / 72 * 25.4), round(float(box.height) / 72 * 25.4)) == (100, 100)

    with pytest.raises(SystemExit) as e:
        _run_cmd(["--paper-type", "a4", "--paper-size", "100", "100", solo_script])
    assert e.value.code == 2


def test_create_margin_too_large_exits_1(tmp_path, web, solo_script, capsys):
    """Margins that leave no printable area are fatal."""
    assert _run_cmd(["-o", str(tmp_path / "out"), "--margin-horizontal", "120", solo_script]) == 1

    assert "margin is too large" in _output(capsys)


def test_create_token_too_large_exits_1(tmp_path, web, solo_script, capsys):
    """A token that does not fit on the page is fatal."""
    assert _run_cmd(["-o", str(tmp_path / "out"), "--role-diameter", "300", "--paper-type", "a5", solo_script]) == 1

    assert "does not fit" in _output(capsys)


def test_create_skip_ability_text_and_grid(tmp_path, web, solo_script):
    """Skipping ability text changes the role token; grid layout still produces sheets."""
    assert _run_cmd(["-o", str(tmp_path / "plain_out"), "-m", str(tmp_path / "plain"), solo_script]) == 0
    assert _run_cmd([
        "-o", str(tmp_path / "out"), "-m", str(tmp_path / "skip"), "--skip-ability-text", "--grid", solo_script
    ]) == 0

    assert (tmp_path / "out" / "roles.pdf").is_file()
    plain = (tmp_path / "plain" / "tokens_solo" / "solo.png").read_bytes()
    skipped = (tmp_path / "skip" / "tokens_solo" / "solo.png").read_bytes()
    assert plain != skipped


def test_create_mm_defaults_match_pixels():
    """The default millimeter options reproduce the historical pixel defaults at 300 DPI."""
    with patch("sys.argv", ["botc_tokens", "create", "script.json"]):
        layout = create._build_layout(create._parse_args())

    assert layout.role_diameter == 543
    assert layout.reminder_diameter == 307
    assert layout.margin_horizontal == 74
    assert layout.margin_vertical == 74
    assert layout.padding == 0
    assert (layout.page_width, layout.page_height) == (2550, 3300)
    assert layout.dpi == 300
    assert layout.close_packing is True


def test_create_sparse_components_note(tmp_path, web, solo_script, component_package, capsys):
    """A component pack missing a file falls back to the built-in one and says so."""
    (component_package / "Leaf1.png").unlink()

    assert _run_cmd(["-o", str(tmp_path / "out"), "-c", str(component_package), solo_script]) == 0

    assert "Using built-in components for: Leaf1.png" in _output(capsys)
