#!/usr/bin/env python
# coding: utf-8
"""Download story from the requested url."""
# Standard library
import argparse
import json
import sys
import urllib.parse
from dataclasses import asdict
from pathlib import Path
from time import sleep
from urllib.error import HTTPError
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
    parser.add_argument('--script-filter', type=str, default='',
                        help="Filter for scripts to pull (Example: 'Experimental')")
    parser.add_argument('-b', '--bloodstar-url', type=str, default='',
                        help="Link to bloodstar hosted script json")
    parser.add_argument('--reminders', type=str,
                        help="JSON file to override reminder guesses from the wiki.")
    parser.add_argument('-c', '--custom-list', type=str, default=None,
                        help="JSON file with a custom list of roles to update.")
    parser.add_argument('--use-playtest', action='store_true',
                        help="Use the playtest icon source instead of the wiki.")
    parser.add_argument('--use-built-in', action='store_true',
                        help="Use the built-in role list as of date 2025-11-13.")
    args = parser.parse_args(sys.argv[2:])
    return args


def _should_skip(role):
    """Determine if a role should be skipped."""
    # Bloodstar uses bare strings for built-in roles. If we see one, we need to pull data from official wiki and
    # see if we can find a match.
    if isinstance(role, str):
        # Remove underscores for better matching
        rolename = role.replace("_", "")
        print(f"[yellow]Warning:[/] Role '{rolename}' does not have any data. Checking the official wiki.")
        if not hasattr(_should_skip, "official_wiki"):
            _should_skip.official_wiki = WikiSoup("")
            _should_skip.official_wiki.load_from_web()
        # Match on either ID or Name
        try:
            role = next(
                role for role in _should_skip.official_wiki.role_data
                if role.get("name") == rolename or role.get("id") == rolename
            )
        except StopIteration:
            print(f"[red]Error:[/] Unable to find '{rolename}' in official wiki. Skipping.")
            return True
    if role.get("id") == "_meta":  # Skip the metadata
        return True
    if not role.get("name"):
        print(f"[red]Error:[/] Skipping id: '{role['id']}' because it has no name.")
        return True
    return False


def run():
    """Run the updater."""
    args = _parse_args()
    progress_group, overall_progress, step_progress = setup_progress_group()

    with Live(progress_group):
        output_path = Path(args.output_dir)
        # create overall progress bar
        role_task = overall_progress.add_task("Updating role data...", total=None)

        step_task = step_progress.add_task("Grabbing role data")
        wiki = prep_wiki(args.script_filter, args.bloodstar_url, args.custom_list, args.use_built_in)
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
            if _should_skip(role):
                overall_progress.update(role_task, advance=1)
                continue
            step_progress.update(step_task, description=f"Found role: {role['name']}")
            # Determine this role's team, preferring the roleType field
            team = role.get("roleType")
            team = role.get("team") if team is None else team
            team = "Unknown" if team is None else team

            version = role.get("version")
            version = role.get("edition") if version is None else version
            version = "Unknown" if version is None else version

            role_output_path = output_path / version / team
            role_output_path.mkdir(parents=True, exist_ok=True)
            role_file = role_output_path / f"{format_filename(role['id'])}.json"

            found_role = \
                process_role(role, role_file, wiki, step_progress, step_task, role_output_path,
                             len(args.bloodstar_url) > 0 or args.use_built_in, args.use_playtest)

            if found_role is not None:
                # Check if the role is in our forced_setup list
                if found_role.id.lower() in forced_setup:
                    found_role.affects_setup = True

                # Write it out
                step_progress.update(step_task, description=f"Writing role file for {found_role.name}")
                with open(role_file, "w") as f:
                    f.write(json.dumps(asdict(found_role)))

            # Update progress bar
            overall_progress.update(role_task, advance=1)
        step_progress.stop_task(step_task)


def prep_wiki(script_filter, bloodstar_url, custom_list=None, use_built_in=False):
    """Prepare the wiki object, loading the data from the web or a custom list.

    Args:
        script_filter (str): The filter to use when downloading the data.
        bloodstar_url (str): The URL of the bloodstar site.
        custom_list (str): The path to a custom list of roles to use.
        use_built_in (bool): Whether to load roles from built in file.
    """
    # Gather the requested role data
    wiki = WikiSoup(script_filter)
    if use_built_in:
        wiki.role_data = json.load(open(data_dir / "known_roles.json", encoding="utf-8"))
    elif bloodstar_url.startswith("https://www.bloodstar.xyz"):
        wiki.load_from_bloodstar(bloodstar_url)
    elif custom_list:
        custom_list_path = Path(custom_list)
        if not custom_list_path.exists():
            print(f"[red]Error:[/] Could not find '{custom_list}'")
            return None
        with open(custom_list_path, "r") as f:
            custom_list = json.load(f)
            try:
                validate(custom_list, json.load(open(data_dir / "role_schema.json")))
            except ValidationError as e:
                print(f"[yellow]Warning:[/] The custom json specified does not fit the copy of the TPI schema that I "
                      f"have. Specifically: {e}"
                      f"\n\nI will continue, but [yellow]be warned that it might not work[/].")
            wiki.role_data = custom_list
    else:
        # Download the official lists from the script tool
        wiki.load_from_web()
    return wiki


