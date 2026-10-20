"""A class to represent a role in a script."""
# Standard Library
from dataclasses import dataclass
import hashlib

# Application Specific
from .text_tools import format_filename


def normalize_id(role_id: str) -> str:
    """Return the normalized form of a role id: lowercase with underscores removed."""
    return role_id.lower().replace("_", "")


@dataclass
class Role:
    """A role in a script.

    Every field except ``id`` is optional; ``None`` means the script did not specify it.

    Attributes:
        id: The id of the role.
        name: The name of the role.
        team: The team of the role (townsfolk, outsider, minion, demon, traveller, ...).
        ability: The description of the role.
        reminders: The reminder token names of the role.
        first_night: Whether the role wakes on the first night.
        other_nights: Whether the role wakes on nights other than the first.
        affects_setup: Whether the role changes the game setup.
        icon: The filename of the icon.
    """
    id: str
    name: str | None = None
    team: str | None = None
    ability: str | None = None
    reminders: list[str] | None = None
    first_night: bool | None = None
    other_nights: bool | None = None
    affects_setup: bool | None = None
    icon: str | None = None

    @property
    def normalized_id(self) -> str:
        """Return the normalized id."""
        return normalize_id(self.id)

    @property
    def slug(self) -> str:
        """Return a filename-safe form of the normalized id.

        Ids that are not already filename-safe get a short hash of the normalized id appended, so that two ids that
        clean to the same text (or to nothing) still get distinct files.
        """
        normalized = self.normalized_id
        clean = format_filename(normalized)
        if clean == normalized:
            return clean
        digest = hashlib.sha1(normalized.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
        return f"{clean}-{digest}" if clean else f"role-{digest}"

    def is_reference(self) -> bool:
        """Return True if the role is a bare reference: its name, team, and ability are all missing."""
        return self.name is None and self.team is None and self.ability is None

    def has_gaps(self) -> bool:
        """Return True if any gap-fillable field is missing."""
        return any(
            value is None
            for value in (
                self.name, self.team, self.ability, self.reminders,
                self.first_night, self.other_nights, self.affects_setup,
            )
        )

    def finalize(self) -> None:
        """Fill any remaining unspecified fields with defaults."""
        if self.name is None:
            self.name = self.id
        if self.team is None:
            self.team = "unknown"
        if self.ability is None:
            self.ability = ""
        if self.reminders is None:
            self.reminders = []
        if self.first_night is None:
            self.first_night = False
        if self.other_nights is None:
            self.other_nights = False
        if self.affects_setup is None:
            self.affects_setup = "[" in self.ability

    def __str__(self):
        """Return a string representation of the role."""
        return f"{self.name}: {self.ability}"
