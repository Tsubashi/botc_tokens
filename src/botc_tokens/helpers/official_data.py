"""Load the official role data and use it to fill in gaps on roles."""
# Standard Library
import json
import re

# Application Specific
from .role import normalize_id, Role
from .web import fetch, FetchError, NotFoundError

ROLES_URL = "https://release.botc.app/resources/data/roles.json"
NIGHTSHEET_URL = "https://release.botc.app/resources/data/nightsheet.json"
TRANSLATIONS_REPO = "https://raw.githubusercontent.com/ThePandemoniumInstitute/botc-translations/main"
TRANSLATIONS_SITE = "https://translation.botc.app/"


class OfficialDataError(RuntimeError):
    """Raised when the official data cannot be fetched or understood."""


def translation_url(language: str) -> str:
    """Return the URL of the official translation file for a language code."""
    return f"{TRANSLATIONS_REPO}/game/{language}.json"


def reminder_key(text: str) -> str:
    """Return the translation table key for an English reminder: lowercase, keeping only letters and digits."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _string_list(value: object) -> list[str]:
    """Return a feed value as a list of strings, treating any other shape as empty."""
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    return []


class OfficialData:
    """The official roles and night order, fetched from the official feeds."""

    def __init__(self, roles_url: str = ROLES_URL, nightsheet_url: str = NIGHTSHEET_URL, language: str | None = None):
        """Remember where to fetch the feeds from, and which language (if not English) to translate text into."""
        self.roles_url = roles_url
        self.nightsheet_url = nightsheet_url
        self.language = None if language is None or language.lower() == "en" else language
        self.roles: dict[str, dict] = {}
        self.first_night: set[str] = set()
        self.other_nights: set[str] = set()
        self.translations: dict[str, dict] = {}
        self.reminder_translations: dict[str, str] = {}

    def load(self) -> None:
        """Fetch and parse the feeds, plus the translation file when a language is set."""
        try:
            roles = json.loads(fetch(self.roles_url))
            nightsheet = json.loads(fetch(self.nightsheet_url))
        except (FetchError, ValueError) as e:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
            raise OfficialDataError(f"Unable to load official data: {e}") from e
        if not isinstance(roles, list) or not all(isinstance(r, dict) and "id" in r for r in roles):
            raise OfficialDataError(f"Unexpected format in {self.roles_url}")
        if not isinstance(nightsheet, dict) or not all(
            isinstance(nightsheet.get(key, []), list) for key in ("firstNight", "otherNight")
        ):
            raise OfficialDataError(f"Unexpected format in {self.nightsheet_url}")
        self.roles = {normalize_id(entry["id"]): entry for entry in roles}
        self.first_night = {normalize_id(role_id) for role_id in nightsheet.get("firstNight", [])}
        self.other_nights = {normalize_id(role_id) for role_id in nightsheet.get("otherNight", [])}
        if self.language is not None:
            self._load_translations()

    def _load_translations(self) -> None:
        """Fetch and parse the translation file for the configured language."""
        url = translation_url(self.language)
        try:
            data = json.loads(fetch(url))
        except NotFoundError as e:
            raise OfficialDataError(
                f"No official translation was found for the language '{self.language}'. "
                f"See {TRANSLATIONS_SITE} for the available languages."
            ) from e
        except (FetchError, ValueError) as e:
            raise OfficialDataError(f"Unable to load the '{self.language}' translation: {e}") from e
        roles = data.get("roles", {}) if isinstance(data, dict) else None
        reminders = data.get("reminders", {}) if isinstance(data, dict) else None
        roles_ok = isinstance(roles, dict) and all(isinstance(entry, dict) for entry in roles.values())
        if not roles_ok or not isinstance(reminders, dict):
            raise OfficialDataError(f"Unexpected format in {url}")
        self.translations = {normalize_id(role_id): entry for role_id, entry in roles.items()}
        self.reminder_translations = reminders

    def _translated(self, role_id: str, field: str, default: str) -> str:
        """Return a role's translated text for a field, or the English default when there is none."""
        value = self.translations.get(normalize_id(role_id), {}).get(field)
        return value if isinstance(value, str) else default

    def _translated_reminder(self, text: str) -> str:
        """Return the translation of an English reminder, or the English text when there is none."""
        value = self.reminder_translations.get(reminder_key(text))
        return value if isinstance(value, str) else text

    def get(self, role_id: str) -> dict | None:
        """Return the official entry for a role id, or None if it is not official."""
        return self.roles.get(normalize_id(role_id))

    def fill_role(self, role: Role) -> bool:
        """Fill the unspecified fields of a role from the official data.

        Returns False if the role is not an official one. The icon is never touched.
        """
        entry = self.get(role.id)
        if entry is None:
            return False
        if role.name is None:
            role.name = self._translated(role.id, "name", entry["name"])
        if role.team is None:
            team = entry["team"]
            role.team = "traveler" if team == "traveller" else team
        if role.ability is None:
            role.ability = self._translated(role.id, "ability", entry["ability"])
        if role.reminders is None:
            reminders = _string_list(entry.get("reminders")) + _string_list(entry.get("remindersGlobal"))
            role.reminders = [self._translated_reminder(text) for text in reminders]
        if role.affects_setup is None:
            role.affects_setup = bool(entry.get("setup", False))
        if role.first_night is None:
            role.first_night = role.normalized_id in self.first_night
        if role.other_nights is None:
            role.other_nights = role.normalized_id in self.other_nights
        return True


def needs_official_data(roles: list[Role], known_ids: frozenset[str]) -> bool:
    """Return True if any role is a bare reference or has gaps an official role could fill."""
    return any(role.is_reference() or (role.has_gaps() and role.normalized_id in known_ids) for role in roles)
