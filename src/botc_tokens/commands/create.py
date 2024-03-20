"""Command to create token images to match json files in a directory tree."""
# Standard Library
import argparse
import json
from pathlib import Path
import string
import sys
from zipfile import BadZipFile

# Third Party
from rich import print
from rich.live import Live
from wand.exceptions import BlobError
from wand.image import Image

# Application Specific
from .. import component_path as default_component_path
from ..helpers.progress_group import setup_progress_group
from ..helpers.text_tools import curved_text_to_image, fit_ability_text, format_filename
from ..helpers.token_components import TokenComponents


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="botc_tokens create",
        description='Create token images to match json files in a directory tree.')
    parser.add_argument('search_dir', type=str, default="inputs", nargs="?",
                        help='The top level directory in which to begin the search.')
    output_dir_default = 'tokens'
    parser.add_argument('-o', '--output-dir', type=str, default=output_dir_default,
                        help=f"Name of the directory in which to output the tokens. (Default: {output_dir_default})")
    parser.add_argument('--components', type=str, default=default_component_path,
                        help="The directory or zip in which to find the token components. (leaves, backgrounds, etc.)")
    role_diameter_default = 575
    parser.add_argument('--role-diameter', type=int, default=role_diameter_default,
                        help="The diameter (in pixels) to use for role tokens. Components will be resized to fit. "
                             f"(Default: {role_diameter_default})")
    reminder_diameter_default = 325
    parser.add_argument('--reminder-diameter', type=int, default=reminder_diameter_default,
                        help="The diameter (in pixels) to use for reminder tokens. Components will be resized to fit. "
                             f"(Default: {reminder_diameter_default})")
    args = parser.parse_args(sys.argv[2:])
    return args


def create_reminder_token(reminder_icon, output, reminder_text, components, diameter):
    """Create and save a reminder token.

    Args:
        reminder_icon (wand.image.Image): The icon to be used for the reminder.
        output (str): The path to save the reminder token to.
        reminder_text (str): The text to be displayed on the reminder token.
        components (TokenComponents): The component package to use.
        diameter (int): The diameter (in pixels) to use for reminder tokens. Components will be resized to fit.
    """
    reminder = components.get_reminder_bg()
    reminder_icon_x = (reminder.width - reminder_icon.width) // 2
    reminder_icon_y = (reminder.height - reminder_icon.height - int(reminder.height * 0.15)) // 2
    reminder.composite(reminder_icon, left=reminder_icon_x, top=reminder_icon_y)
    # Add the reminder text
    text_img = curved_text_to_image(string.capwords(reminder_text), "reminder", reminder.width, components)
    text_x = (reminder.width - text_img.width) // 2
    text_y = (reminder.height - text_img.height - int(reminder_icon.height * 0.05))
    reminder.composite(text_img, left=text_x, top=text_y)
    text_img.close()
    # Resize to requested diameter
    reminder.resize(width=diameter, height=diameter)
    # Save the reminder token
    reminder.save(filename=output)
    reminder.close()


def create_role_token(token_icon, role, components, output, diameter):
    """Create and save a role token.

    Args:
        token_icon (wand.image.Image): The icon to be used for the role.
        role (dict): The role data to use for the token.
        components (TokenComponents): The component package to use.
        output (str): The path to save the role token to.
        diameter (int): The diameter (in pixels) to use for role tokens.
    """
    # Check if we have reminders. If so, add leaves.
    # Add leaves to the big token

    token = components.get_role_bg()
    for leaf in components.leaves[:len(role['reminders'])]:
        token.composite(leaf, left=0, top=0)
    # Determine where to place the icon
    icon_x = (token.width - token_icon.width) // 2
    icon_y = (token.height - token_icon.height + int(token.height * 0.15)) // 2
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
    ability_text_img = fit_ability_text(
        text=role['ability'],
        font_size=int(token.height * 0.055),
        first_line_width=int(token.width * .52),
        step=int(token.width * .1),
        components=components
    )
    ability_text_x = (token.width - ability_text_img.width) // 2
    token.composite(ability_text_img, left=ability_text_x, top=int(token.height * 0.09))
    ability_text_img.close()
    # Add the role name to the token
    text_img = curved_text_to_image(role['name'], "role", token.width, components)
    text_x = (token.width - text_img.width) // 2
    text_y = (token.height - text_img.height - int(token.height * 0.08))
    token.composite(text_img, left=text_x, top=text_y)
    text_img.close()

    # Resize to requested diameter
    token.resize(width=diameter, height=diameter)

    # Save the token
    token.save(filename=output)
    token.close()


