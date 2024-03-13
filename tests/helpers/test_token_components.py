"""Make sure that the token components are loading as expected."""
# Standard Library
import zipfile

# Third Party Libraries
import pytest

# Application Specific
from botc_tokens import component_path
from botc_tokens.helpers.token_components import TokenComponents


@pytest.fixture()
def zipped_package(component_package):
    """Create a zipped token component package."""
    zip_path = component_package.parent / "dump.zip"
    with zipfile.ZipFile(zip_path, "w") as zip_ref:
        for file in component_package.iterdir():
            zip_ref.write(file, file.name)
    return zip_path


@pytest.fixture()
def zipped_incomplete_package(component_package):
    """Create a zipped token component package."""
    # Remove a file
    (component_package / "TokenBG.png").unlink()

    # Zip up the dumped token components
    zip_path = component_package.parent / "dump.zip"
    with zipfile.ZipFile(zip_path, "w") as zip_ref:
        for file in component_package.iterdir():
            zip_ref.write(file, file.name)
    return zip_path


def test_token_components_creation():
    """Test that the token components are created as expected."""
    # Create the token components
    token_components = TokenComponents()

    # Verify that we created something.
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


def test_token_components_dump(tmp_path):
    """Test that the token components are dumped as expected."""
    # Create the token components
    token_components = TokenComponents(component_path)

    # Dump the token components
    dump_path = tmp_path / "dump"
    token_components.dump(dump_path)
    for file in token_components.required_files:
        assert next(dump_path.glob(file))


def test_token_components_zipped(zipped_package):
    """Load a zipped package and verify the token components."""
    token_components = TokenComponents(zipped_package)
    assert token_components.setup_flower

    # Close the token components
    token_components.close()


def test_token_components_missing_files(component_package):
    """Fail to load a package with missing files."""
    # Remove a file
    (component_package / "TokenBG.png").unlink()

    # Try to load the components
    with pytest.raises(FileNotFoundError):
        token_components = TokenComponents(component_package)
        token_components.close()


def test_token_components_zipped_incomplete(zipped_incomplete_package):
    """Fail to load a zipped package with missing files."""
    with pytest.raises(FileNotFoundError):
        token_components = TokenComponents(zipped_incomplete_package)
        token_components.close()


def test_token_compoents_modified_package(tmp_path, component_package):
    """Fail to dump a package that has been modified after loading."""
    token_components = TokenComponents(component_package)
    (component_package / "TokenBG.png").unlink()
    with pytest.raises(FileNotFoundError):
        token_components.dump(tmp_path)
        token_components.close()
