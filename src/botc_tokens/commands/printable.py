import argparse
from pathlib import Path
from rich.progress import Progress, TimeElapsedColumn, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn, Live, Group
import json
from rich import print
from ..helpers.printable import Printable


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="botc_tokens printable",
        description='Create printable sheets based on a script json file.'
    )
    parser.add_argument('script_json', type=str,
                        help='the json file containing the script info.')
    parser.add_argument('--token-dir', type=str, default='tokens',
                        help="Name of the directory in which to find the token images. (Default: 'tokens')")
    parser.add_argument('-o', '--output-dir', type=str, default='printables',
                        help="Name of the directory in which to output the sheets. (Default: 'printables')")
    args = parser.parse_args()
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

    # Read the script json file
    print(f"[green]Reading {args.script_json}...[/]")
    with open(args.script_json, "r") as f:
        script = json.load(f)

    # Create the printable sheets
    print(f"[green]Creating sheets in {args.output_dir}...[/]", end="")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Overall progress bar
    overall_progress = Progress(
        TimeElapsedColumn(), BarColumn(), TextColumn("{task.description}"), TimeRemainingColumn()
    )

    # Progress bars for single steps (will be hidden when step is done)
    step_progress = Progress(
        TextColumn("  |-"),
        TextColumn("[bold purple]{task.description}"),
        SpinnerColumn("simpleDots"),
    )

    # Group the progress bars
    progress_group = Group(overall_progress, step_progress)

    with Live(progress_group):
        overall_progress.add_task("Creating Sheets", total=2)
        step_task = step_progress.add_task("Adding roles")
        role_page = Printable(output_dir, "roles")
        reminder_page = Printable(output_dir, "reminders")
        for role in script:
            if isinstance(role, dict):
                continue  # Skip metadata
            role_name = role.lower().replace("_", " ").strip()
            step_progress.update(step_task, description=f"Adding {role_name.title()}")
            # See if we have tokens for this role
            role_file = next((t for t in role_images if role_name in t.name.lower().replace("'","")), None)
            reminder_files = (t for t in reminder_images if t.name.lower().replace("'","").startswith(role_name))
            if not role_file:
                print(f"[yellow]No token found for {role_name}[/]")
                continue
            role_page.add_token(role_file)
            for reminder in reminder_files:
                reminder_page.add_token(reminder)

        # Save the last pages
        step_progress.update(step_task, description=f"Saving pages")
        role_page.save_page()
        reminder_page.save_page()