def run():
    """Use JSON to create a set of tokens."""
    args = _parse_args()
    json_files = [file for file in Path(args.search_dir).rglob("*.json")]
    if len(json_files) == 0:
        print("[red]Error: [/][bold]No JSON files found in the search directory.[/]")
        return
    print("[green]Finding Roles...[/]")
    roles = find_roles_from_json(json_files)
    print(f"[green]Creating tokens in {args.output_dir}...[/]", end="")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load the component images
    components = load_components(args.components)
    if components is None:
        return

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
            token_output_path = role_output_path / f"{format_filename(role['name'])}.png"
            if token_output_path.exists():
                continue

            # Create the reminder tokens
            icon = Image(filename=role['icon'])
            reminder_icon = icon.clone()
            # The "^" modifier means this transform specifies the minimum height and width.
            # A transform without a modifier specifies the maximum height and width.
            target_width = components.reminder_bg.width * 0.75
            target_height = components.reminder_bg.height * 0.75
            reminder_icon.transform(resize=f"{target_width}x{target_height}^")
            reminder_icon.transform(resize=f"{target_width}x{target_height}")
            for reminder_text in role['reminders']:
                step_progress.update(step_task, description=f"Creating Token for: {role.get('name')}")
                reminder_name = format_filename(f"{role['name']}-Reminder-{reminder_text}")
                reminder_output_path = role_output_path / f"{reminder_name}.png"
                duplicate_counter = 1
                while reminder_output_path.exists():
                    duplicate_counter += 1
                    reminder_output_path = role_output_path / f"{reminder_name}-{duplicate_counter}.png"

                create_reminder_token(
                    reminder_icon, reminder_output_path, reminder_text, components, args.reminder_diameter
                )
            reminder_icon.close()

            # Composite the various pieces of the token.
            step_progress.update(step_task, description=f"Creating Token for: {role.get('name')}")
            token_icon = icon.clone()
            # The "^" modifier means this transform specifies the minimum height and width.
            # A transform without a modifier specifies the maximum height and width.
            target_width = components.role_bg.width * 0.6
            target_height = components.role_bg.height * 0.5
            token_icon.transform(resize=f"{target_width}x{target_height}^")
            token_icon.transform(resize=f"{target_width}x{target_height}")

            create_role_token(token_icon, role, components, token_output_path, args.role_diameter)

            # Update the progress bar
            overall_progress.update(overall_task, advance=1)

    # Close the component images
    components.close()


def load_components(component_package):
    """Handle loading the components from a directory or zip file, and alerting the user if it fails."""
    try:
        components = TokenComponents(component_package)
    except BlobError as e:
        print(f"\n[red]Error:[/][bold] Could not load component: {str(e)}[/]")
        return None
    except BadZipFile:
        print(f"\n[red]Error:[/][bold] Could not load components from '{component_package}' it does not appear to be a "
              "valid components package.[/]")
        return None
    except FileNotFoundError as e:
        print(f"\n[red]Error:[/][bold] Unable to load components from '{component_package}': {str(e)}")
        return None
    return components


def find_roles_from_json(json_files):
    """Load each json file and return the roles."""
    roles = []
    for json_file in json_files:
        with open(json_file, "r") as f:
            data = json.load(f)
        # Rewrite the icon path to be relative to our working directory
        data['icon'] = str(json_file.parent / data.get('icon'))
        roles.append(data)
    return roles
