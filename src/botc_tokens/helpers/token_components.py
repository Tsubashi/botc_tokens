"""A simple class for preloading token components."""
from pathlib import Path

from wand.image import Image


class TokenComponents:
    """A simple class for preloading token components."""

    def __init__(self, component_dir):
        """Initialize the TokenComponents class.

        Args:
            component_dir (str): The directory in which to find the token components files. (leaves, backgrounds, etc.)
        """
        self.comp_path = Path(component_dir)
        self._load_components()

    def _load_components(self):
        """Load the token components."""
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
