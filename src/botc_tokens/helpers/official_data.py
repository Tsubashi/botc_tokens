"""Load the official role data and use it to fill in gaps on roles."""
# Standard Library
import json

# Application Specific
from .role import normalize_id, Role
from .web import fetch, FetchError

ROLES_URL = "https://release.botc.app/resources/data/roles.json"
NIGHTSHEET_URL = "https://release.botc.app/resources/data/nightsheet.json"


class OfficialDataError(RuntimeError):
    """Raised when the official data cannot be fetched or understood."""


class OfficialData:
    """The official roles and night order, fetched from the official feeds."""

    def __init__(self, roles_url: str = ROLES_URL, nightsheet_url: str = NIGHTSHEET_URL):
        """Remember where to fetch the feeds from."""
        self.roles_url = roles_url
        self.nightsheet_url = nightsheet_url
        self.roles: dict[str, dict] = {}
        self.first_night: set[str] = set()
        self.other_nights: set[str] = set()

    def load(self) -> None:
        """Fetch and parse both feeds."""
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
            role.name = entry["name"]
        if role.team is None:
            team = entry["team"]
            role.team = "traveler" if team == "traveller" else team
        if role.ability is None:
            role.ability = entry["ability"]
        if role.reminders is None:
            role.reminders = list(entry.get("reminders", [])) + list(entry.get("remindersGlobal", []))
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
