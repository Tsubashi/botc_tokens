"""Tests for the create command."""
# Standard Library
import json
from shutil import copy
from unittest.mock import patch
from urllib.error import URLError

# Third Party
from pypdf import PdfReader
import pytest
from wand.color import Color
from wand.image import Image

# Application Specific
from botc_tokens.commands import create
from botc_tokens.helpers.official_data import NIGHTSHEET_URL, ROLES_URL, translation_url
from botc_tokens.helpers.overrides import load_icon_lookup
from botc_tokens.helpers.role import Role

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
    # The partial drunk entry overrides the team only; its name and reminder are back-filled from official data
    assert (tokens / "drunk.png").is_file()
    assert (tokens / "drunk-reminder-1.png").is_file()


def test_create_homebrew_without_ability(tmp_path, web, capsys):
    """A homebrew object without an ability renders with empty ability text and needs no official data."""
    cache = tmp_path / "cache"
    role = _solo()
    del role["ability"]
    script = _write_script(tmp_path / "noability.json", [role])

    assert _run_cmd(["-o", str(tmp_path / "out"), "-m", str(cache), script]) == 0

    assert (cache / "tokens_noability" / "solo.png").is_file()
    assert ROLES_URL not in web.calls
    assert NIGHTSHEET_URL not in web.calls
    assert "skipped 0 roles" in _output(capsys)


def test_create_corrupt_cached_icon(tmp_path, web, solo_script, capsys):
    """An unreadable cached icon is reported, deleted, and the tokens are made without an icon."""
    cache = tmp_path / "cache"
    bad_icon = cache / "icons" / "solo.png"
    bad_icon.parent.mkdir(parents=True)
    bad_icon.write_bytes(b"this is not a png")

    assert _run_cmd(["-o", str(tmp_path / "out"), "-m", str(cache), "--incremental", solo_script]) == 0

    out = _output(capsys)
    assert "Warning:" in out
    assert "could not be read" in out
    assert (cache / "tokens_solo" / "solo.png").is_file()
    assert not bad_icon.exists()
    assert SOLO_ICON_URL not in web.calls


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
    assert "Created 8 role tokens and 1 reminder tokens" in _output(capsys)


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


@pytest.mark.parametrize("option", [
    ["--role-diameter", "0"],
    ["--dpi", "-1"],
    ["--dpi", "1.5"],
    ["--reminder-diameter", "nan"],
    ["--paper-size", "100", "0"],
    ["--margin-vertical", "-0.1"],
    ["--padding", "inf"],
    ["--role-diameter", "1e308"],
    ["--paper-size", "1e308", "100"],
    ["--margin-horizontal", "1e308"],
    ["--dpi", "100000000"],
])
def test_create_rejects_bad_numbers(solo_script, capsys, option):
    """Sizes and resolution must be positive, and margins and padding must not be negative."""
    with pytest.raises(SystemExit) as e:
        _run_cmd([*option, solo_script])
    assert e.value.code == 2
    assert option[0] in capsys.readouterr().err


def test_create_accepts_zero_spacing():
    """Margins and padding may be zero."""
    with patch("sys.argv", ["botc_tokens", "create", "--padding", "0", "--margin-horizontal", "0", "script.json"]):
        args = create._parse_args()
    assert (args.padding, args.margin_horizontal) == (0.0, 0.0)


def test_create_output_dir_is_a_file_exits_1(tmp_path, web, solo_script, capsys):
    """An output path that exists but is not a directory is fatal before anything is rendered."""
    not_a_dir = tmp_path / "out"
    not_a_dir.write_text("x")

    assert _run_cmd(["-o", str(not_a_dir), solo_script]) == 1

    assert "Error:" in _output(capsys)
    assert web.calls == []


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


def test_create_zero_pixel_tokens_exit_1(tmp_path, web, solo_script, capsys):
    """Sizes that round to zero pixels at the chosen DPI are fatal."""
    options = ["--dpi", "1", "--role-diameter", "1", "--reminder-diameter", "1"]
    assert _run_cmd(["-o", str(tmp_path / "out"), *options, solo_script]) == 1
    assert "rounds to zero pixels" in _output(capsys)


def test_create_huge_page_exits_1(tmp_path, web, solo_script, capsys):
    """A page that would need an unreasonable number of pixels is fatal before rendering starts."""
    assert _run_cmd(["-o", str(tmp_path / "out"), "--dpi", "4000", solo_script]) == 1
    assert "too large" in _output(capsys)
    assert web.calls == []


