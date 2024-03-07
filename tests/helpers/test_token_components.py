"""Make sure that the token components are loading as expected."""
# Standard Library

# Third Party Libraries

# Application Specific
from botc_tokens.helpers.token_components import TokenComponents
from botc_tokens import component_path


def test_token_components_creation():
    """Test that the token components are created as expected."""
    # Create the token components
    token_components = TokenComponents(component_path)

    # Check that the token components are created as expected
    assert token_components.role_bg
    assert token_components.reminder_bg
    assert token_components.leaves
    assert token_components.left_leaf
    assert token_components.right_leaf
    assert token_components.setup_flower

    # Close the token components
    token_components.close()


def test_token_components_clone_bgs():
    """Test that the token components are cloned as expected."""
    # Create the token components
    token_components = TokenComponents(component_path)

    # Check that the token components are created as expected
    reminder_bg = token_components.get_reminder_bg()
    assert reminder_bg
    reminder_bg.close()

    role_bg = token_components.get_role_bg()
    assert role_bg
    role_bg.close()

    # Close the token components
    token_components.close()
