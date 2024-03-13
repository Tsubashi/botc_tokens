"""A simple class for preloading token components."""
# Standard Library
from pathlib import Path
from shutil import copy, copyfileobj
from tempfile import TemporaryDirectory
import zipfile

# Third Party
from wand.image import Image

# Application Specific
from .. import component_path as default_component_path


class TokenComponents:
    """A simple class for preloading token components."""
    required_files = [
        "TokenBG.png",
        "ReminderBG.png",
        "Leaf1.png",
        "Leaf2.png",
        "Leaf3.png",
        "Leaf4.png",
        "Leaf5.png",
        "Leaf6.png",
        "Leaf7.png",
        "LeafLeft.png",
        "LeafRight.png",
        "SetupFlower.png",
        "AbilityText.*",
        "ReminderText.*",
        "RoleName.*"
    ]

    def __init__(self, component_package=None):
        """Load all the token components (backgrounds, leaves, etc.).

        Args:
            component_package (str): The directory or zip file in which to find the token components.
        """
        # Load the components from our own package if none are specified
        if not component_package:
            component_package = default_component_path

        self.comp_path = Path(component_package)

        # Create a temporary directory in case we need to unzip a package
        self.temp_dir = TemporaryDirectory(suffix=f"-{self.comp_path.name}")

        # Handle zipped packages
        if self.comp_path.is_file():
            # If it is a file, presume it's a zipped package regardless of extension
            self._unzip_package()
            # Reset comp_path to the unzipped package directory
            self.comp_path = Path(self.temp_dir.name)

        self._load_components()

    def _verify_package(self):
        """Ensure that we have all the component pieces that we need."""
        for file in self.required_files:
            try:
                next(self.comp_path.glob(file))
            except StopIteration:
                raise FileNotFoundError(f"Missing required file: {file}")

    def _unzip_package(self):
        """Unzip the component package, only pulling the pieces we need."""
        with zipfile.ZipFile(self.comp_path, "r") as zip_ref:
            # Only pull what we expect. This will hopefully mitigate the risk of zip bombs or other unpleasantries.
            file_list = zip_ref.namelist()
            for file in self.required_files:
                # Search through all directories and find the first match. This allows us to accept zip packages
                # created through various means, and ignore any directory structure. Remove any wildcards from the
                # required file name.
                try:
                    file_in_zip = next(f for f in file_list if file.replace("*", "") in f)
                except StopIteration:
                    raise FileNotFoundError(f"Zip package is missing: {file}")
                source = zip_ref.open(file_in_zip)
                target = open(Path(self.temp_dir.name) / file, "wb")
                with source, target:
                    copyfileobj(source, target)

    def _load_components(self):
        """Load the token components."""
        # Make sure we have everything before we move forward.
        self._verify_package()

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

    def get_reminder_bg(self):
        """Get the reminder background image."""
        return self.reminder_bg.clone()

    def get_role_bg(self):
        """Get the role background image."""
        return self.role_bg.clone()

    def dump(self, target_dir):
        """Dump all component files to a target directory."""
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        for file in self.required_files:
            try:
                source = next(self.comp_path.glob(file))
            except StopIteration:
                raise FileNotFoundError(f"Unable to find '{file}' despite it being loaded. Perhaps the components "
                                        "package was modified after loading?")
            target = target_dir / source.name
            copy(source, target)

    def close(self):
        """Close the token components."""
        # Close all loaded image
        self.role_bg.close()
        self.reminder_bg.close()
        for leaf in self.leaves:
            leaf.close()
        self.left_leaf.close()
        self.right_leaf.close()
        self.setup_flower.close()

        # Clean up the temp directory
        self.temp_dir.cleanup()
