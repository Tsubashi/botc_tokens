import json
from pathlib import Path
import argparse
from rich import print
from rich.progress import track


def main(args):
    """One script to find them all, and in the JSON bind them!"""
    json_files = Path(args.dir).rglob("*.json")
    roles = []
    for json_file in track(json_files, description="Reading JSON files"):
        with open(json_file, "r") as f:
            data = json.load(f)
        # Rewrite the icon path to be relative to the roles.json file
        data['icon'] = str(json_file.parent / data.get('icon'))
        roles.append(data)
    print(f"[green]Writing to {args.output_file}...[/]", end="")
    with open(args.output_file, "w") as f:
        json.dump(roles, f)
    print("[bold green]Done![/]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Read all json file in a directory tree and create a master list.')
    parser.add_argument('dir', type=str, default="results", nargs="?",
                        help='The top level directory in which to begin the search.')
    parser.add_argument('output_file', type=str, default='roles.json', nargs="?",
                        help="Path to output file. (Default: 'roles.json')")
    args = parser.parse_args()
    main(args)
    print("--Done!--")
