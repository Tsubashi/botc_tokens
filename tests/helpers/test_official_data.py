"""Tests for the official data loader."""
# Third Party
import pytest

# Application Specific
from botc_tokens.helpers.official_data import (
    needs_official_data, NIGHTSHEET_URL, OfficialData, OfficialDataError, reminder_key, ROLES_URL, translation_url
)
from botc_tokens.helpers.role import Role
from botc_tokens.helpers.web import FetchError


@pytest.fixture()
def fake_feeds(fake_web, test_data_dir):
    """Serve the official fixture feeds."""
    fake_web.routes[ROLES_URL] = (test_data_dir / "official" / "roles.json").read_bytes()
    fake_web.routes[NIGHTSHEET_URL] = (test_data_dir / "official" / "nightsheet.json").read_bytes()
    return fake_web


@pytest.fixture()
def official(fake_feeds):
    """Return a loaded OfficialData."""
    data = OfficialData()
    data.load()
    return data


def test_load_and_get(official):
    """Lookups are normalized and unknown ids give None."""
    assert official.get("Fortune_Teller") is None
    assert official.get("IMP")["name"] == "Imp"


def test_load_failure_is_error(fake_feeds):
    """Fetch failures, bad JSON, and wrong shapes become OfficialDataError."""
    fake_feeds.routes[ROLES_URL] = FetchError("boom")
    with pytest.raises(OfficialDataError):
        OfficialData().load()
    fake_feeds.routes[ROLES_URL] = b"not json"
    with pytest.raises(OfficialDataError):
        OfficialData().load()
    fake_feeds.routes[ROLES_URL] = b"\xff\xfe"
    with pytest.raises(OfficialDataError):
        OfficialData().load()
    fake_feeds.routes[ROLES_URL] = b'{"id": "imp"}'
    with pytest.raises(OfficialDataError):
        OfficialData().load()
    fake_feeds.routes[ROLES_URL] = b'["imp"]'
    with pytest.raises(OfficialDataError):
        OfficialData().load()


def test_nightsheet_wrong_shape_is_error(fake_feeds, test_data_dir):
    """A nightsheet that is not a dict of lists is an error."""
    fake_feeds.routes[ROLES_URL] = (test_data_dir / "official" / "roles.json").read_bytes()
    for body in (b"[]", b'{"firstNight": "x", "otherNight": []}'):
        fake_feeds.routes[NIGHTSHEET_URL] = body
        with pytest.raises(OfficialDataError):
            OfficialData().load()


def test_fill_reference(official):
    """A bare reference is filled from the official data."""
    role = Role("washerwoman")
    assert official.fill_role(role) is True
    assert role.name == "Washerwoman"
    assert role.team == "townsfolk"
    assert role.ability.startswith("You start knowing")
    assert role.reminders == ["Townsfolk", "Wrong"]
    assert role.first_night is True
    assert role.other_nights is False
    assert role.affects_setup is False
    assert role.icon is None


def test_fill_keeps_explicit_fields(official):
    """Explicit fields are kept, gaps are filled."""
    role = Role("drunk", team="outsider", ability="custom", icon="x.png")
    assert official.fill_role(role) is True
    assert role.ability == "custom"
    assert role.name == "Drunk"
    assert role.reminders == ["Is The Drunk"]
    assert role.affects_setup is True
    assert role.icon == "x.png"


def test_fill_normalizes_traveller(official):
    """The live feed's 'traveller' spelling becomes 'traveler'."""
    role = Role("beggar")
    official.fill_role(role)
    assert role.team == "traveler"


def test_fill_night_flags_and_missing_reminders(official):
    """Night flags come from the nightsheet; absent reminder keys count as empty."""
    role = Role("imp")
    official.fill_role(role)
    assert (role.first_night, role.other_nights) == (False, True)
    official.roles["imp"] = {"id": "imp", "name": "Imp", "team": "demon", "ability": "a"}
    role = Role("imp")
    official.fill_role(role)
    assert role.reminders == []
    assert role.affects_setup is False


@pytest.mark.parametrize("reminders, global_reminders", [(None, "ABC"), ("ABC", ["A", 3]), ({"a": 1}, None)])
def test_fill_malformed_feed_reminders(official, reminders, global_reminders):
    """Feed reminders that are not lists of strings count as empty."""
    official.roles["imp"] = {
        "id": "imp", "name": "Imp", "team": "demon", "ability": "a",
        "reminders": reminders, "remindersGlobal": global_reminders,
    }
    role = Role("imp")
    official.fill_role(role)
    assert role.reminders == []


def test_fill_unknown_returns_false(official):
    """Unknown ids are left alone."""
    role = Role("fortuneteller")
    assert official.fill_role(role) is False
    assert role.name is None


def test_needs_official_data():
    """Only references and fillable gaps need the feeds."""
    known = frozenset({"imp"})
    assert needs_official_data([Role("imp")], known) is True
    full = Role("x", name="X", team="minion", ability="a")
    assert needs_official_data([full], known) is False
    gappy = Role("imp", name="Imp", team="demon", ability="a")
    assert needs_official_data([gappy], known) is True