def test_create_intermediate_dir_is_a_file_exits_1(tmp_path, web, solo_script, capsys):
    """An intermediate path that cannot be used as a directory is fatal with a message."""
    not_a_dir = tmp_path / "inter"
    not_a_dir.write_text("x")
    assert _run_cmd(["-o", str(tmp_path / "out"), "-m", str(not_a_dir), solo_script]) == 1
    assert "Error:" in _output(capsys)


def test_create_broken_component_font_exits_1(tmp_path, web, solo_script, component_package, capsys):
    """A component pack whose font cannot be read fails with a message instead of a traceback."""
    for font in component_package.glob("AbilityText.*"):
        font.write_text("not a font")
    assert _run_cmd(["-o", str(tmp_path / "out"), "-c", str(component_package), solo_script]) == 1
    output = _output(capsys)
    assert "Error:" in output
    assert "font" in output


def test_create_reads_intermediate_dir_and_paper_from_config(tmp_path, isolated_config, web, solo_script, capsys):
    """A local config supplies -m relative to the file and the paper type; the run prints which file it used."""
    local = isolated_config.cwd / "botc_tokens.conf"
    local.write_text("[create]\nintermediate-dir = work\npaper-type = a4\n")
    assert _run_cmd(["-o", str(tmp_path / "out"), solo_script]) == 0
    assert (isolated_config.cwd / "work" / "icons").is_dir()
    out = _output(capsys)
    assert "Using config:" in out and str(local) in out
    box = PdfReader(tmp_path / "out" / "roles.pdf").pages[0].mediabox
    assert (round(float(box.width) / 72 * 25.4), round(float(box.height) / 72 * 25.4)) == (210, 297)


def test_create_cli_paper_size_beats_config_paper_type(tmp_path, isolated_config, web, solo_script):
    """--paper-size on the command line wins over paper-type from config without a mutual-exclusion error."""
    (isolated_config.cwd / "botc_tokens.conf").write_text("[create]\npaper-type = a4\n")
    assert _run_cmd(["-o", str(tmp_path / "out"), "--paper-size", "100", "100", solo_script]) == 0
    box = PdfReader(tmp_path / "out" / "roles.pdf").pages[0].mediabox
    assert (round(float(box.width) / 72 * 25.4), round(float(box.height) / 72 * 25.4)) == (100, 100)


def test_create_config_error_exits_two(isolated_config, capsys):
    """A bad config value is reported like a bad command line argument."""
    (isolated_config.cwd / "botc_tokens.conf").write_text("[create]\ndpi = 0\n")
    with pytest.raises(SystemExit) as e:
        _run_cmd(["script.json"])
    assert e.value.code == 2
    assert "[create] dpi: '0' must be greater than zero" in capsys.readouterr().err


@pytest.fixture()
def french_web(web, test_data_dir):
    """Serve the French fixture translation alongside the official feeds."""
    web.routes[translation_url("fr")] = (test_data_dir / "official" / "fr.json").read_bytes()
    return web


def test_create_language_translates_official_text(tmp_path, french_web):
    """With --language, bare official ids are filled with translated names, abilities, and reminders."""
    script = _write_script(tmp_path / "script.json", ["washerwoman", {"id": "drunk", "team": "outsider"}, _solo()])
    out = tmp_path / "out"
    cache = tmp_path / "cache"

    assert _run_cmd(["-o", str(out), "-m", str(cache), "--language", "fr", script]) == 0

    assert translation_url("fr") in french_web.calls
    assert (out / "roles.pdf").is_file()
    tokens = cache / "tokens_script"
    assert (tokens / "washerwoman-reminder-2.png").is_file()
    assert (tokens / "drunk-reminder-1.png").is_file()


def test_resolve_official_with_language(french_web):
    """The language reaches the official data: translated gaps, untouched script text."""
    roles = create._resolve_official([Role("washerwoman"), Role("drunk", name="Mine", team="outsider")], {}, "fr")
    assert [role.name for role in roles] == ["Lavandière", "Mine"]
    assert roles[0].reminders == ["Villageois", "Wrong"]
    assert roles[1].reminders == ["Est l'Ivrogne"]


def test_create_default_language_skips_translation(tmp_path, web):
    """Without --language, no translation file is fetched."""
    script = _write_script(tmp_path / "script.json", ["imp"])

    assert _run_cmd(["-o", str(tmp_path / "out"), script]) == 0

    assert not any("botc-translations" in url for url in web.calls)


