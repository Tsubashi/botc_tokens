"""Missing tests for the text tools."""
# Standard Library

# Third Party

# Application Specific
from botc_tokens.helpers import text_tools
from botc_tokens.helpers.token_components import TokenComponents


def test_empty_ability_text():
    """Test that an empty string returns an empty image."""
    img = text_tools.fit_ability_text("", 12, 100, 10, None)
    assert img.size == (1, 1)


def test_long_ability_text():
    """Test that a long string gets split into multiple lines."""
    text = "This is a long string that should be split into multiple lines."
    img = text_tools.fit_ability_text(text, 12, 100, 10, TokenComponents())
    assert img.size == (114, 67)


def test_empty_curved_text():
    """Test that an empty string returns an empty image."""
    img = text_tools.curved_text_to_image("", "reminder", 100, None)
    assert img.size == (1, 1)


def test_long_curved_text():
    """Test that a long string gets curved."""
    text = "This is a long string that should be curved."
    img = text_tools.curved_text_to_image(text, "role", 100, TokenComponents())
    assert img.size == (72, 57)
