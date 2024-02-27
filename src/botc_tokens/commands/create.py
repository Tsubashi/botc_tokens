import json
import sys
from pathlib import Path
import argparse
from rich import print
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.live import Live
from rich.console import Group
from wand.image import Image
from ..helpers.text_tools import curved_text_to_image, fit_ability_text
from .. import component_path as default_component_path


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="botc_tokens create",
        description='Create token images to match json files in a directory tree.')
    parser.add_argument('search_dir', type=str, default="inputs", nargs="?",
                        help='The top level directory in which to begin the search.')
    parser.add_argument('output_dir', type=str, default='tokens', nargs="?",
                        help="Name of the directory in which to output the tokens. (Default: 'tokens')")
    parser.add_argument('--component-dir', type=str, nargs="?", default=default_component_path,
                        help="The directory in which to find the token components files. (leaves, backgrounds, etc.)")
    args = parser.parse_args(sys.argv[2:])
    return args


def run():
    """Use JSON to create a set of tokens."""
    args = _parse_args()
    json_files = Path(args.search_dir).rglob("*.json")
    roles = []
    print("[green]Finding Roles...[/]")
    for json_file in json_files:
        with open(json_file, "r") as f:
            data = json.load(f)
        # Rewrite the icon path to be relative to our working directory
        data['icon'] = str(json_file.parent / data.get('icon'))
        roles.append(data)
    print(f"[green]Creating tokens in {args.output_dir}...[/]", end="")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load the component images
    component_path = Path(args.component_dir)
    token_bg = Image(filename=component_path / "TokenBG.png")
    reminder_bg = Image(filename=component_path / "ReminderBG.png")
    leaves = [
        Image(filename=component_path / "Leaf1.png"),
        Image(filename=component_path / "Leaf2.png"),
        Image(filename=component_path / "Leaf3.png"),
        Image(filename=component_path / "Leaf4.png"),
        Image(filename=component_path / "Leaf5.png"),
        Image(filename=component_path / "Leaf6.png"),
        Image(filename=component_path / "Leaf7.png"),
    ]
    left_leaf = Image(filename=component_path / "LeafLeft.png")
    right_leaf = Image(filename=component_path / "LeafRight.png")
    setup_flower = Image(filename=component_path / "SetupFlower.png")

    # Create the tokens
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
        output_path = Path(args.output_dir)
        overall_task = overall_progress.add_task("Creating Tokens...", total=len(roles))
        step_task = step_progress.add_task("Reading roles...")
        for role in roles:
            # Make sure our target directory exists
            role_output_path = output_path / role['home_script'] / role['type']
            role_output_path.mkdir(parents=True, exist_ok=True)

            # Skip if the token already exists
            token_output_path = role_output_path / f"{role['name']}.png"
            if token_output_path.exists():
                continue

            # Composite the various pieces of the token.
            step_progress.update(step_task, description=f"Creating Token for: {role.get('name')}")
            token = token_bg.clone()
            icon = Image(filename=role['icon'])
            token_icon = icon.clone()
            token_icon.transform(resize=f"{token_bg.width*0.7}x{reminder_bg.height*0.7}^")

            # Check if we have reminders. If so, create them.
            reminder_icon = icon.clone()
            reminder_icon.transform(resize=f"{reminder_bg.width}x{reminder_bg.height}>")
            # Add leaves to the big token
            for leaf in leaves[:len(role['reminders'])]:
                token.composite(leaf, left=0, top=0)

            # Create the reminder tokens
            for reminder_text in role['reminders']:
                reminder_name = f"{role['name']}-Reminder-{reminder_text.replace(':', '-')}"
                reminder_output_path = role_output_path / f"{reminder_name}.png"
                duplicate_counter = 1
                while reminder_output_path.exists():
                    duplicate_counter += 1
                    reminder_output_path = role_output_path / f"{reminder_name}-{duplicate_counter}.png"

                step_progress.update(step_task, description=f"Creating Token for: {role.get('name')}")
                reminder = reminder_bg.clone()
                reminder_icon_x = (reminder.width - reminder_icon.width) // 2
                reminder_icon_y = (reminder.height - reminder_icon.height - int(reminder.height*0.15)) // 2
                reminder.composite(reminder_icon, left=reminder_icon_x, top=reminder_icon_y)
                # Add the reminder text
                text_img = curved_text_to_image(reminder_text.title(), "reminder", reminder_icon.width)
                text_x = (reminder.width - text_img.width) // 2
                text_y = (reminder.height - text_img.height - int(reminder_icon.height*0.05))
                reminder.composite(text_img, left=text_x, top=text_y)
                text_img.close()

                # Resize to 319x319 since that will yield a 27mm token when printed at 300dpi
                # This allows for a 2mm bleed
                reminder.resize(width=319, height=319)

                # Save the reminder token
                reminder.save(filename=reminder_output_path)
                reminder.close()
            reminder_icon.close()

            # Determine where to place the icon
            icon_x = (token.width - token_icon.width) // 2
            icon_y = (token.height - token_icon.height + int(token.height * 0.22)) // 2
            token.composite(token_icon, left=icon_x, top=icon_y)
            token_icon.close()

            # Check for modifiers
            if role.get('first_night'):
                token.composite(left_leaf, left=0, top=0)
            if role.get('other_nights'):
                token.composite(right_leaf, left=0, top=0)
            if role.get('affects_setup'):
                token.composite(setup_flower, left=0, top=0)

            # Add ability text to the token
            step_progress.update(step_task, description=f"Creating Token for: {role.get('name')}")
            ability_text_img = fit_ability_text(
                text=role['ability'],
                font_size=int(token.height*0.055),
                first_line_width=int(token.width*.52),
                step=int(token.width*.1)
            )
            ability_text_x = (token.width - ability_text_img.width) // 2
            token.composite(ability_text_img, left=ability_text_x, top=int(token.height*0.09))
            ability_text_img.close()

            # Add the role name to the token
            text_img = curved_text_to_image(role['name'], "role", token.width)
            text_x = (token.width - text_img.width) // 2
            text_y = (token.height - text_img.height - int(token.height*0.08))
            token.composite(text_img, left=text_x, top=text_y)
            text_img.close()

            # Resize to 555x555, since that will yield a 47mm token when printed at 300dpi
            # This allows for a 2mm bleed
            token.resize(width=555, height=555)

            # Save the token
            token.save(filename=token_output_path)
            token.close()

            # Update the progress bar
            overall_progress.update(overall_task, advance=1)

    # Close the component images
    token_bg.close()
    reminder_bg.close()
    for leaf in leaves:
        leaf.close()
    left_leaf.close()
    right_leaf.close()
    setup_flower.close()




