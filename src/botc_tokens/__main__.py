"""Main Script for m4b-util."""
import argparse
import sys

from rich import print

from .__version__ import version
from .commands import printable, create, update


def _print_version():
    """Print the current version, then exit."""
    print(f"[green]botc_tokens[/], Version '{version}'")
    return 0


# Set up the dictionary of commands. The values are tuples, first the function to run, second the description.
allowed_commands = {
    "printable": (printable.run, "Create printable sheets of roles and reminder from a json script file."),
    "tokens": (create.run, "Create token images to match json files in a directory tree."),
    "update": (update.run, "Download roles from the wiki, with associated icon and description."),
}


def main():
    """Run the application."""
    # Write our usage message
    usage = ("botc_tokens <command> [<args>]\n\n"
             "Allowed Commands:\n"
             )
    for name, (_, description) in allowed_commands.items():
        usage += f"{name:18}: {description}\n"
    usage += ("\nFor more help with a command, use m4b-util <command> --help\n"
              " \n"
              )

    # Set up argparse
    parser = argparse.ArgumentParser(
        prog="m4b-util",
        usage=usage
    )
    parser.add_argument('command', help='Subcommand to run')
    # parse_args defaults to [1:] for args, but we need to exclude the rest of the args so that they can be picked up by
    # the subcommands.
    args = parser.parse_args(sys.argv[1:2])

    # Make sure args.command is always lowercase
    args.command = args.command.lower()

    if args.command not in allowed_commands:
        print("[bold red]Error:[/] Unrecognized command")
        print(parser.print_help())
        exit(-1)

    # Invoke the subcommand
    retcode = allowed_commands[args.command][0]()

    print("[green]Done![/]")
    exit(retcode)


# We don't test coverage for this, since we don't test it directly.
# We just make it simple enough that we can trust it works.
if __name__ == "__main__":  # pragma: no cover
    main()  # pragma: no cover
