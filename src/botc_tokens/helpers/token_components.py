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
        "AbilityTextBold.*",
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
        if not self.comp_path.exists():
            raise FileNotFoundError(f"Component package not found: {self.comp_path}")

        # Create a temporary directory in case we need to unzip a package
        self.temp_dir = TemporaryDirectory(suffix=f"-{self.comp_path.name}")

        # Handle zipped packages
        if self.comp_path.is_file():
            # If it is a file, presume it's a zipped package regardless of extension
            self._unzip_package()
            # Reset comp_path to the unzipped package directory
            self.comp_path = Path(self.temp_dir.name)

        self._load_components()

    def _resolve(self, pattern: str) -> Path:
        """Find a component in the user package, falling back to the built-in one.

        Args:
            pattern (str): The required-file glob pattern to look for.

        Returns:
            Path: The matching file in the user package, else the built-in file.
        """
        try:
            return next(self.comp_path.glob(pattern))
        except StopIteration:
            return next(Path(default_component_path).glob(pattern))

    def _unzip_package(self):
        """Unzip the component package, only pulling the pieces we need."""
        with zipfile.ZipFile(self.comp_path, "r") as zip_ref:
            # Only pull what we expect. This will hopefully mitigate the risk of zip bombs or other unpleasantries.
            file_list = zip_ref.namelist()
            for file in self.required_files:
                # Search through all directories and find the first match. This allows us to accept zip packages
                # created through various means, and ignore any directory structure. Remove any wildcards from the
                # required file name. Absent components are skipped; they fall back to the built-in ones.
                try:
                    file_in_zip = next(f for f in file_list if file.replace("*", "") in f)
                except StopIteration:
                    continue
                source = zip_ref.open(file_in_zip)
                target = open(Path(self.temp_dir.name) / Path(file_in_zip).name, "wb")
                with source, target:
                    copyfileobj(source, target)

    def _load_components(self):
        """Load the token components."""
        # Record which components the package lacks (in required_files order); those use the built-in ones.
        self.fallbacks: list[str] = [f for f in self.required_files if next(self.comp_path.glob(f), None) is None]

        self.role_bg = Image(filename=self._resolve("TokenBG.png"))
        self.reminder_bg = Image(filename=self._resolve("ReminderBG.png"))
        self.leaves = [Image(filename=self._resolve(f"Leaf{i}.png")) for i in range(1, 8)]
        self.left_leaf = Image(filename=self._resolve("LeafLeft.png"))
        self.right_leaf = Image(filename=self._resolve("LeafRight.png"))
        self.setup_flower = Image(filename=self._resolve("SetupFlower.png"))

        self.AbilityTextFont = self._resolve("AbilityText.*")
        self.AbilityTextBoldFont = self._resolve("AbilityTextBold.*")
        self.ReminderTextFont = self._resolve("ReminderText.*")
        self.RoleNameFont = self._resolve("RoleName.*")

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
            source = self._resolve(file)
            copy(source, target_dir / source.name)

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
