"""A class to represent a role in a script."""
from dataclasses import dataclass


@dataclass
class Role:
    """A role in a script.

    Attributes:
        name: The name of the role.
        ability: The description of the role.
        type: The type of the role (Townsfolk, Outsider, Minion, Demon, or Traveller).
        first_night: Whether the role wakes for a night action on the first night.
        other_nights: Whether the role wakes for a night action on nights other than the first.
        reminders: The number of reminders tokens the role has.
        icon: The filename of the icon.
        home_script: The name of the script in which the role is found.
    """
    name: str
    ability: str = None
    type: str = None
    icon: str = None
    first_night: bool = False
    other_nights: bool = False
    reminders: list = None
    affects_setup: bool = False
    home_script: str = None

    def __str__(self):
        """Return a string representation of the role."""
        return f"{self.name}: {self.ability}"
