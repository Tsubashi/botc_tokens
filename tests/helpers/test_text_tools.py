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
    assert img.size == (68, 36)


def test_inline_brackets():
    """Bracketed should stay in line if they fit."""
    text = "This is a test of [setup effects]"
    img = text_tools.fit_ability_text(text, 12, 200, 10, TokenComponents())
    assert img.size == (161, 16)


def test_multiline_brackets(tmp_path):
    """Brackets that need to be split should start their own line."""
    text = "A [test of setup effects that most certainly cause wrapping before the bracket ends]"
    img = text_tools.fit_ability_text(text, 12, 100, 10, TokenComponents())
    assert img.height == 48  # Only check height on this one because GHA rounds differently than local.


def test_large_font():
    """Test that large fonts are used when requested."""
    text = "This is a long string that should be curved."
    img = text_tools.curved_text_to_image(
        text, "role", 100, TokenComponents(), use_large_fonts=True
    )
    assert img.size == (68, 37)


def test_wide_word_shrinks_font_instead_of_failing():
    """A single word wider than the first line is fitted by shrinking the font, not dropped as an empty line."""
    text = "Each night, the " + "W" * 20 + " player wakes."
    img = text_tools.fit_ability_text(text, 58, 554, 106, TokenComponents())
    assert img.width > 1 and img.height > 1


def test_zero_font_size_still_renders():
    """A font size that rounds to zero (tiny components) still produces an image instead of failing."""
    img = text_tools.fit_ability_text("Does a thing.", 0, 1, 1, TokenComponents())
    assert img.width >= 1 and img.height >= 1