def test_create_unknown_language_exits_1(tmp_path, web, capsys):
    """A language with no translation file is fatal and points at the translation site."""
    script = _write_script(tmp_path / "script.json", ["imp"])

    assert _run_cmd(["-o", str(tmp_path / "out"), "--language", "xx", script]) == 1

    out = _output(capsys)
    assert "Error:" in out
    assert "'xx'" in out
    assert "translation.botc.app" in out


def test_create_language_without_official_roles_skips_fetch(tmp_path, web, solo_script):
    """A fully homebrew script never needs the translation file, even with --language."""
    assert _run_cmd(["-o", str(tmp_path / "out"), "--language", "xx", solo_script]) == 0
    assert not any("botc-translations" in url for url in web.calls)


def _signature(path):
    """Return a hash of an image's pixels."""
    with Image(filename=str(path)) as image:
        return image.signature


def test_create_several_scripts_share_sheets(tmp_path, web, solo_script, capsys):
    """Several scripts are rendered into their own token folders and placed together on one set of sheets."""
    out = tmp_path / "out"
    cache = tmp_path / "cache"
    other = _write_script(tmp_path / "other.json", [_solo("two", "https://example.test/two.png")])

    assert _run_cmd(["-o", str(out), "-m", str(cache), solo_script, other]) == 0

    assert (cache / "tokens_solo" / "solo.png").is_file()
    assert (cache / "tokens_other" / "two.png").is_file()
    assert len(PdfReader(out / "roles.pdf").pages) == 1
    output = _output(capsys)
    assert "Script 1 of 2:" in output
    assert "Script 2 of 2:" in output
    assert "Created 2 role tokens and 0 reminder tokens; skipped 0 roles." in output


def test_create_single_script_prints_no_script_heading(tmp_path, web, solo_script, capsys):
    """A run with one script does not print the per-script heading."""
    assert _run_cmd(["-o", str(tmp_path / "out"), solo_script]) == 0

    assert "Script 1 of" not in _output(capsys)


def test_create_components_per_script(tmp_path, web, solo_script, component_package, capsys):
    """One --components per script gives each script its own pack, and 'default' picks the built-in one."""
    cache = tmp_path / "cache"
    with Image(width=64, height=64, background=Color("red")) as background:
        background.save(filename=str(component_package / "TokenBG.png"))
    (component_package / "Leaf1.png").unlink()
    same_role = _write_script(tmp_path / "custom.json", [_solo()])

    assert _run_cmd([
        "-o", str(tmp_path / "out"), "-m", str(cache), solo_script, same_role,
        "-c", "default", "-c", str(component_package),
    ]) == 0

    default_token = cache / "tokens_solo" / "solo.png"
    custom_token = cache / "tokens_custom" / "solo.png"
    assert _signature(default_token) != _signature(custom_token)
    output = _output(capsys)
    assert f"'{component_package}' is using built-in components for: Leaf1.png" in output
    assert "Created 2 role tokens" in output  # The role both scripts share is printed for each


def test_create_one_components_applies_to_every_script(tmp_path, web, solo_script, component_package):
    """A single --components is used for all the scripts."""
    cache = tmp_path / "cache"
    with Image(width=64, height=64, background=Color("red")) as background:
        background.save(filename=str(component_package / "TokenBG.png"))
    same_role = _write_script(tmp_path / "custom.json", [_solo()])

    assert _run_cmd([
        "-o", str(tmp_path / "out"), "-m", str(cache), "-c", str(component_package), solo_script, same_role
    ]) == 0

    assert _signature(cache / "tokens_solo" / "solo.png") == _signature(cache / "tokens_custom" / "solo.png")


def test_create_components_count_mismatch_exits_1(tmp_path, web, solo_script, component_package, capsys):
    """A number of --components that is neither one nor the number of scripts is fatal before anything is fetched."""
    pack = str(component_package)

    assert _run_cmd(["-o", str(tmp_path / "out"), "-c", pack, "-c", pack, solo_script, solo_script, solo_script]) == 1

    assert "Got 2 --components for 3 scripts" in _output(capsys)
    assert web.calls == []


def test_create_cli_components_replace_config_components(tmp_path, isolated_config, web, solo_script):
    """--components on the command line replaces the config file's pack instead of adding to it."""
    (isolated_config.cwd / "botc_tokens.conf").write_text("[create]\ncomponents = missing_pack\n")

    assert _run_cmd(["-o", str(tmp_path / "out"), solo_script]) == 1
    assert _run_cmd(["-o", str(tmp_path / "out"), "-c", "default", solo_script]) == 0


