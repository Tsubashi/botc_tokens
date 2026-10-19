"""Functions for creating tokens."""
# Standard Library
import string

# Third Party
from wand.image import Image

# Application Specific
from .role import Role
from .text_tools import curved_text_to_image, fit_ability_text
from .token_components import TokenComponents


ROLE_ICON_BOX_WITH_TEXT = 0.72
ROLE_ICON_BOX_NO_TEXT = 1.0
REMINDER_ICON_BOX = 1.0
ROLE_ICON_SHIFT_WITH_TEXT = 0.075
ROLE_ICON_SHIFT_NO_TEXT = -0.05


def fit_icon(icon: Image, box: int) -> None:
    """Scale an icon in place to fit within a square box, preserving aspect ratio.

    Args:
        icon: The icon to scale. Icons are already padded, so the whole canvas is scaled as a unit.
        box: The side length (in pixels) of the square box.
    """
    icon.transform(resize=f"{box}x{box}")


def create_reminder_token(icon: Image | None, reminder_text: str, components: TokenComponents, diameter: int) -> Image:
    """Create a reminder token.

    Args:
        icon: The padded icon to use for the reminder, or None to omit the icon. It is not closed.
        reminder_text: The text to be displayed on the reminder token.
        components: The component package to use.
        diameter: The diameter (in pixels) to use for reminder tokens. Components will be resized to fit.

    Returns:
        The reminder token image.
    """
    reminder = components.get_reminder_bg()
    icon_height = 0
    if icon is not None:
        reminder_icon = icon.clone()
        fit_icon(reminder_icon, int(reminder.width * REMINDER_ICON_BOX))
        icon_height = reminder_icon.height
        reminder_icon_x = (reminder.width - reminder_icon.width) // 2
        reminder_icon_y = (reminder.height - reminder_icon.height - int(reminder.height * 0.15)) // 2
        reminder.composite(reminder_icon, left=reminder_icon_x, top=reminder_icon_y)
        reminder_icon.close()
    # Add the reminder text
    text_img = curved_text_to_image(string.capwords(reminder_text), "reminder", reminder.width, components)
    text_x = (reminder.width - text_img.width) // 2
    text_y = (reminder.height - text_img.height - int(icon_height * 0.05))
    reminder.composite(text_img, left=text_x, top=text_y)
    text_img.close()
    # Resize to requested diameter
    reminder.resize(width=diameter, height=diameter)
    return reminder


def create_role_token(
        icon: Image | None,
        role: Role,
        components: TokenComponents,
        diameter: int,
        skip_ability_text: bool) -> Image:
    """Create a role token.

    Args:
        icon: The padded icon to use for the role, or None to omit the icon. It is not closed.
        role: The role data to use for the token.
        components: The component package to use.
        diameter: The diameter (in pixels) to use for role tokens.
        skip_ability_text: Whether to omit the ability text from the role token.

    Returns:
        The role token image.
    """
    # Check if we have reminders. If so, add leaves.
    token = components.get_role_bg()
    for leaf in components.leaves[:len(role.reminders)]:
        token.composite(leaf, left=0, top=0)

    # Place the icon. With ability text the icon is smaller and moves down to make room;
    # without it the icon uses the free space.
    if icon is not None:
        if skip_ability_text:
            box, shift = ROLE_ICON_BOX_NO_TEXT, ROLE_ICON_SHIFT_NO_TEXT
        else:
            box, shift = ROLE_ICON_BOX_WITH_TEXT, ROLE_ICON_SHIFT_WITH_TEXT
        token_icon = icon.clone()
        fit_icon(token_icon, int(token.width * box))
        icon_x = (token.width - token_icon.width) // 2
        icon_y = ((token.height - token_icon.height) // 2) + int(token.height * shift)
        token.composite(token_icon, left=icon_x, top=icon_y)
        token_icon.close()
    # Check for modifiers
    if role.first_night:
        token.composite(components.left_leaf, left=0, top=0)
    if role.other_nights:
        token.composite(components.right_leaf, left=0, top=0)
    if role.affects_setup:
        token.composite(components.setup_flower, left=0, top=0)
    # Add ability text to the token
    if not skip_ability_text:
        ability_text_img = fit_ability_text(
            text=role.ability,
            font_size=int(token.height * 0.055),
            first_line_width=int(token.width * .52),
            step=int(token.width * .1),
            components=components
        )
        ability_text_x = (token.width - ability_text_img.width) // 2
        token.composite(ability_text_img, left=ability_text_x, top=int(token.height * 0.09))
        ability_text_img.close()
    # Add the role name to the token
    text_img = curved_text_to_image(role.name, "role", token.width, components, skip_ability_text)
    text_x = (token.width - text_img.width) // 2
    text_y = (token.height - text_img.height - int(token.height * 0.06))
    token.composite(text_img, left=text_x, top=text_y)
    text_img.close()

    # Resize to requested diameter
    token.resize(width=diameter, height=diameter)
    return token
