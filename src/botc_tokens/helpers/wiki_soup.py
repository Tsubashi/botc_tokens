"""A class to act as a cache for wiki access. That way we don't have to keep hitting the wiki for the same page."""
import json
from time import sleep
import urllib.error
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from .. import data_dir
from ..__version__ import version

# The official data files published alongside the script tool. The old script.bloodontheclocktower.com/data
# location no longer exists.
ROLES_URL = "https://release.botc.app/resources/data/roles.json"
NIGHTSHEET_URL = "https://release.botc.app/resources/data/nightsheet.json"
WIKI_URL = "https://wiki.bloodontheclocktower.com"

# Some of the hosts reject requests with a bare default User-Agent (with a 418 or 403). Rather than pretending to be
# a browser, identify ourselves honestly so the site owners know who is asking and where to find us.
REQUEST_HEADERS = {
    "User-Agent": f"botc_tokens/{version} (+https://github.com/Tsubashi/botc_tokens)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
FETCH_ATTEMPTS = 3
FETCH_RETRY_DELAY = 1.5


def fetch(url):
    """Read the contents of a URL, identifying ourselves as botc_tokens.

    Anything other than a 404 is retried a few times, with a growing pause between attempts, in case we were
    rate limited.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return urlopen(Request(url, headers=REQUEST_HEADERS)).read()
        except urllib.error.HTTPError as e:
            if e.code == 404 or attempt >= FETCH_ATTEMPTS:
                raise
            sleep(FETCH_RETRY_DELAY * attempt)


class WikiSoup:
    """A class to act as a cache for wiki access."""

    def __init__(self, script_filter: str = "Experimental"):
        """Prep the reminders and wiki soup."""
        self.wiki_soups = {}
        self.reminders = {}
        with open(data_dir / "known_reminders.json", "r") as f:
            self.reminders = json.load(f)
        self.reminder_overrides = {}
        self.role_data = {}
        self.night_data = {"firstNight": [], "otherNight": []}
        self._script_filter = script_filter

    def load_from_web(self):
        """Load the official role and night order data."""
        self.role_data = json.loads(fetch(ROLES_URL).decode('utf-8'))
        # Filter the roles. The official data calls the home script 'edition', older feeds used 'version'.
        self.role_data = [
            role for role in self.role_data
            if self._script_filter in role.get('edition', role.get('version', ''))
        ]
        self.night_data = json.loads(fetch(NIGHTSHEET_URL).decode('utf-8'))

    def load_from_web_json(self, custom_url):
        """Load the role data from the provided web hosted JSON file."""
        roles_from_web_json = json.loads(fetch(custom_url).decode('utf-8'))
        meta_data = next((item for item in roles_from_web_json if item.get('id') == '_meta'), None)
        version_name = None
        if meta_data:
            version_name = meta_data.get('name')
        # Filter and convert the roles
        roles_with_version = []
        for role in roles_from_web_json:
            if role.get('id') != '_meta':
                role['version'] = version_name if role.get('version') is None else role['version']
                role['name'] = role['name']
                role['ability'] = role.get('ability')
                roles_with_version.append(role)
        self.role_data = roles_with_version

    def _get_wiki_soup(self, role_name):
        """Take a role name and return a BeautifulSoup object for the role's wiki page."""
        # Check if we have already seen this role
        role_name = role_name.replace(" ", "_")
        if role_name not in self.wiki_soups:
            url = f"{WIKI_URL}/{role_name}"
            try:
                html = fetch(url)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise RuntimeError(f"Could not find role {role_name} at {url}")
                raise
            self.wiki_soups[role_name] = BeautifulSoup(html, 'html5lib')
        return self.wiki_soups[role_name]

    def get_ability_text(self, role_name):
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

    def get_reminders(self, role_name):
        """Take a role name and grab the reminders."""
        # First check if we have the role in the override reminders file
        if role_name in self.reminder_overrides:
            return self.reminder_overrides[role_name]

        # Next check if we have the role in the local reminders file
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

    def get_big_icon_url(self, role_name):
        """Take a role name and grab the corresponding icon url from the wiki."""
        soup = self._get_wiki_soup(role_name)
        icon_tag = soup.select_one("#character-details img")
        if not icon_tag:
            raise RuntimeError(f"Could not find icon for {role_name}")
        icon_url = icon_tag["src"]
        return icon_url
