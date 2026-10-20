"""Enable users to dump the built-in defaults to a directory so they can be customized."""
# Standard Library
import argparse
from pathlib import Path
from shutil import copy
import sys

# Third Party
from rich import print
from rich.markup import escape

# Application Specific
from .. import data_dir
from ..helpers.token_components import TokenComponents


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="botc_tokens dump",
        description="Write the built-in defaults to a directory so they can be customized and passed back in.")
    parser.add_argument('what', type=str, choices=["components", "duplicates", "icon-lookup", "all"],
                        help="Which defaults to write. 'components' writes the token component pack, 'duplicates' "
                             "writes duplicates.json, 'icon-lookup' writes icon_lookup.json, 'all' writes "
                             "everything.")
    parser.add_argument('output_dir', type=str, default="botc_tokens_defaults", nargs="?",
                        help='The directory in which to write the files. (Default: "botc_tokens_defaults")')
    return parser.parse_args(sys.argv[2:])


def _dump_components(target_dir):
    print(f"[bold]Writing components to {target_dir}...[/]")
    components = TokenComponents()
    try:
        components.dump(target_dir)
    finally:
        components.close()


def _dump_json(source_name, target):
    print(f"[bold]Writing {target.name} to {target.parent}...[/]")
    target.parent.mkdir(parents=True, exist_ok=True)
    copy(data_dir / source_name, target)


def run():
    """Write the requested built-in defaults to the specified directory."""
    args = _parse_args()
    output_dir = Path(args.output_dir)
    what = args.what

    try:
        if what == "all":
            _dump_components(output_dir / "components")
        elif what == "components":
            _dump_components(output_dir)
        if what in ("duplicates", "all"):
            _dump_json("known_duplicates.json", output_dir / "duplicates.json")
        if what in ("icon-lookup", "all"):
            _dump_json("icon_lookup.json", output_dir / "icon_lookup.json")
    except OSError as e:
        print(f"[red]Error:[/] Unable to write to {escape(str(output_dir))}: {escape(str(e))}")
        return 1
    return 0
