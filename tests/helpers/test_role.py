"""Test the role class."""
# Standard Library
import hashlib

# Application Specific
from botc_tokens.helpers.role import normalize_id, Role


def test_normalize_id():
    """Make sure ids are lowercased and underscores removed."""
    assert normalize_id("Fortune_Teller") == "fortuneteller"


def test_role_defaults_are_none():
    """Make sure every field except id defaults to None."""
    role = Role("imp")
    assert role.id == "imp"
    for field in ("name", "team", "ability", "reminders", "first_night", "other_nights", "affects_setup", "icon"):
        assert getattr(role, field) is None


def test_is_reference_and_has_gaps():
    """Make sure reference and gap detection work."""
    bare = Role("imp")
    assert bare.is_reference()
    assert bare.has_gaps()
    partial = Role("x", name="X", team="demon", ability="a")
    assert not partial.is_reference()
    assert partial.has_gaps()
    for field in ("name", "team", "ability"):
        one_field = Role("x", **{field: "set"})
        assert not one_field.is_reference()
        assert one_field.has_gaps()


def test_finalize_fills_defaults():
    """Make sure finalize fills the gaps and leaves explicit values alone."""
    role = Role("imp")
    role.finalize()
    assert role.name == "imp"
    assert role.team == "unknown"
    assert role.ability == ""
    assert role.reminders == []
    assert role.first_night is False
    assert role.other_nights is False
    assert role.affects_setup is False
    assert not role.has_gaps()

    bracket = Role("baron", ability="There are extra Outsiders in play. [+2 Outsiders]")
    bracket.finalize()
    assert bracket.affects_setup is True

    explicit = Role("baron", ability="[+2 Outsiders]", affects_setup=False)
    explicit.finalize()
    assert explicit.affects_setup is False


def test_slug():
    """Make sure the slug is a filename-safe normalized id, with a hash when cleaning changed it."""
    digest = hashlib.sha1("my role/1".encode("utf-8")).hexdigest()[:8]
    assert Role("My Role/1").slug == f"my_role-1-{digest}"
    assert Role("My_Role").normalized_id == "myrole"
    assert Role("Fortune_Teller").slug == "fortuneteller"


def test_slug_empty_after_cleaning():
    """An id with no filename-safe characters gets a hashed placeholder slug."""
    digest = hashlib.sha1("éè".encode("utf-8")).hexdigest()[:8]
    assert Role("éè").slug == f"role-{digest}"


def test_slug_distinct_non_ascii_ids():
    """Two different ids that clean to the same text still get different slugs."""
    first, second = Role("été"), Role("àtà")
    assert first.slug != second.slug
    assert first.slug.startswith("t-") and second.slug.startswith("t-")


def test_role_str():
    """Make sure the __str__ method works."""
    role = Role(id="villager", name="Villager", ability="You are a boring villager.")
    assert str(role) == "Villager: You are a boring villager."


def test_finalize_keeps_specified_values():
    """Make sure finalize leaves every already-specified field untouched."""
    role = Role("x", name="X", team="demon", ability="a", reminders=["r"], first_night=True, other_nights=True,
                affects_setup=True)
    role.finalize()
    assert (role.name, role.team, role.ability, role.reminders) == ("X", "demon", "a", ["r"])
    assert (role.first_night, role.other_nights, role.affects_setup) == (True, True, True)
    assert not role.has_gaps()
