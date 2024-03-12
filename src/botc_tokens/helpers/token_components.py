"""A simple class for preloading token components."""
from pathlib import Path
from tempfile import TemporaryDirectory
import zipfile

from wand.image import Image


class TokenComponents:
    """A simple class for preloading token components."""

    def __init__(self, component_package):
        """Load all the token components (backgrounds, leaves, etc.).

        Args:
            component_package (str): The directory or zip file in which to find the token components.
        """
        self.comp_path = Path(component_package)
        self._load_components()

    def _load_components(self):
        """Load the token components."""
        temp_dir = TemporaryDirectory()
        if self.comp_path.is_file():
            with zipfile.ZipFile(self.comp_path, "r") as zip_ref:
                self.comp_path = Path(temp_dir.name)
                zip_ref.extractall(temp_dir.name)

        self.role_bg = Image(filename=self.comp_path / "TokenBG.png")
        self.reminder_bg = Image(filename=self.comp_path / "ReminderBG.png")
        self.leaves = [
            Image(filename=self.comp_path / "Leaf1.png"),
            Image(filename=self.comp_path / "Leaf2.png"),
            Image(filename=self.comp_path / "Leaf3.png"),
            Image(filename=self.comp_path / "Leaf4.png"),
            Image(filename=self.comp_path / "Leaf5.png"),
            Image(filename=self.comp_path / "Leaf6.png"),
            Image(filename=self.comp_path / "Leaf7.png"),
        ]
        self.left_leaf = Image(filename=self.comp_path / "LeafLeft.png")
        self.right_leaf = Image(filename=self.comp_path / "LeafRight.png")
        self.setup_flower = Image(filename=self.comp_path / "SetupFlower.png")

        self.AbilityTextFont = next(self.comp_path.glob("AbilityText.*"))
        self.ReminderTextFont = next(self.comp_path.glob("ReminderText.*"))
        self.RoleNameFont = next(self.comp_path.glob("RoleName.*"))

        # Clean up the temp directory
        temp_dir.cleanup()

    def get_reminder_bg(self):
        """Get the reminder background image."""
        return self.reminder_bg.clone()

    def get_role_bg(self):
        """Get the role background image."""
        return self.role_bg.clone()

    def close(self):
        """Close the token components."""
        self.role_bg.close()
        self.reminder_bg.close()
        for leaf in self.leaves:
            leaf.close()
        self.left_leaf.close()
        self.right_leaf.close()
        self.setup_flower.close()
