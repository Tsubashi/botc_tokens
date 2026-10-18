"""Create printable sheets based on a script json file."""
# Standard Library
import argparse
import json
from pathlib import Path
import re
import sys

# Third Party
from jsonschema import validate, ValidationError
from rich import print
from rich.live import Live

# Application Specific
from .. import data_dir
from ..helpers.printable import Printable
from ..helpers.progress_group import setup_progress_group


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="botc_tokens group",
        description='Create printable sheets based on a script json file.'
    )
    parser.add_argument('script', type=str,
                        help='the json file or directory containing the script info.')
    token_dir_default = 'tokens'
    parser.add_argument('--token-dir', type=str, default=token_dir_default,
                        help="Name of the directory in which to find the token images. Ignored if script is a "
                             f"directory. (Default: {token_dir_default})")
    output_dir_default = 'printables'
    parser.add_argument('-o', '--output-dir', type=str, default=output_dir_default,
                        help=f"Name of the directory in which to output the sheets. (Default: {output_dir_default})")
    parser.add_argument('--fixed-role-size', type=int, default=None,
                        help="The radius (in pixels) to allocate per role tokens. "
                             "(Default: The first token's largest dimension)")
    parser.add_argument('--fixed-reminder-size', type=int, default=None,
                        help="The radius (in pixels) to allocate per reminder tokens. "
                             "(Default: The first token's largest dimension)")
    margin_default = 74
    parser.add_argument('--margin-horizontal', type=int, default=margin_default,
                        help=f"The margin (in pixels) between the left/right edge of the paper and the tokens. "
                             f"(Default: {margin_default})")
    parser.add_argument('--margin-vertical', type=int, default=margin_default,
                        help=f"The margin (in pixels) between the top/bottom of the paper and the tokens. "
                             f"(Default: {margin_default})")
    padding_default = 0
    parser.add_argument('--padding', type=int, default=padding_default,
                        help=f"The padding (in pixels) between tokens. (Default: {padding_default})")
    paper_width_default = 2550
    parser.add_argument('--paper-width', type=int, default=paper_width_default,
                        help="The width (in pixels) of the paper to use for the tokens. "
                             f"(Default: {paper_width_default})")
    paper_height_default = 3300
    parser.add_argument('--paper-height', type=int, default=paper_height_default,
                        help="The height (in pixels) of the paper to use for the tokens. "
                             f"(Default: {paper_height_default})")
    parser.add_argument('--duplicates', type=str, default=None,
                        help="A json file containing the number of duplicates to add for each role.")
    parser.add_argument("--grid", action="store_true", help="Use a grid layout instead of close packing.")
    args = parser.parse_args(sys.argv[2:])

    return args


def run():
    """Create printable sheets based on a script json file."""
    args = _parse_args()

    # Check to make sure that the margin leaves enough room for the tokens
    if args.paper_width - (args.margin_horizontal * 2) <= 0:
        print("[red]Error:[/] The horizontal margin is too large for the paper width.")
        return 1
    if args.paper_height - (args.margin_vertical * 2) <= 0:
        print("[red]Error:[/] The vertical margin is too large for the paper height.")
        return 1

    # Ensure the script file/directory exists

    # Read the script json file
    print(f"[green]Reading {args.script}...[/]")
    try:
        script = load_script(args)
    except RuntimeError as e:
        print(f"[red]Error:[/] Unable to load script {args.script}: {str(e)}")
        return 1

    # Find all the token images
    token_files = Path(args.token_dir).rglob("*.png")
    print("[green]Finding Token Images...[/]")
    role_images, reminder_images = find_images(token_files)

    if not role_images and not reminder_images:
        print("[yellow]Warning:[/] No token images found.")

    # Load in the duplicate lists
    try:
        duplicates, duplicates_overrides = load_duplicates(args.duplicates)
    except ValidationError as e:
        print(f"[red]Error:[/] {args.duplicates} does not match the schema: {e}")
        return 1

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
            margin_vertical=args.margin_vertical,
            margin_horizontal=args.margin_horizontal,
            padding=args.padding,
            diameter=args.fixed_role_size,
            close_packing=not args.grid
        )
        reminder_page = Printable(
            output_dir,
            basename="reminders",
            page_width=args.paper_width,
            page_height=args.paper_height,
            margin_vertical=args.margin_vertical,
            margin_horizontal=args.margin_horizontal,
            padding=args.padding,
            diameter=args.fixed_reminder_size,
            close_packing=not args.grid
        )
        process_tokens(duplicates, duplicates_overrides, reminder_images, reminder_page, role_images, role_page, script,
                       step_progress, step_task)

        # Save the last pages
        step_progress.update(step_task, description="Saving pages")
        role_page.write()
        reminder_page.write()

        # Clean up
        role_page.close()
        reminder_page.close()


def process_tokens(duplicates, duplicates_overrides, reminder_images, reminder_page, role_images, role_page, script,
                   step_progress, step_task):
    """Do all the processing.

    If we are being honest, this function exists separate from the run() function only to decrease its complexity.
    """
    for role in script:
        if isinstance(role, dict):
            continue  # Skip metadata
        # Remove underscores and make lowercase for matching
        role_name = role.lower().replace("_", "").strip()
        step_progress.update(step_task, description=f"Adding {role_name.title()}")

        # See if we have a matching token image
        role_file = None
        for imgfile in role_images:
            # Remove underscores, apostrophes, and make lowercase for matching
            img_name = imgfile.stem.lower().replace("'", "").replace("_", "")
            if role_name == img_name:
                role_file = imgfile
                break

        # Find any matching reminder images
        reminder_files = []
        for reminder_img in reminder_images:
            # Remove underscores, apostrophes, and make lowercase for matching
            r_img_name = reminder_img.stem.lower().replace("'", "").replace("_", "")
            reminder_regex = re.compile(f"{role_name}-reminder.*")
            if reminder_regex.match(r_img_name):
                reminder_files.append(reminder_img)

        if not role_file:
            print(f"[yellow]Warning:[/] No token found for {role_name}")
            continue
        # Check if we should add duplicate tokens
        token_count = 1
        if role_name in duplicates_overrides:
            token_count = duplicates_overrides[role_name]
        elif role_name in duplicates:
            token_count = duplicates[role_name]

        for _ in range(token_count):
            role_page.add_token(role_file)
        for reminder in reminder_files:
            reminder_page.add_token(reminder)


def load_duplicates(user_duplicates):
    """Load the known duplicates and user overrides."""
    duplicates_overrides = {}
    with open(data_dir / "known_duplicates.json", "r") as f:
        duplicates = json.load(f)
    if user_duplicates:
        with open(user_duplicates, "r") as f:
            json_data = json.load(f)
            validate(json_data, json.load(open(data_dir / "duplicate_schema.json")))
            duplicates_overrides = json_data
    return duplicates, duplicates_overrides


def find_images(token_files):
    """Populate role and reminder lists with the images we find."""
    role_images = []
    reminder_images = []
    for img_file in token_files:
        if "Reminder" in img_file.name:
            reminder_images.append(img_file)
        else:
            role_images.append(img_file)
    return role_images, reminder_images


def load_script(args):
    """Load the script from the file or directory."""
    script_path = Path(args.script)
    if not script_path.exists():
        raise RuntimeError(f"File or directory {args.script} does not exist.")
    script = []
    if script_path.is_dir():
        script = [file.stem for file in script_path.rglob("*.png") if "Reminder" not in file.name]
        args.token_dir = str(script_path)
    else:
        with open(args.script, "r") as f:
            script = json.load(f)
    return script
