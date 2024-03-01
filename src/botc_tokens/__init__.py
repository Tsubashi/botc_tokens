"""Unofficial token tools for Blood on the Clocktower."""
from importlib.resources import files as package_data

data_dir = package_data(__package__) / "data"
component_path = data_dir / "components"
