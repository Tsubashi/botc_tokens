"""Convert an old `inputs/<script>/<team>/<role>.json` tree into TPI script JSON files plus a shared icons folder."""
# Standard Library
import argparse
import json
from pathlib import Path
import sys

# Third Party
from rich import print
from rich.markup import escape
from wand.exceptions import WandException
from wand.image import Image

# Application Specific
from ..helpers.role import normalize_id
from ..helpers.text_tools import format_filename


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="botc_tokens migrate",
        description="Convert old directory structures to the new format.")
    parser.add_argument('-i', '--input', type=str, required=True, dest="input_dir",
                        help="The old directory to convert.")
    parser.add_argument('output_dir', type=str, default=".", nargs="?",
                        help='The directory in which to output the new JSON and intermediates. (Default: ".")')
    return parser.parse_args(sys.argv[2:])


def find_scripts(input_dir: Path) -> list[tuple[str, list[Path]]]:
    """Find the scripts in an old input tree.

    Args:
        input_dir: The old input directory.

    Returns:
        A list of (script name, sorted role JSON paths). Each immediate child directory holding role JSON beneath it is
        a script. If the directory itself directly holds role JSON, it is a single script named after the directory.
    """
    direct = sorted(input_dir.glob("*.json"))
    if direct:
        return [(input_dir.name, direct)]
    scripts = []
    for child in sorted(p for p in input_dir.iterdir() if p.is_dir()):
        files = sorted(child.rglob("*.json"))
        if files:
            scripts.append((child.name, files))
    return scripts


def _convert_icon(source: Path, target: Path):
    """Write the source image to the target as a PNG."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image(filename=str(source)) as image:
        image.format = "png"
        image.save(filename=str(target))


def _migrate_icon(role_json: Path, data: dict, role_id: str, icons_dir: Path) -> str | None:
    """Convert a role's icon into the icons directory, returning its script-relative path or None (with a warning)."""
    icon_name = data.get("icon")
    if not isinstance(icon_name, str) or not icon_name:
        print(f"[yellow]Warning:[/] {escape(str(data['id']))} has no icon; writing the role without an image.")
        return None
    icon = role_json.parent / icon_name
    if not icon.is_file():
        print(f"[yellow]Warning:[/] Icon for {escape(str(data['id']))} not found ({escape(str(icon))}); "
              "writing the role without an image.")
        return None
    try:
        _convert_icon(icon, icons_dir / f"{role_id}.png")
    except WandException as e:
        print(f"[yellow]Warning:[/] Could not convert the icon {escape(str(icon))} for {escape(str(data['id']))} "
              f"({escape(str(e))}); writing the role without an image.")
        return None
    return f"icons/{role_id}.png"


def convert_role(role_json: Path, icons_dir: Path, night_counters: dict[str, int]) -> dict | None:
    """Convert one old role JSON into a TPI role object, converting its icon.

    Args:
        role_json: The old role JSON file.
        icons_dir: The directory to which the icon is written as `<id>.png`.
        night_counters: Per-script counters (keys `firstNight` and `otherNight`), updated in place.

    Returns:
        The TPI role object, or None if the JSON could not be read.
    """
    try:
        data = json.loads(role_json.read_text(encoding="utf-8"))
        role_id = normalize_id(data["id"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print(f"[yellow]Warning:[/] Skipping {escape(str(role_json))}: {escape(str(e))}")
        return None
    role = {
        "id": data["id"],
        "name": data.get("name", data["id"]),
        "team": str(data.get("type") or "unknown").lower(),
        "ability": data.get("ability", ""),
        "reminders": data.get("reminders", []),
        "setup": bool(data.get("affects_setup", False)),
    }
    for flag, key in (("first_night", "firstNight"), ("other_nights", "otherNight")):
        if data.get(flag):
            night_counters[key] = night_counters.get(key, 0) + 1
            role[key] = night_counters[key]
    image = _migrate_icon(role_json, data, role_id, icons_dir)
    if image is not None:
        role["image"] = image
    return role


def write_script(name: str, roles: list[dict], output_dir: Path) -> Path:
    """Write a TPI script file.

    Args:
        name: The script name.
        roles: The role objects, in order.
        output_dir: The directory in which to write the file.

    Returns:
        The path of the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{format_filename(name)}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump([{"id": "_meta", "name": name}, *roles], f, indent=2)
    return path


def run():
    """Convert the old input tree into TPI scripts."""
    args = _parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    if not input_dir.is_dir():
        print(f"[red]Error:[/] Input directory {escape(str(input_dir))} does not exist.")
        return 1
    scripts = find_scripts(input_dir)
    if not scripts:
        print(f"[red]Error:[/] No role JSON files found in {escape(str(input_dir))}.")
        return 1

    for name, files in scripts:
        counters: dict[str, int] = {}
        roles = [r for r in (convert_role(f, output_dir / "icons", counters) for f in files) if r is not None]
        path = write_script(name, roles, output_dir)
        print(f"[green]Wrote {escape(str(path))} ({len(roles)} roles).[/]")
    return 0
