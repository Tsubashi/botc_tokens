"""Create printable sheets based on a script json file."""
import argparse
import json
from pathlib import Path
import sys

from rich import print
from rich.live import Live

from ..helpers.printable import Printable
from ..helpers.progress_group import setup_progress_group


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="botc_tokens group",
        description='Create printable sheets based on a script json file.'
    )
    parser.add_argument('script', type=str,
                        help='the json file or directory containing the script info.')
    parser.add_argument('--token-dir', type=str, default='tokens',
                        help="Name of the directory in which to find the token images. (Default: 'tokens')")
    parser.add_argument('-o', '--output-dir', type=str, default='printables',
                        help="Name of the directory in which to output the sheets. (Default: 'printables')")
    parser.add_argument('--fixed-role-size', type=int, default=None,
                        help="The radius (in pixels) to allocate per role tokens. "
                             "(Default: The first token's largest dimension)")
    parser.add_argument('--fixed-reminder-size', type=int, default=None,
                        help="The radius (in pixels) to allocate per reminder tokens. "
                             "(Default: The first token's largest dimension)")
    parser.add_argument('--padding', type=int, default=0,
                        help="The padding (in pixels) between tokens. (Default: 0)")
    parser.add_argument('--paper-width', type=int, default=2402,
                        help="The width (in pixels) of the paper to use for the tokens. (Default: 2402)")
    parser.add_argument('--paper-height', type=int, default=3152,
                        help="The height (in pixels) of the paper to use for the tokens. (Default: 3152)")
    args = parser.parse_args(sys.argv[2:])
    return args


def run():
    """Create printable sheets based on a script json file."""
    args = _parse_args()
    # Find all the token images
    token_files = Path(args.token_dir).rglob("*.png")
    role_images = []
    reminder_images = []
    print("[green]Finding Token Images...[/]")
    for img_file in token_files:
        if "Reminder" in img_file.name:
            reminder_images.append(img_file)
        else:
            role_images.append(img_file)

    if not role_images and not reminder_images:
        print("[yellow]Warning:[/] No token images found.")

    # Read the script json file
    print(f"[green]Reading {args.script}...[/]")
    script_path = Path(args.script)
    script = []
    if script_path.is_dir():
        script = [file.stem for file in script_path.rglob("*.png") if "Reminder" not in file.name]
    else:
        with open(args.script, "r") as f:
            script = json.load(f)

    # Create the printable sheets
    print(f"[green]Creating sheets in {args.output_dir}...[/]", end="")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    progress_group, overall_progress, step_progress = setup_progress_group()

    with Live(progress_group):
        overall_progress.add_task("Creating Sheets", total=None)
        step_task = step_progress.add_task("Adding roles")
        role_page = Printable(
            output_dir,
            basename="roles",
            page_width=args.paper_width,
            page_height=args.paper_height,
            padding=args.padding,
            diameter=args.fixed_role_size
        )
        reminder_page = Printable(
            output_dir,
            basename="reminders",
            page_width=args.paper_width,
            page_height=args.paper_height,
            padding=args.padding,
            diameter=args.fixed_role_size
        )
        for role in script:
            if isinstance(role, dict):
                continue  # Skip metadata
            role_name = role.lower().strip()
            step_progress.update(step_task, description=f"Adding {role_name.title()}")
            # See if we have tokens for this role
            role_file = next((t for t in role_images if role_name in t.name.lower().replace("'", "")), None)
            reminder_files = (t for t in reminder_images if t.name.lower().replace("'", "").startswith(role_name))
            if not role_file:
                print(f"[yellow]Warning:[/] No token found for {role_name}")
                continue
            role_page.add_token(role_file)
            for reminder in reminder_files:
                reminder_page.add_token(reminder)

        # Save the last pages
        step_progress.update(step_task, description="Saving remaining pages")
        role_page.save_page()
        reminder_page.save_page()