def test_create_config_components_apply_to_every_script(
        tmp_path, isolated_config, web, solo_script, component_package, capsys
):
    """A pack named in a config file is used for all the scripts."""
    (component_package / "Leaf1.png").unlink()
    (isolated_config.cwd / "botc_tokens.conf").write_text(f"[create]\ncomponents = {component_package}\n")

    assert _run_cmd(["-o", str(tmp_path / "out"), solo_script, solo_script]) == 0

    assert _output(capsys).count("Using built-in components for: Leaf1.png") == 1


def test_create_same_named_scripts_get_separate_token_dirs(tmp_path, web, solo_script):
    """Scripts that resolve to the same name are numbered so their tokens do not overwrite each other."""
    cache = tmp_path / "cache"

    assert _run_cmd(["-o", str(tmp_path / "out"), "-m", str(cache), solo_script, solo_script, solo_script]) == 0

    for name in ("tokens_solo", "tokens_solo_2", "tokens_solo_3"):
        assert (cache / name / "solo.png").is_file()


def test_create_bad_later_script_stops_before_rendering(tmp_path, web, solo_script, capsys):
    """A script that cannot be read stops the run before any icon is fetched or sheet written, and is named."""
    out = tmp_path / "out"
    not_a_script = _write_script(tmp_path / "object.json", {})

    assert _run_cmd(["-o", str(out), solo_script, not_a_script]) == 1

    output = _output(capsys)
    assert f"{not_a_script}: Unrecognized script format" in output
    assert web.calls == []
    assert not (out / "roles.pdf").exists()


def test_create_later_script_without_roles_writes_no_sheets(tmp_path, web, solo_script, capsys):
    """A later script with no usable roles stops the run without sheets, naming the script."""
    out = tmp_path / "out"
    empty = _write_script(tmp_path / "empty.json", ["notarole"])

    assert _run_cmd(["-o", str(out), solo_script, empty]) == 1

    assert f"No roles left to create tokens for in {empty}" in _output(capsys)
    assert not (out / "roles.pdf").exists()


def test_create_scripts_and_components_can_be_interleaved(tmp_path, web, solo_script, component_package, capsys):
    """Each --components may follow its script; packs are still matched to the scripts by order."""
    cache = tmp_path / "cache"
    (component_package / "Leaf1.png").unlink()
    other = _write_script(tmp_path / "other.json", [_solo()])

    assert _run_cmd([
        solo_script, "-c", "default", other, "-c", str(component_package), "-o", str(tmp_path / "out"), "-m", str(cache)
    ]) == 0

    assert (cache / "tokens_solo" / "solo.png").is_file()
    assert (cache / "tokens_other" / "solo.png").is_file()
    assert f"'{component_package}' is using built-in components for: Leaf1.png" in _output(capsys)


def test_create_script_names_differing_only_by_case_get_separate_token_dirs(tmp_path, web):
    """Names that differ only by case would be one directory on some filesystems, so the later one is numbered."""
    cache = tmp_path / "cache"
    upper = _write_script(tmp_path / "upper.json", [{"id": "_meta", "name": "Homebrew"}, _solo()])
    lower = _write_script(tmp_path / "lower.json", [{"id": "_meta", "name": "homebrew"}, _solo()])

    assert _run_cmd(["-o", str(tmp_path / "out"), "-m", str(cache), upper, lower]) == 0

    assert sorted(path.name for path in cache.iterdir()) == ["icons", "tokens_Homebrew", "tokens_homebrew_2"]


def test_create_incremental_does_not_share_icons_between_scripts_in_one_run(tmp_path, web, test_data_dir, solo_script):
    """With --incremental, a later script's role with the same id but different art still gets its own icon."""
    cache = tmp_path / "cache"
    web.routes["https://example.test/two.png"] = (test_data_dir / "icons" / "1.png").read_bytes()
    other_art = _write_script(tmp_path / "other.json", [_solo(image="https://example.test/two.png")])
    same_art = _write_script(tmp_path / "same.json", [_solo()])

    assert _run_cmd([
        "-o", str(tmp_path / "out"), "-m", str(cache), "--incremental", solo_script, same_art, other_art
    ]) == 0

    assert web.calls.count(SOLO_ICON_URL) == 1  # The second script shares the first one's artwork, so it is reused
    assert "https://example.test/two.png" in web.calls
    assert _signature(cache / "tokens_solo" / "solo.png") == _signature(cache / "tokens_same" / "solo.png")
    assert _signature(cache / "tokens_solo" / "solo.png") != _signature(cache / "tokens_other" / "solo.png")
