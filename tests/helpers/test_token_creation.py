"""Tests for token rendering."""
# Standard Library
from pathlib import Path

# Third Party
import pytest
from wand.image import Image

# Application Specific
from botc_tokens.helpers.role import Role
from botc_tokens.helpers.token_components import TokenComponents
from botc_tokens.helpers.token_creation import (
    create_reminder_token,
    create_role_token,
    fit_icon,
)


@pytest.fixture(scope="module")
def components():
    """Provide the built-in component package."""
    package = TokenComponents()
    yield package
    package.close()


@pytest.fixture
def padded_icon(test_data_dir: Path):
    """Provide the padded icon fixture."""
    with Image(filename=str(test_data_dir / "icons" / "padded.png")) as image:
        yield image


@pytest.fixture
def role():
    """Provide a role with reminders and every modifier."""
    return Role(
        id="test", name="Test Role", team="townsfolk", ability="Each night, learn something.",
        reminders=["One", "Two", "Three"], first_night=True, other_nights=True, affects_setup=True,
    )


def test_role_token_size_and_leaves(padded_icon, role, components):
    """A role token with leaves, modifiers, and an icon has the requested size."""
    token = create_role_token(padded_icon, role, components, 200, False)
    assert token.size == (200, 200)
    assert padded_icon.size == (100, 100)
    token.close()


def test_role_token_without_icon(padded_icon, role, components):
    """Omitting the icon leaves the token center showing only the background."""
    with create_role_token(None, role, components, 200, True) as bare:
        with create_role_token(padded_icon, role, components, 200, True) as with_icon:
            assert bare.size == (200, 200)
            assert bare[100, 100] != with_icon[100, 100]
        with create_role_token(None, role, components, 200, True) as again:
            assert bare[100, 100] == again[100, 100]


def test_role_token_skip_ability_text(padded_icon, role, components):
    """A role token without ability text still honors the requested size."""
    with create_role_token(padded_icon, role, components, 150, True) as token:
        assert token.size == (150, 150)


def test_reminder_token(padded_icon, components):
    """A reminder token has the requested size, with or without an icon."""
    with create_reminder_token(padded_icon, "some thing", components, 100) as token:
        assert token.size == (100, 100)
    with create_reminder_token(None, "some thing", components, 100) as token:
        assert token.size == (100, 100)


def test_fit_icon_preserves_aspect():
    """Fitting a 100x50 icon into a 60 box yields 60x30."""
    with Image(width=100, height=50) as icon:
        fit_icon(icon, 60)
        assert icon.size == (60, 30)