def test_fill_complete_role_changes_nothing(official):
    """A role with every field set is left exactly as it was."""
    role = Role("imp", "Mine", "minion", "mine", ["r"], True, False, True, "i.png")
    assert official.fill_role(role) is True
    assert role == Role("imp", "Mine", "minion", "mine", ["r"], True, False, True, "i.png")


@pytest.fixture()
def french(fake_feeds, test_data_dir):
    """Return an OfficialData loaded with the French fixture translation."""
    fake_feeds.routes[translation_url("fr")] = (test_data_dir / "official" / "fr.json").read_bytes()
    data = OfficialData(language="fr")
    data.load()
    return data


def test_translation_url():
    """The translation feed lives in TPI's translations repository, one file per language."""
    assert translation_url("fr") == (
        "https://raw.githubusercontent.com/ThePandemoniumInstitute/botc-translations/main/game/fr.json"
    )


@pytest.mark.parametrize("text, key", [
    ("Townsfolk", "townsfolk"), ("Is The Drunk", "isthedrunk"), ("About To Die", "abouttodie"),
    ("3 Attacks", "3attacks"), ("Dead - Don't Vote", "deaddontvote"), ("?", ""), ("X", "x"),
])
def test_reminder_key(text, key):
    """English reminder text maps onto the translation table's keys by dropping case and punctuation."""
    assert reminder_key(text) == key


def test_language_fill_translates_text(french):
    """With a language, the name, ability, and reminders come from the translation."""
    role = Role("washerwoman")
    assert french.fill_role(role) is True
    assert role.name == "Lavandière"
    assert role.ability.startswith("Lors de votre première nuit")
    # "Townsfolk" is translated; "Wrong" is not in the table and stays English
    assert role.reminders == ["Villageois", "Wrong"]
    # Language-neutral fields still come from the English feeds
    assert role.team == "townsfolk"
    assert role.first_night is True


def test_language_fill_falls_back_per_field(french):
    """Fields missing from a partial translation fall back to English one at a time."""
    drunk = Role("drunk")
    french.fill_role(drunk)
    assert drunk.name == "Ivrogne"
    assert drunk.ability.startswith("You do not know you are the Drunk")
    assert drunk.reminders == ["Est l'Ivrogne"]
    imp = Role("imp")
    french.fill_role(imp)
    assert imp.name == "Imp"
    assert imp.reminders == ["Mort"]


def test_language_fill_keeps_explicit_fields(french):
    """Text the script wrote is never replaced by a translation."""
    role = Role("washerwoman", name="Mine", reminders=["Townsfolk"])
    french.fill_role(role)
    assert role.name == "Mine"
    assert role.reminders == ["Townsfolk"]
    assert role.ability.startswith("Lors de votre première nuit")


def test_language_ignores_malformed_translation_entries(french):
    """Translation values that are not strings are treated as missing."""
    french.translations["washerwoman"] = {"name": 3, "ability": None}
    french.reminder_translations["townsfolk"] = ["x"]
    role = Role("washerwoman")
    french.fill_role(role)
    assert role.name == "Washerwoman"
    assert role.ability.startswith("You start knowing")
    assert role.reminders == ["Townsfolk", "Wrong"]


@pytest.mark.parametrize("language", [None, "en", "EN"])
def test_english_skips_translation_fetch(fake_feeds, language):
    """English needs no translation file."""
    data = OfficialData(language=language)
    data.load()
    assert translation_url("en") not in fake_feeds.calls
    role = Role("washerwoman")
    data.fill_role(role)
    assert role.name == "Washerwoman"


def test_unknown_language_is_error(fake_feeds):
    """A language with no translation file names the code and where to look."""
    with pytest.raises(OfficialDataError, match="'xx'.*translation.botc.app"):
        OfficialData(language="xx").load()


def test_translation_fetch_failure_is_error(fake_feeds):
    """Other fetch failures and bad JSON are reported as official data errors."""
    fake_feeds.routes[translation_url("fr")] = FetchError("boom")
    with pytest.raises(OfficialDataError, match="boom"):
        OfficialData(language="fr").load()
    fake_feeds.routes[translation_url("fr")] = b"not json"
    with pytest.raises(OfficialDataError):
        OfficialData(language="fr").load()


@pytest.mark.parametrize("body", [b"[]", b'{"roles": []}', b'{"roles": {"imp": "x"}}', b'{"reminders": []}'])
def test_translation_wrong_shape_is_error(fake_feeds, body):
    """A translation file that is not a dict of role dicts and a reminder dict is an error."""
    fake_feeds.routes[translation_url("fr")] = body
    with pytest.raises(OfficialDataError, match="Unexpected format"):
        OfficialData(language="fr").load()


def test_translation_without_sections_is_empty(fake_feeds):
    """A translation file that has no roles or reminders yet translates nothing."""
    fake_feeds.routes[translation_url("fr")] = b"{}"
    data = OfficialData(language="fr")
    data.load()
    role = Role("washerwoman")
    data.fill_role(role)
    assert role.name == "Washerwoman"
    assert role.reminders == ["Townsfolk", "Wrong"]
