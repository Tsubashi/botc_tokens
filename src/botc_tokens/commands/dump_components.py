"""Enable users to dump all the default components to a directory."""
# Standard Library
import argparse
import sys

# Third Party
from rich import print

# Application Specific
from ..helpers.token_components import TokenComponents


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="botc_tokens dump-components",
        description='Write all the default components to the specified directory.')
    parser.add_argument('output_dir', type=str, default="new_component_package", nargs="?",
                        help='The directory in which to output the components. (Default: "new_component_package")')
    args = parser.parse_args(sys.argv[2:])
    return args


def run():
    """Write all the default components to the specified directory."""
    args = _parse_args()
    components = TokenComponents()
    print(f"[bold]Writing components to {args.output_dir}...[/]")
    try:
        components.dump(args.output_dir)
    except FileNotFoundError as e:
        print("[red]Error:[/][bold]The package is somehow missing a required component. Please report this bug: "
              f"{str(e)}")
