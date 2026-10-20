"""Generate the bundled icon lookup from the official Blood on the Clocktower release data."""
# Standard Library
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROLES_URL = "https://release.botc.app/resources/data/roles.json"
TREE_URL = "https://api.github.com/repos/ThePandemoniumInstitute/botc-release/git/trees/main?recursive=1"
ICON_BASE = "https://release.botc.app/resources/characters"
USER_AGENT = "botc_tokens-dev (+https://github.com/Tsubashi/botc_tokens)"
OUTPUT = Path(__file__).resolve().parent.parent / "src" / "botc_tokens" / "data" / "icon_lookup.json"
PREFERRED_SUFFIX = {
    "townsfolk": "_g",
    "outsider": "_g",
    "minion": "_e",
    "demon": "_e",
    "traveler": "",
    "traveller": "",
    "fabled": "",
}


def fetch_json(url: str) -> object:
    """Fetch and decode a JSON document."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def collect_icons(tree: dict) -> dict[str, str]:
    """Map each icon file stem to its edition-qualified path."""
    icons: dict[str, str] = {}
    prefix = "resources/characters/"
    for entry in tree["tree"]:
        path = entry["path"]
        if not path.startswith(prefix) or not path.endswith(".webp"):
            continue
        edition, _, filename = path[len(prefix):].partition("/")
        if filename and "/" not in filename:
            icons[filename[:-len(".webp")]] = f"{edition}/{filename}"
    return icons


def build_lookup(roles: list[dict], icons: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Build the id to icon URL lookup, returning it with the ids that have no icon."""
    lookup: dict[str, str] = {}
    missing: list[str] = []
    for role in roles:
        role_id = role["id"]
        key = role_id.lower().replace("_", "")
        preferred = PREFERRED_SUFFIX.get(role.get("team", ""), "_g")
        candidates = [role_id + preferred] + [role_id + s for s in ("_g", "_e", "")]
        found = next((icons[c] for c in candidates if c in icons), None)
        if found is None:
            missing.append(role_id)
        else:
            lookup[key] = f"{ICON_BASE}/{found}"
    return lookup, missing


def main() -> None:
    """Fetch the release data and write the lookup file."""
    roles = fetch_json(ROLES_URL)
    icons = collect_icons(fetch_json(TREE_URL))
    lookup, missing = build_lookup(roles, icons)
    for role_id in missing:
        print(f"No icon for {role_id}", file=sys.stderr)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        json.dump(lookup, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print(f"Wrote {len(lookup)} entries to {OUTPUT}")


if __name__ == "__main__":
    main()
