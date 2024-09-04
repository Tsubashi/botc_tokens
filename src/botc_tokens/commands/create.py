"""Command to create token images to match json files in a directory tree."""
# Standard Library
import argparse
import json
from pathlib import Path
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
from ..helpers.role import Role
from ..helpers.text_tools import format_filename
from ..helpers.token_components import TokenComponents
from ..helpers.token_creation import create_reminder_token, create_role_token


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
            step_progress.update(step_task, description=f"Creating Token for: {role.name}")
            # Make sure our target directory exists
            role_output_path = output_path / role.type
            role_output_path.mkdir(parents=True, exist_ok=True)

            # Skip if the token already exists
            token_output_path = role_output_path / f"{format_filename(role.name)}.png"
            if token_output_path.exists():
                continue

            # Create the reminder tokens
            icon = Image(filename=role.icon)
            reminder_icon = icon.clone()
            # The "^" modifier means this transform specifies the minimum height and width.
            # A transform without a modifier specifies the maximum height and width.
            target_width = components.reminder_bg.width * 0.75
            target_height = components.reminder_bg.height * 0.75
            reminder_icon.transform(resize=f"{target_width}x{target_height}^")
            reminder_icon.transform(resize=f"{target_width}x{target_height}")
            for reminder_text in role.reminders:
                step_progress.update(step_task, description=f"Creating Token for: {role.name}")
                reminder_name = format_filename(f"{role.name}-Reminder-{reminder_text}")
                reminder_output_path = role_output_path / f"{reminder_name}.png"
                duplicate_counter = 1
                while reminder_output_path.exists():
                    duplicate_counter += 1
                    reminder_output_path = role_output_path / f"{reminder_name}-{duplicate_counter}.png"

                reminder_token = create_reminder_token(reminder_icon, reminder_text, components, args.reminder_diameter)
                # Save the reminder token
                reminder_token.save(filename=reminder_output_path)
                reminder_token.close()
            reminder_icon.close()

            # Composite the various pieces of the token.
            step_progress.update(step_task, description=f"Creating Token for: {role.name}")
            token_icon = icon.clone()

            token = create_role_token(token_icon, role, components, args.role_diameter)
            # Save the token
            token.save(filename=token_output_path)
            token.close()

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
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
            # Rewrite the icon path to be relative to our working directory
            data['icon'] = str(json_file.parent / data.get('icon'))
            role = Role(data.get('name', "Unknown"))
            for att in dir(role):
                if att in data:
                    setattr(role, att, data[att])
            roles.append(role)
        except json.JSONDecodeError as e:
            print(f"[red]Error:[/][bold] Could not decode JSON file:[/] {json_file}")
            print(f"- {str(e)}")
        except UnicodeDecodeError as e:
            print(f"[red]Error:[/][bold] Could not decode JSON file: {json_file}")
            print(f"- {str(e)}")
        except Exception as e:
            print(f"[red]Error:[/][bold] Unknown error loading JSON file: {json_file}")
            print(f"- {str(e)}")

    return roles
