#!/usr/bin/env python
# coding: utf-8
"""Download story from the requested url."""
from urllib.request import urlopen, urlretrieve
import urllib.parse
import string
import json
import argparse
import sys
from bs4 import BeautifulSoup
from pathlib import Path
from rich import print
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.live import Live
from rich.console import Group
from dataclasses import asdict
from ..helpers.role import Role
from .. import data_dir


def _parse_args():
    parser = argparse.ArgumentParser(description='Download roles from the wiki, with associated icon and description.')
    parser.add_argument('-o', '--output-dir', type=str, default='inputs',
                        help="Directory in which to write the json and icon files (Default: 'inputs')")
    parser.add_argument('--script-filter', type=str, default='Experimental',
                        help="Filter for scripts to pull (Default: 'Experimental')")
    args = parser.parse_args(sys.argv[2:])
    return args


def run():
    # Run the script
    args = _parse_args()
    u = Updater()
    u.run(args)


class Updater:

    def __init__(self):
        """Prep the reminders and wiki soup."""
        self.wiki_soups = {}
        self.reminders = []
        with open(data_dir / "known_reminders.json", "r") as f:
            self.reminders = json.load(f)

    def _get_wiki_soup(self, role_name):
        """Take a role name and return a BeautifulSoup object for the role's wiki page."""
        # Check if we have already seen this role
        role_name = role_name.replace(" ", "_")
        if role_name not in self.wiki_soups:
            role_name = role_name.replace("Of", "of")  # Fixes Spirit Of Ivory
            url = f"https://wiki.bloodontheclocktower.com/{role_name}"
            try:
                html = urlopen(url).read()
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise RuntimeError(f"Could not find role {role_name} at {url}")
                else:
                    raise
            self.wiki_soups[role_name] = BeautifulSoup(html, 'html5lib')
        return self.wiki_soups[role_name]

    def _get_ability_text(self, role_name):
        """Take a role name and grab the ability description."""
        soup = self._get_wiki_soup(role_name)
        summary_title = soup.find(id="Summary")
        if not summary_title:
            raise RuntimeError(f"Could not find summary section for {role_name}")
        tag = summary_title.parent.find_next_sibling("p")
        if not tag:
            raise RuntimeError(f"Could not find ability description for {role_name}")
        ability = tag.get_text()
        ability = ability.replace("\n", " ")
        ability = ability.strip('" ')
        ability = ability.replace("\"", "'")
        return ability

    def _get_reminders(self, role_name):
        """Take a role name and grab the reminders."""

        # First check if we have the role in the local reminders file
        if role_name in self.reminders:
            return self.reminders[role_name]

        # If we don't have the role, go get it from the wiki
        reminders = set()
        soup = self._get_wiki_soup(role_name)
        reminder_title = soup.find(id="How_to_Run")
        if not reminder_title:
            raise RuntimeError(f"Could not find 'How To Run' section for {role_name}")
        paragraphs = reminder_title.parent.find_next_siblings("p")
        for paragraph in paragraphs:
            bold_list = paragraph.find_all("b")
            for bold in bold_list:
                text = bold.get_text()
                if text.isupper():
                    disallowed_reminders = [
                        "YOU ARE",
                        "THIS PLAYER IS",
                        "THIS CHARACTER SELECTED YOU",
                        "THESE CHARACTERS ARE NOT IN PLAY",
                        "THIS IS THE DEMON",
                        "THESE ARE YOUR MINIONS",
                    ]
                    if text not in disallowed_reminders:
                        reminders.add(text)
        return list(reminders)

    def _get_big_icon_url(self, role_name):
        """Take a role name and grab the corresponding icon url from the wiki."""
        soup = self._get_wiki_soup(role_name)
        icon_tag = soup.select_one("#character-details img")
        if not icon_tag:
            raise RuntimeError(f"Could not find icon for {role_name}")
        icon_url = icon_tag["src"]
        return icon_url

    @staticmethod
    def _format_filename(in_string):
        """Take a string and return a valid filename constructed from the string.

        Args:
            in_string: The string to convert to a filename.

        This function uses a whitelist approach: any characters not present in valid_chars are removed. Spaces are
        replaced with underscores.

        Note: this method may produce invalid filenames such as ``, `.` or `..`
        """
        valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        in_string = in_string.replace(' ', '_')
        file_name = ''.join(char for char in in_string if char in valid_chars)
        return file_name

    def run(self, args):
        """Run the script.
        Args:
            args: The command line arguments.
        """

        # Download the official lists from the script tool
        print("[green]Downloading role data from the official script tool...[/green]", end='')
        roles_from_web = urlopen("https://script.bloodontheclocktower.com/data/roles.json").read().decode('utf-8')
        role_data = json.loads(roles_from_web)
        # Filter the roles
        role_data = [role for role in role_data if args.script_filter in role['version']]
        night_data = urlopen("https://script.bloodontheclocktower.com/data/nightsheet.json").read().decode('utf-8')
        night_json = json.loads(night_data)
        print("[bold green]Done![/]")

        # Overall progress bar
        overall_progress = Progress(
            TimeElapsedColumn(), BarColumn(), TextColumn("{task.description}")
        )

        # Progress bars for single steps (will be hidden when step is done)
        step_progress = Progress(
            TextColumn("  "),
            TimeElapsedColumn(),
            TextColumn("[bold purple]{task.description}"),
            SpinnerColumn("simpleDots"),
        )

        # Group the progress bars
        progress_group = Group(overall_progress, step_progress)

        with Live(progress_group):
            output_path = Path(args.output_dir)
            # create overall progress bar
            role_task = overall_progress.add_task("Parsing role data...", total=len(role_data))
            step_task = step_progress.add_task("Finding roles")

            # Step through each role and grab the relevant data before adding it to the list.
            for role in role_data:
                name = role['name']
                step_progress.update(step_task, description=f"Found role: {name}")
                role_output_path = output_path / role['version'] / role['roleType']
                role_output_path.mkdir(parents=True, exist_ok=True)

                # Check to see if we already have a json file for this role
                role_file = role_output_path / f"{self._format_filename(name)}.json"
                found_role = Role(name=name)
                if role_file.exists():
                    try:
                        with open(role_file, "r") as f:
                            j = json.load(f)
                        found_role = Role(**j)
                    except json.decoder.JSONDecodeError:
                        print(f"[red]Error:[/] Could not read {role_file}. Regenerating.")
                        role_file.unlink()

                # Get info from the wiki
                if not found_role.ability:
                    try:
                        step_progress.update(step_task, description=f"Getting ability text for {name}")
                        found_role.ability = self._get_ability_text(name)
                    except RuntimeError:
                        print(f"[red]Error:[/] No ability found for {name}")
                if found_role.reminders is None:
                    try:
                        step_progress.update(step_task, description=f"Getting reminders for {name}")
                        found_role.reminders = self._get_reminders(name)
                    except RuntimeError:
                        print(f"[red]Error:[/] No reminder info found for {name}")

                # Grab the icon, checking first to see if it exists
                if found_role.icon:
                    icon_path = role_output_path / found_role.icon
                    if not icon_path.exists():
                        found_role.icon = None
                # If we don't have the icon, go get it from the wiki
                if not found_role.icon:
                    try:
                        step_progress.update(step_task, description=f"Getting icon for {name}")
                        icon_url = self._get_big_icon_url(name)
                        icon_url = urllib.parse.urljoin("https://wiki.bloodontheclocktower.com", icon_url)
                        icon_path = role_output_path / f"{self._format_filename(name)}{Path(icon_url).suffix}"
                        icon_path.parent.mkdir(parents=True, exist_ok=True)
                        if not icon_path.exists():
                            urlretrieve(icon_url, icon_path)
                        found_role.icon = str(icon_path.name)
                    except RuntimeError:
                        print(f"[red]Error:[/] No icon found for {name}")

                # Determine night actions
                found_role.first_night = True if role['id'] in night_json['firstNight'] else False
                found_role.other_nights = True if role['id'] in night_json['otherNight'] else False

                # Check if the role affects setup
                if "[" in found_role.ability:
                    found_role.affects_setup = True

                # Record home script and type
                if not found_role.home_script:
                    found_role.home_script = role['version']
                if not found_role.type:
                    found_role.type = role['roleType']

                # Write individual role json
                step_progress.update(step_task, description=f"Writing role file for {name}")
                with open(role_file, "w") as f:
                    f.write(json.dumps(asdict(found_role)))

                # Update progress bar
                overall_progress.update(role_task, advance=1)

            step_progress.stop_task(step_task)
