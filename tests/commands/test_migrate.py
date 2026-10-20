"""Tests for the migrate command."""
# Standard Library
import json
from unittest.mock import patch

# Third Party
from pypdf import PdfReader
import pytest
from wand.color import Color
from wand.image import Image

# Application Specific
from botc_tokens.commands import create, migrate


def _run_cmd(arg_list):
    """Run the migrate command with the given arguments and return its exit code."""
    with patch("sys.argv", ["botc_tokens", "migrate", *arg_list]):
        return migrate.run()


def _save_image(path, fmt):
    """Write a small solid image in the given format."""
    with Image(width=10, height=10, background=Color("red")) as image:
        image.format = fmt
        image.save(filename=str(path))


def _write_role(directory, role_id, **extra):
    """Write an old-format role JSON and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    data = {"id": role_id, "name": role_id.title(), "ability": "Does a thing.", "type": "Townsfolk",
            "icon": f"{role_id}.png", "first_night": False, "other_nights": False, "reminders": [],
            "affects_setup": False, "home_script": "x"}
    data.update(extra)
    path = directory / f"{role_id}.json"
    path.write_text(json.dumps(data))
    return path


def _old_tree(root):
    """Build an old input tree with two scripts."""
    script_a = root / "Script A"
    _write_role(script_a / "townsfolk", "one", first_night=True, reminders=["Mark"], affects_setup=True)
    _save_image(script_a / "townsfolk" / "one.png", "png")
    _write_role(script_a / "demon", "two", type="Demon", icon="two.jpg", other_nights=True)
    _save_image(script_a / "demon" / "two.jpg", "jpeg")
    _write_role(root / "Script B" / "outsider", "three", type=None)
    (script_a / "townsfolk" / "bad.json").write_text("{not json")
    return root


def test_migrate_writes_one_json_per_script(tmp_path, capsys):
    """Each script directory becomes one TPI file, with icons converted to PNG."""
    inputs = _old_tree(tmp_path / "inputs")
    out = tmp_path / "out"

    assert _run_cmd(["-i", str(inputs), str(out)]) == 0

    script_a = json.loads((out / "Script_A.json").read_text())
    assert script_a[0] == {"id": "_meta", "name": "Script A"}
    assert [r["id"] for r in script_a[1:]] == ["two", "one"]  # sorted path order: demon/ before townsfolk/
    roles = {r["id"]: r for r in script_a[1:]}
    assert roles["one"] == {"id": "one", "name": "One", "team": "townsfolk", "ability": "Does a thing.",
                            "reminders": ["Mark"], "setup": True, "firstNight": 1, "image": "icons/one.png"}
    assert roles["two"]["otherNight"] == 1
    assert "firstNight" not in roles["two"]
    assert roles["two"]["image"] == "icons/two.png"
    script_b = json.loads((out / "Script_B.json").read_text())
    assert script_b[1]["team"] == "unknown"
    assert "image" not in script_b[1]
    for name in ("one", "two"):
        with Image(filename=str(out / "icons" / f"{name}.png")) as image:
            assert image.format == "PNG"
    output = capsys.readouterr().out.replace("\n", "")
    assert output.count("Warning:") == 2
    assert "bad.json" in output
    assert "three" in output


def test_migrate_icon_problems_warn_and_continue(tmp_path, capsys):
    """A null icon, a corrupt icon, and markup in an id are warned about; the roles are written without images."""
    inputs = tmp_path / "Odd Script"
    _write_role(inputs, "nullicon", icon=None)
    _write_role(inputs, "corrupt")
    (inputs / "corrupt.png").write_bytes(b"this is not a png")
    _write_role(inputs, "markup", id="[/x]", icon="missing.png")
    _write_role(inputs, "zgood")
    _save_image(inputs / "zgood.png", "png")
    out = tmp_path / "out"

    assert _run_cmd(["-i", str(inputs), str(out)]) == 0

    roles = {r["id"]: r for r in json.loads((out / "Odd_Script.json").read_text())[1:]}
    assert sorted(roles) == ["[/x]", "corrupt", "nullicon", "zgood"]
    assert all("image" not in roles[name] for name in ("[/x]", "corrupt", "nullicon"))
    assert roles["zgood"]["image"] == "icons/zgood.png"
    assert not (out / "icons" / "corrupt.png").exists()
    output = capsys.readouterr().out.replace("\n", "")
    assert output.count("Warning:") == 3
    assert "nullicon has no icon" in output
    assert "Could not convert the icon" in output
    assert "Icon for [/x] not found" in output


def test_migrate_help_matches_spec(capsys):
    """The help text matches the documented command-line surface."""
    with pytest.raises(SystemExit):
        _run_cmd(["--help"])
    help_text = " ".join(capsys.readouterr().out.split())
    for expected in (
        "usage: botc_tokens migrate [-h] -i INPUT_DIR [output_dir]",
        "Convert old directory structures to the new format.",
        'output_dir The directory in which to output the new JSON and intermediates. (Default: ".")',
        "-i INPUT_DIR, --input INPUT_DIR The old directory to convert.",
    ):
        assert expected in help_text


def test_migrate_flat_input_dir(tmp_path):
    """JSON directly in the input directory forms a single script named after it."""
    inputs = tmp_path / "Flat Script"
    _write_role(inputs, "one")
    _save_image(inputs / "one.png", "png")
    out = tmp_path / "out"

    assert _run_cmd(["-i", str(inputs), str(out)]) == 0

    assert [p.name for p in out.glob("*.json")] == ["Flat_Script.json"]


def test_migrate_missing_input_exits_1(tmp_path, capsys):
    """A missing input directory is an error."""
    assert _run_cmd(["-i", str(tmp_path / "nope"), str(tmp_path / "out")]) == 1
    assert "does not exist" in capsys.readouterr().out.replace("\n", "")


def test_migrate_no_roles_exits_1(tmp_path, capsys):
    """An input directory with no role JSON is an error."""
    (tmp_path / "inputs" / "Empty").mkdir(parents=True)
    (tmp_path / "inputs" / "file.txt").write_text("x")
    assert _run_cmd(["-i", str(tmp_path / "inputs"), str(tmp_path / "out")]) == 1
    assert "No role JSON" in capsys.readouterr().out.replace("\n", "")


def test_migrated_script_feeds_create(tmp_path, fake_web):
    """A migrated script, with its relative icon paths, can be rendered by create."""
    inputs = _old_tree(tmp_path / "inputs")
    out = tmp_path / "out"
    assert _run_cmd(["-i", str(inputs), str(out)]) == 0
    sheets = tmp_path / "sheets"

    with patch("sys.argv", ["botc_tokens", "create", "-o", str(sheets), "-m", str(tmp_path / "cache"),
                            str(out / "Script_A.json")]):
        assert create.run() == 0

    assert len(PdfReader(sheets / "roles.pdf").pages) >= 1


def test_migrate_output_is_a_file_exits_1(tmp_path, capsys):
    """An output path that is an existing file is reported, not a traceback."""
    inputs = tmp_path / "Flat"
    _write_role(inputs, "one")
    not_a_dir = tmp_path / "out"
    not_a_dir.write_text("x")
    assert _run_cmd(["-i", str(inputs), str(not_a_dir)]) == 1
    assert "Error:" in capsys.readouterr().out.replace("\n", "")


def test_migrate_icon_dir_is_a_file_exits_1(tmp_path, capsys):
    """Failing to create the icons directory is reported, not a traceback."""
    inputs = tmp_path / "Flat"
    _write_role(inputs, "one")
    _save_image(inputs / "one.png", "png")
    out = tmp_path / "out"
    out.mkdir()
    (out / "icons").write_text("x")
    assert _run_cmd(["-i", str(inputs), str(out)]) == 1
    assert "Error:" in capsys.readouterr().out.replace("\n", "")


def test_migrate_deeply_nested_role_json_is_skipped(tmp_path, capsys):
    """A role JSON nested too deeply to decode is skipped with a warning."""
    inputs = tmp_path / "Flat"
    _write_role(inputs, "one", icon=None)
    (inputs / "deep.json").write_text("[" * 100000 + "]" * 100000)
    assert _run_cmd(["-i", str(inputs), str(tmp_path / "out")]) == 0
    output = capsys.readouterr().out.replace("\n", "")
    assert "Skipping" in output and "deep.json" in output
