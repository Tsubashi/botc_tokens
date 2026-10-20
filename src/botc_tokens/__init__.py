"""Unofficial token tools for Blood on the Clocktower."""
from importlib.resources import files as package_data

from .helpers.bundled_imagemagick import activate, find_data_dir, installation_dir

# Standalone binaries ship ImageMagick beside the executable. This must run before any submodule imports wand.
activate()

# Standalone binaries also keep the package data beside the executable, since Nuitka cannot place a botc_tokens/ folder
# next to an executable of the same name.
data_dir = find_data_dir(installation_dir()) or package_data(__package__) / "data"
component_path = data_dir / "components"