def process_role(role, file, wiki, step_progress, step_task, role_output_path, skip_reminders=False, use_playtest=False):
    """Process a role, grabbing the relevant data and returning a Role object.

    Args:
        role (dict): The role data from the script tool.
        file (Path): The file to write the role data to.
        wiki (WikiSoup): The wiki soup object.
        step_progress (Progress): The progress bar to update.
        step_task (int): The task to update.
        role_output_path (Path): The path to write the role file to.
        use_playtest (bool): Whether to use the playtest icon source instead of the wiki.
    """
    name = role['name']
    role_id = role['id']
    found_role = Role(id= role_id, name=name)

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
        found_role.reminders = []
        if role.get("reminders"):
            found_role.reminders.extend(role.get("reminders"))
        if role.get("remindersGlobal"):
            found_role.reminders.extend(role.get("remindersGlobal"))
        if not found_role.reminders:
            found_role.reminders = get_role_reminders(name, wiki, skip_reminders)

        # Determine night actions
        if role.get("firstNight") or has_value(role.get("firstNightReminder")):
            found_role.first_night = True
        else:
            found_role.first_night = True if role['id'] in wiki.night_data['firstNight'] else False

        if role.get("otherNight") or has_value(role.get("otherNightReminder")):
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
    get_role_icon(found_role, role, role_output_path, wiki, use_playtest)

    return found_role

def has_value(value):
    if isinstance(value, str):
        return len(value) > 0
    return False

def get_role_icon(found_role, role, role_output_path, wiki, use_playtest=False):
    """Get the icon for a role, using the wiki if needed.

    Args:
        found_role (Role): The role to update.
        role (dict): The role data from the script tool or custom list.
        role_output_path (Path): The path to write the icon to.
        wiki (WikiSoup): The wiki soup object.
        use_playtest (bool): Whether to use the playtest icon source instead of the wiki.
    """
    if found_role.icon:
        icon_path = role_output_path / found_role.icon
        if icon_path.exists():
            return
    # Set the icon URL if we already have it
    if role.get("image"):
        img = role.get("image")
        if isinstance(img, list):
            # Empty lists would already be caught by previous checks.
            # Since we don't support multiple icons, just take the first one. It should match the team alignment.
            icon_url = img[0]
        else:
            icon_url = img
    else:
        if use_playtest:
            filename = ''.join(e for e in found_role.name.lower() if e.isalnum())
            icon_url = f"https://github.com/tomozbot/botc-icons/raw/main/PNG/{filename}.png"
        else:
            try:
                icon_url = wiki.get_big_icon_url(found_role.name)
            except RuntimeError as e:
                print(f"[red]Error:[/] No icon found for {found_role.name}: {str(e)}")
                return
            icon_url = urllib.parse.urljoin("https://wiki.bloodontheclocktower.com", icon_url)
    icon_path = role_output_path / f"{format_filename(found_role.id)}{Path(icon_url).suffix}"
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    if not save_icon(found_role, icon_path, icon_url):
        return
    found_role.icon = str(icon_path.name)


def save_icon(found_role, icon_path, icon_url):
    """Download (if needed) and save the icon for a role."""
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
                return False
        # Parse the image
        with Image(blob=image_bits) as img:
            # Remove the extra space around the icon
            img.trim(color=Color('rgba(0,0,0,0)'), fuzz=0)
            img.save(filename=str(icon_path))
    return True


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


def get_role_reminders(name, wiki, skip_reminders=False):
    """Get the reminders for a role, using the wiki if needed.

    Args:
        name (str): The name of the role to search.
        wiki (WikiSoup): The wiki soup object.
        skip_reminders (bool): Whether to skip the reminder search in case of built-in and bloodstar homebrew characters.
    """
    try:
        return wiki.get_reminders(name, skip_reminders)
    except RuntimeError:
        print(f"[red]Error:[/] No reminder info found for {name}")
        return []
