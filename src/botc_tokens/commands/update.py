#!/usr/bin/env python
# coding: utf-8
"""Download story from the requested url."""
# Standard library
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from time import sleep
from urllib.error import HTTPError
import urllib.parse
from urllib.request import Request, urlopen

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
    parser.add_argument('-c', '--custom-list', type=str, default=None,
                        help="JSON file with a custom list of roles to update.")
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

        step_task = step_progress.add_task("Grabbing role data")
        wiki = prep_wiki(args.script_filter, args.custom_list)
        if wiki is None:
            return 1

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

        # Read in the forced_setup list
        with open(data_dir / "forced_setup.json", "r") as f:
            forced_setup = json.load(f)

        # Step through each role and grab the relevant data before adding it to the list.
        overall_progress.update(role_task, total=len(wiki.role_data))
        for role in wiki.role_data:
            if role.get("id") == "_meta":  # Skip the metadata
                overall_progress.update(role_task, advance=1)
                continue
            step_progress.update(step_task, description=f"Found role: {role['name']}")
            # Determine this role's team, preferring the roleType field
            team = role.get("roleType")
            team = role.get("team") if team is None else team
            team = "Unknown" if team is None else team

            version = role.get("version", "Unknown")

            role_output_path = output_path / version / team
            role_output_path.mkdir(parents=True, exist_ok=True)
            role_file = role_output_path / f"{format_filename(role['name'])}.json"

            found_role = process_role(role, role_file, wiki, step_progress, step_task, role_output_path)

            if found_role is not None:
                # Check if the role is in our forced_setup list
                if found_role.name.lower() in forced_setup:
                    found_role.affects_setup = True

                # Write it out
                step_progress.update(step_task, description=f"Writing role file for {found_role.name}")
                with open(role_file, "w") as f:
                    f.write(json.dumps(asdict(found_role)))

            # Update progress bar
            overall_progress.update(role_task, advance=1)
        step_progress.stop_task(step_task)


def prep_wiki(script_filter, custom_list=None):
    """Prepare the wiki object, loading the data from the web or a custom list.

    Args:
        script_filter (str): The filter to use when downloading the data.
        custom_list (str): The path to a custom list of roles to use.
    """
    # Gather the requested role data
    wiki = WikiSoup(script_filter)
    if custom_list:
        custom_list_path = Path(custom_list)
        if not custom_list_path.exists():
            print(f"[red]Error:[/] Could not find '{custom_list}'")
            return None
        with open(custom_list_path, "r") as f:
            custom_list = json.load(f)
            try:
                validate(custom_list, json.load(open(data_dir / "role_schema.json")))
            except ValidationError as e:
                print(f"[red]Error:[/] Could not parse '{custom_list}' as it does not match the schema: {e}")
                return None
            wiki.role_data = custom_list
    else:
        # Download the official lists from the script tool
        wiki.load_from_web()
    return wiki


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
    else:
        # Get info from the wiki
        step_progress.update(step_task, description=f"Getting ability text for {name}")
        found_role.ability = role.get("ability") if role.get("ability") else get_role_ability(name, wiki)

        step_progress.update(step_task, description=f"Getting reminders for {name}")
        found_role.reminders = role.get("reminders") if role.get("reminders") else get_role_reminders(name, wiki)

        # Determine night actions
        if role.get("firstNight"):
            found_role.first_night = True
        else:
            found_role.first_night = True if role['id'] in wiki.night_data['firstNight'] else False

        if role.get("otherNight"):
            found_role.other_nights = True
        else:
            found_role.other_nights = True if role['id'] in wiki.night_data['otherNight'] else False

        # Check if the role affects setup
        if "[" in found_role.ability:
            found_role.affects_setup = True

        # Record home script and type
        home = role.get("version")
        home = role.get("edition") if home is None else home
        home = "Unknown" if home is None else home
        found_role.home_script = home

        team = role.get("roleType")
        team = role.get("team") if team is None else team
        team = "Unknown" if team is None else team
        found_role.type = team

    # Grab the icon, checking first to see if it exists
    step_progress.update(step_task, description=f"Getting icon for {name}")
    get_role_icon(found_role, role, role_output_path, wiki)

    return found_role


def get_role_icon(found_role, role, role_output_path, wiki):
    """Get the icon for a role, using the wiki if needed.

    Args:
        found_role (Role): The role to update.
        role (dict): The role data from the script tool or custom list.
        role_output_path (Path): The path to write the icon to.
        wiki (WikiSoup): The wiki soup object.
    """
    if found_role.icon:
        icon_path = role_output_path / found_role.icon
        if icon_path.exists():
            return
    # Set the icon URL if we already have it
    if role.get("image"):
        img = role.get("image")
        if isinstance(img, list):
            # Empty lists would already be caught by the check above.
            # Since we don't support multiple icons, just take the first one. It should match the team alignment.
            icon_url = img[0]
        else:
            icon_url = img
    else:
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
            # Retry failed requests with a few changes
            # - a slight delay to appease rate limits
            # - a different User-Agent
            sleep(0.5)
            try:
                req = Request(icon_url, headers={'User-Agent': 'Mozilla/5.0'})
                image_bits = urlopen(req).read()
            except HTTPError:
                print(f"[red]Error:[/] Unable to download icon for {found_role.name}: {str(e)}")
                return
        # Parse the image
        with Image(blob=image_bits) as img:
            # Remove the extra space around the icon
            img.trim(color=Color('rgba(0,0,0,0)'), fuzz=0)
            img.save(filename=str(icon_path))
    found_role.icon = str(icon_path.name)


def get_role_ability(name, wiki):
    """Get the ability for a role, using the wiki if needed.

    Args:
        name (str): The name of the role to search.
        wiki (WikiSoup): The wiki soup object.
    """
    try:
        return wiki.get_ability_text(name)
    except RuntimeError:
        print(f"[red]Error:[/] No ability found for {name}")
        return ""


def get_role_reminders(name, wiki):
    """Get the reminders for a role, using the wiki if needed.

    Args:
        name (str): The name of the role to search.
        wiki (WikiSoup): The wiki soup object.
    """
    try:
        return wiki.get_reminders(name)
    except RuntimeError:
        print(f"[red]Error:[/] No reminder info found for {name}")
        return []
