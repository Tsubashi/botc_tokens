"""Functions for creating tokens."""
# Standard Library
import string

# Third Party
from wand.image import Image

# Application Specific
from .role import Role
from .text_tools import curved_text_to_image, fit_ability_text
from .token_components import TokenComponents


def create_reminder_token(reminder_icon, reminder_text, components, diameter):
    """Create and save a reminder token.

    Args:
        reminder_icon (wand.image.Image): The icon to be used for the reminder.
        reminder_text (str): The text to be displayed on the reminder token.
        components (TokenComponents): The component package to use.
        diameter (int): The diameter (in pixels) to use for reminder tokens. Components will be resized to fit.
    """
    reminder = components.get_reminder_bg()
    reminder_icon_x = (reminder.width - reminder_icon.width) // 2
    reminder_icon_y = (reminder.height - reminder_icon.height - int(reminder.height * 0.15)) // 2
    reminder.composite(reminder_icon, left=reminder_icon_x, top=reminder_icon_y)
    # Add the reminder text
    text_img = curved_text_to_image(string.capwords(reminder_text), "reminder", reminder.width, components)
    text_x = (reminder.width - text_img.width) // 2
    text_y = (reminder.height - text_img.height - int(reminder_icon.height * 0.05))
    reminder.composite(text_img, left=text_x, top=text_y)
    text_img.close()
    # Resize to requested diameter
    reminder.resize(width=diameter, height=diameter)
    return reminder


def create_role_token(token_icon: Image, role: Role, components: TokenComponents, diameter: int):
    """Create and save a role token.

    Args:
        token_icon (wand.image.Image): The icon to be used for the role.
        role (dict): The role data to use for the token.
        components (TokenComponents): The component package to use.
        diameter (int): The diameter (in pixels) to use for role tokens.
    """
    # Adjust icon size
    # The "^" modifier means this transform specifies the minimum height and width.
    # A transform without a modifier specifies the maximum height and width.
    target_width = components.role_bg.width * 0.6
    target_height = components.role_bg.height * 0.5
    token_icon.transform(resize=f"{target_width}x{target_height}^")
    token_icon.transform(resize=f"{target_width}x{target_height}")

    # Check if we have reminders. If so, add leaves.
    token = components.get_role_bg()
    for leaf in components.leaves[:len(role.reminders)]:
        token.composite(leaf, left=0, top=0)

    # Determine where to place the icon
    icon_x = (token.width - token_icon.width) // 2
    icon_y = (token.height - token_icon.height + int(token.height * 0.15)) // 2
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
    text_img = curved_text_to_image(role.name, "role", token.width, components)
    text_x = (token.width - text_img.width) // 2
    text_y = (token.height - text_img.height - int(token.height * 0.08))
    token.composite(text_img, left=text_x, top=text_y)
    text_img.close()

    # Resize to requested diameter
    token.resize(width=diameter, height=diameter)
    return token
