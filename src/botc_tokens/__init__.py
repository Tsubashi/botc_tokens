"""Unofficial token tools for Blood on the Clocktower."""
from importlib.resources import files as package_data

from .helpers.bundled_imagemagick import activate

# Standalone binaries ship ImageMagick beside the executable. This must run before any submodule imports wand.
activate()

data_dir = package_data(__package__) / "data"
component_path = data_dir / "components"
