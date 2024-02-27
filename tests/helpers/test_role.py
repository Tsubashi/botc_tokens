"""Test the role class."""
from botc_tokens.helpers.role import Role


def test_role_str():
    """Make sure the __str__ method works."""
    role = Role(name="Villager", ability="You are a boring villager.")
    assert str(role) == "Villager: You are a boring villager."
