"""Command to create token images to match json files in a directory tree."""
import argparse
import json
from pathlib import Path
import sys

from rich import print
from rich.live import Live
from wand.image import Image

from .. import component_path as default_component_path
from ..helpers.progress_group import setup_progress_group
from ..helpers.text_tools import curved_text_to_image, fit_ability_text
from ..helpers.token_components import TokenComponents


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


def create_reminder_token(reminder_bg_img, reminder_icon, reminder_output_path, reminder_text):
    """Create and save a reminder token.

    Args:
        reminder_bg_img (wand.image.Image): The background image for the reminder token.
        reminder_icon (wand.image.Image): The icon to be used for the reminder.
        reminder_output_path (str): The path to save the reminder token to.
        reminder_text (str): The text to be displayed on the reminder token.
    """
    reminder_icon_x = (reminder_bg_img.width - reminder_icon.width) // 2
    reminder_icon_y = (reminder_bg_img.height - reminder_icon.height - int(reminder_bg_img.height * 0.15)) // 2
    reminder_bg_img.composite(reminder_icon, left=reminder_icon_x, top=reminder_icon_y)
    # Add the reminder text
    text_img = curved_text_to_image(reminder_text.title(), "reminder", reminder_icon.width)
    text_x = (reminder_bg_img.width - text_img.width) // 2
    text_y = (reminder_bg_img.height - text_img.height - int(reminder_icon.height * 0.05))
    reminder_bg_img.composite(text_img, left=text_x, top=text_y)
    text_img.close()
    # Resize to 319x319 since that will yield a 27mm token when printed at 300dpi
    # This allows for a 2mm bleed
    reminder_bg_img.resize(width=319, height=319)
    # Save the reminder token
    reminder_bg_img.save(filename=reminder_output_path)
    reminder_bg_img.close()


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
    components = TokenComponents(args.component_dir)

    # Create the tokens
    progress_group, overall_progress, step_progress = setup_progress_group()

    with Live(progress_group):
        output_path = Path(args.output_dir)
        overall_task = overall_progress.add_task("Creating Tokens...", total=len(roles))
        step_task = step_progress.add_task("Reading roles...")
        for role in roles:
            step_progress.update(step_task, description=f"Creating Token for: {role.get('name')}")
            # Make sure our target directory exists
            role_output_path = output_path / role['home_script'] / role['type']
            role_output_path.mkdir(parents=True, exist_ok=True)

            # Skip if the token already exists
            token_output_path = role_output_path / f"{role['name']}.png"
            if token_output_path.exists():
                continue

            # Create the reminder tokens
            icon = Image(filename=role['icon'])
            reminder_icon = icon.clone()
            reminder_icon.transform(resize=f"{components.reminder_bg.width}x{components.reminder_bg.height}>")
            for reminder_text in role['reminders']:
                step_progress.update(step_task, description=f"Creating Token for: {role.get('name')}")
                reminder_name = f"{role['name']}-Reminder-{reminder_text.replace(':', '-')}"
                reminder_output_path = role_output_path / f"{reminder_name}.png"
                duplicate_counter = 1
                while reminder_output_path.exists():
                    duplicate_counter += 1
                    reminder_output_path = role_output_path / f"{reminder_name}-{duplicate_counter}.png"

                reminder_bg_img = components.get_reminder_bg()
                create_reminder_token(reminder_bg_img, reminder_icon, reminder_output_path, reminder_text)
            reminder_icon.close()

            # Composite the various pieces of the token.
            token = components.get_role_bg()
            token_icon = icon.clone()
            token_icon.transform(resize=f"{token.width * 0.7}x{token.height * 0.7}^")

            # Check if we have reminders. If so, add leaves.
            # Add leaves to the big token
            for leaf in components.leaves[:len(role['reminders'])]:
                token.composite(leaf, left=0, top=0)

            # Determine where to place the icon
            icon_x = (token.width - token_icon.width) // 2
            icon_y = (token.height - token_icon.height + int(token.height * 0.22)) // 2
            token.composite(token_icon, left=icon_x, top=icon_y)
            token_icon.close()

            # Check for modifiers
            if role.get('first_night'):
                token.composite(components.left_leaf, left=0, top=0)
            if role.get('other_nights'):
                token.composite(components.right_leaf, left=0, top=0)
            if role.get('affects_setup'):
                token.composite(components.setup_flower, left=0, top=0)

            # Add ability text to the token
            step_progress.update(step_task, description=f"Creating Token for: {role.get('name')}")
            ability_text_img = fit_ability_text(
                text=role['ability'],
                font_size=int(token.height * 0.055),
                first_line_width=int(token.width * .52),
                step=int(token.width * .1)
            )
            ability_text_x = (token.width - ability_text_img.width) // 2
            token.composite(ability_text_img, left=ability_text_x, top=int(token.height * 0.09))
            ability_text_img.close()

            # Add the role name to the token
            text_img = curved_text_to_image(role['name'], "role", token.width)
            text_x = (token.width - text_img.width) // 2
            text_y = (token.height - text_img.height - int(token.height * 0.08))
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
    components.close()
