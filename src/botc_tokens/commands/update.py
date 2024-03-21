#!/usr/bin/env python
# coding: utf-8
"""Download story from the requested url."""
# Standard library
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
import urllib.parse
from urllib.request import urlopen


# Third-party libraries
from jsonschema import validate, ValidationError
from rich import print
from rich.live import Live
from wand.color import Color
from wand.image import Image

# Application specific
from .. import data_dir
from ..helpers.progress_group import setup_progress_group
from ..helpers.role import Role
from ..helpers.text_tools import format_filename
from ..helpers.wiki_soup import WikiSoup


def _parse_args():
    parser = argparse.ArgumentParser(description='Download roles from the wiki, with associated icon and description.')
    parser.add_argument('-o', '--output-dir', type=str, default='inputs',
                        help="Directory in which to write the json and icon files (Default: 'inputs')")
    parser.add_argument('--script-filter', type=str, default='Experimental',
                        help="Filter for scripts to pull (Default: 'Experimental')")
    parser.add_argument('--reminders', type=str,
                        help="JSON file to override reminder guesses from the wiki.")
    args = parser.parse_args(sys.argv[2:])
    return args


def run():
    """Run the updater."""
    args = _parse_args()
    progress_group, overall_progress, step_progress = setup_progress_group()

    with Live(progress_group):
        output_path = Path(args.output_dir)
        # create overall progress bar
        role_task = overall_progress.add_task("Updating role data...", total=None)

        # Download the official lists from the script tool by initializing the WikiSoup
        step_task = step_progress.add_task("Downloading role data from the official script tool")
        wiki = WikiSoup(args.script_filter)

        # Open the reminder overrides file, if it exists
        step_progress.update(step_task, description="Reading reminder overrides file")
        if args.reminders:
            with open(args.reminders, "r") as f:
                json_data = json.load(f)
                try:
                    validate(json_data, json.load(open(data_dir / "reminder_schema.json")))
                except ValidationError as e:
                    print(f"[red]Error:[/] {args.reminders} does not match the schema: {e}")
                    return 1
                wiki.reminder_overrides = json_data

        # Step through each role and grab the relevant data before adding it to the list.
        overall_progress.update(role_task, total=len(wiki.role_data))
        for role in wiki.role_data:
            step_progress.update(step_task, description=f"Found role: {role['name']}")
            role_output_path = output_path / role['version'] / role['roleType']
            role_output_path.mkdir(parents=True, exist_ok=True)
            role_file = role_output_path / f"{format_filename(role['name'])}.json"

            found_role = process_role(role, role_file, wiki, step_progress, step_task, role_output_path)

            # Write individual role json, if we found it
            if found_role is not None:
                step_progress.update(step_task, description=f"Writing role file for {found_role.name}")
                with open(role_file, "w") as f:
                    f.write(json.dumps(asdict(found_role)))

            # Update progress bar
            overall_progress.update(role_task, advance=1)
        step_progress.stop_task(step_task)


def process_role(role, file, wiki, step_progress, step_task, role_output_path):
    """Process a role, grabbing the relevant data and returning a Role object.

    Args:
        role (dict): The role data from the script tool.
        file (Path): The file to write the role data to.
        wiki (WikiSoup): The wiki soup object.
        step_progress (Progress): The progress bar to update.
        step_task (int): The task to update.
        role_output_path (Path): The path to write the role file to.
    """
    name = role['name']
    found_role = Role(name=name)

    # Check if we have a json file for the role
    if file.exists():
        try:
            with open(file, "r") as f:
                j = json.load(f)
            found_role = Role(**j)
        except json.decoder.JSONDecodeError:
            print(f"[red]Error:[/] Could not read {file}. Skipping.")
            return None

    # Get info from the wiki
    step_progress.update(step_task, description=f"Getting ability text for {name}")
    get_role_ability(found_role, wiki)

    step_progress.update(step_task, description=f"Getting reminders for {name}")
    get_role_reminders(found_role, wiki)

    # Grab the icon, checking first to see if it exists
    if found_role.icon:
        icon_path = role_output_path / found_role.icon
        if not icon_path.exists():
            found_role.icon = None
    # If we don't have the icon, go get it from the wiki
    if not found_role.icon:
        step_progress.update(step_task, description=f"Getting icon for {name}")
        get_role_icon(found_role, role_output_path, wiki)
    # Determine night actions
    found_role.first_night = True if role['id'] in wiki.night_data['firstNight'] else False
    found_role.other_nights = True if role['id'] in wiki.night_data['otherNight'] else False
    # Check if the role affects setup
    if "[" in found_role.ability:
        found_role.affects_setup = True
    # Record home script and type
    if not found_role.home_script:
        found_role.home_script = role['version']
    if not found_role.type:
        found_role.type = role['roleType']
    return found_role


def get_role_icon(found_role, role_output_path, wiki):
    """Get the icon for a role, using the wiki if needed.

    Args:
        found_role (Role): The role to update.
        role_output_path (Path): The path to write the icon to.
        wiki (WikiSoup): The wiki soup object.
    """
    try:
        icon_url = wiki.get_big_icon_url(found_role.name)
    except RuntimeError as e:
        print(f"[red]Error:[/] No icon found for {found_role.name}: {str(e)}")
        return
    icon_url = urllib.parse.urljoin("https://wiki.bloodontheclocktower.com", icon_url)
    icon_path = role_output_path / f"{format_filename(found_role.name)}{Path(icon_url).suffix}"
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    if not icon_path.exists():
        # Load the image from the web
        try:
            image_bits = urlopen(icon_url).read()
        except HTTPError as e:
            print(f"[red]Error:[/] Unable to download icon for {found_role.name}: {str(e)}")
            return
        # Parse the image
        with Image(blob=image_bits) as img:
            # Remove the extra space around the icon
            img.trim(color=Color('rgba(0,0,0,0)'), fuzz=0)
            img.save(filename=str(icon_path))
    found_role.icon = str(icon_path.name)


def get_role_ability(found_role, wiki):
    """Get the ability for a role, using the wiki if needed.

    Args:
        found_role (Role): The role to update.
        wiki (WikiSoup): The wiki soup object.
    """
    if not found_role.ability:
        try:
            found_role.ability = wiki.get_ability_text(found_role.name)
        except RuntimeError:
            print(f"[red]Error:[/] No ability found for {found_role.name}")
            found_role.ability = ""


def get_role_reminders(found_role, wiki):
    """Get the reminders for a role, using the wiki if needed.

    Args:
        found_role (Role): The role to update.
        wiki (WikiSoup): The wiki soup object.
    """
    if found_role.reminders is None:
        try:
            found_role.reminders = wiki.get_reminders(found_role.name)
        except RuntimeError:
            print(f"[red]Error:[/] No reminder info found for {found_role.name}")
            found_role.reminders = []
