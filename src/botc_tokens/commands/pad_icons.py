"""Enable users to pad tightly cropped icons to match the official icons."""
# Standard Library
import argparse
from pathlib import Path
import sys

# Third Party
from rich import print
from rich.live import Live
from rich.markup import escape
from wand.exceptions import WandException
from wand.image import Image

# Application Specific
from ..helpers.icons import is_blank, pad_icon
from ..helpers.progress_group import setup_progress_group


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="botc_tokens pad-icons",
        description="Find all icons in a folder and add extra space to match what the official icons do (if needed).")
    parser.add_argument("target_directory", type=str, help="The directory containing the icons.")
    parser.add_argument("-i", "--in-place", action="store_true", help="Overwrite the original files.")
    return parser.parse_args(sys.argv[2:])


def _pad_file(icon_path: Path, in_place: bool) -> None:
    """Pad one icon file if it needs it, warning instead of failing if it is blank or unreadable."""
    try:
        with Image(filename=str(icon_path)) as image:
            padded = pad_icon(image)
            if padded is None:
                if is_blank(image):
                    print(f"[yellow]Warning:[/] {escape(str(icon_path))} is fully transparent, skipping.")
                return
            output_path = icon_path
            if not in_place:
                output_path = icon_path.with_name(f"{icon_path.stem}_padded{icon_path.suffix}")
            with padded:
                padded.save(filename=str(output_path))
    except WandException as e:
        print(f"[yellow]Warning:[/] Could not read {escape(str(icon_path))} ({escape(str(e))}), skipping.")


def run():
    """Pad the tightly cropped icons found in a directory."""
    args = _parse_args()
    target = Path(args.target_directory)
    if not target.is_dir():
        print(f"[red]Error:[/] {escape(str(target))} is not a directory.")
        return 1

    icons = sorted(p for pattern in ("*.png", "*.webp") for p in target.rglob(pattern))
    if not icons:
        print("[red]Error:[/] No icons found.")
        return 1

    progress_group, overall_progress, step_progress = setup_progress_group()
    with Live(progress_group):
        overall_task = overall_progress.add_task("Padding icons...", total=len(icons))
        step_task = step_progress.add_task("Reading icons...")
        for icon_path in icons:
            step_progress.update(step_task, description=f"Checking {escape(icon_path.name)}")
            _pad_file(icon_path, args.in_place)
            overall_progress.update(overall_task, advance=1)
    return 0
