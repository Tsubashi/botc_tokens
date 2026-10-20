"""Create print-n-play sheets from a script JSON."""
# Standard Library
import argparse
from contextlib import nullcontext
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import BadZipFile

# Third Party
import jsonschema
from rich import print
from rich.live import Live
from rich.markup import escape
from wand.exceptions import WandException
from wand.image import Image

# Application Specific
from ..helpers.icons import acquire_icon
from ..helpers.official_data import needs_official_data, OfficialData, OfficialDataError
from ..helpers.overrides import load_duplicates, load_icon_lookup, official_ids
from ..helpers.progress_group import setup_progress_group
from ..helpers.role import Role
from ..helpers.script_loader import load_script_source, parse_script, ParsedScript, script_slug, ScriptError, \
    ScriptSource
from ..helpers.sheet_builder import build_sheets, LayoutError, SheetLayout
from ..helpers.token_components import TokenComponents
from ..helpers.token_creation import create_reminder_token, create_role_token
from ..helpers.units import DEFAULT_DPI, mm_to_px, PAPER_SIZES_MM

DEFAULT_ROLE_DIAMETER_MM = 46.0
DEFAULT_REMINDER_DIAMETER_MM = 26.0
DEFAULT_MARGIN_MM = 6.27
DEFAULT_PADDING_MM = 0.0
DEFAULT_PAPER_TYPE = "letter"
MAX_OPTION_VALUE = 1_000_000


def _checked_number(text: str, convert, allow_zero: bool):
    """Convert a command line number, rejecting non-finite, negative, and (unless allowed) zero values."""
    try:
        number = convert(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a number") from None
    if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        raise argparse.ArgumentTypeError(f"'{text}' must be {'zero or more' if allow_zero else 'greater than zero'}")
    if number > MAX_OPTION_VALUE:
        raise argparse.ArgumentTypeError(f"'{text}' must be at most {MAX_OPTION_VALUE}")
    return number


def _positive_int(text: str) -> int:
    """Parse a whole number greater than zero."""
    return _checked_number(text, int, allow_zero=False)


def _positive_float(text: str) -> float:
    """Parse a number greater than zero."""
    return _checked_number(text, float, allow_zero=False)


def _non_negative_float(text: str) -> float:
    """Parse a number that is zero or more."""
    return _checked_number(text, float, allow_zero=True)


def _parse_args():
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser(
        prog="botc_tokens create",
        usage="%(prog)s [OPTIONS LISTED BELOW] [script_path_or_URL]",
        description="Create print-n-play sheets from a script JSON.")
    parser.add_argument("script", metavar="script_path_or_URL", type=str,
                        help="The location of the script JSON for which to create the print-n-play sheets. "
                             "Can be a file path or a URL.")
    parser.add_argument("-o", "--output-dir", type=str, default=".",
                        help="Where to save the print-n-play sheets. (Default: '.')")
    parser.add_argument("-m", "--intermediate-dir", type=str, default=None,
                        help="Optional path to store intermediate output such as icons and generated tokens. "
                             "Useful for storing a cache, or if you want to use the individual token images. "
                             "(Default: None)")
    parser.add_argument("--incremental", action="store_true",
                        help="Don't overwrite existing tokens in the intermediate dir. "
                             "No effect if -m is not specified.")
    parser.add_argument("-c", "--components", type=str, default=None,
                        help="The directory or zip in which to find the token components. (leaves, backgrounds, etc.)")
    parser.add_argument("--dpi", type=_positive_int, default=DEFAULT_DPI,
                        help="The DPI to use for distance-to-pixel calculations, such as token diameters. "
                             f"(Default: {DEFAULT_DPI})")
    parser.add_argument("--role-diameter", type=_positive_float, default=DEFAULT_ROLE_DIAMETER_MM,
                        help="The diameter (in mm) to use for role tokens. Components will be resized to fit. "
                             f"(Default: {DEFAULT_ROLE_DIAMETER_MM})")
    parser.add_argument("--reminder-diameter", type=_positive_float, default=DEFAULT_REMINDER_DIAMETER_MM,
                        help="The diameter (in mm) to use for reminder tokens. Components will be resized to fit. "
                             f"(Default: {DEFAULT_REMINDER_DIAMETER_MM})")
    parser.add_argument("--skip-ability-text", action="store_true",
                        help="Don't include ability text on the role tokens.")
    parser.add_argument("--margin-horizontal", type=_non_negative_float, default=DEFAULT_MARGIN_MM,
                        help="The margin (in mm) between the left/right edge of the paper and the tokens. "
                             f"(Default: {DEFAULT_MARGIN_MM})")
    parser.add_argument("--margin-vertical", type=_non_negative_float, default=DEFAULT_MARGIN_MM,
                        help="The margin (in mm) between the top/bottom of the paper and the tokens. "
                             f"(Default: {DEFAULT_MARGIN_MM})")
    parser.add_argument("--padding", type=_non_negative_float, default=DEFAULT_PADDING_MM,
                        help=f"The padding (in mm) between tokens. (Default: {DEFAULT_PADDING_MM})")
    paper = parser.add_mutually_exclusive_group()
    default_width, default_height = PAPER_SIZES_MM[DEFAULT_PAPER_TYPE]
    paper.add_argument("--paper-size", nargs=2, type=_positive_float, metavar=("PAPER_WIDTH", "PAPER_HEIGHT"),
                       default=None,
                       help="The width and height (in mm) of the paper to use for the tokens. "
                            f"Cannot be used with --paper-type (Default: {default_width} {default_height})")
    paper.add_argument("--paper-type", type=str, choices=list(PAPER_SIZES_MM), metavar="PAPER_TYPE", default=None,
                       help="The name of the type of paper to use for the tokens. "
                            f"One of: [{', '.join(PAPER_SIZES_MM)}]. Cannot be used with --paper-size "
                            f"(Default: {DEFAULT_PAPER_TYPE})")
    parser.add_argument("--duplicates", type=str, default=None,
                        help="A json file containing the number of duplicates to add for each role.")
    parser.add_argument("--icon-lookup", type=str, default=None,
                        help="A json file mapping role IDs to icon URLs or paths, "
                             "used for roles that do not specify an image.")
    parser.add_argument("--grid", action="store_true",
                        help="Use a grid layout instead of close packing.")
    return parser.parse_args(sys.argv[2:])


class _Progress:
    """The overall progress bar and step line shown while creating sheets."""

    def __init__(self):
        """Set up the progress bars."""
        self.group, self._overall, self._steps = setup_progress_group()
        self._overall_task = self._overall.add_task("Creating print-n-play sheets...", total=None)
        self._step_task = self._steps.add_task("Starting...")

    def phase(self, description: str, total: int | None = None) -> None:
        """Start a new phase, optionally with a known number of steps."""
        self._overall.update(self._overall_task, description=description, total=total, completed=0)
        self._steps.update(self._step_task, description=description)

    def step(self, description: str) -> None:
        """Describe the current step."""
        self._steps.update(self._step_task, description=description)

    def advance(self) -> None:
        """Mark a step of the current phase as done."""
        self._overall.update(self._overall_task, advance=1)


def _build_layout(args) -> SheetLayout:
    """Convert the physical page options into a pixel sheet layout."""
    width_mm, height_mm = args.paper_size if args.paper_size else PAPER_SIZES_MM[args.paper_type or DEFAULT_PAPER_TYPE]
    dpi = args.dpi
    return SheetLayout(
        page_width=mm_to_px(width_mm, dpi),
        page_height=mm_to_px(height_mm, dpi),
        margin_horizontal=mm_to_px(args.margin_horizontal, dpi),
        margin_vertical=mm_to_px(args.margin_vertical, dpi),
        padding=mm_to_px(args.padding, dpi),
        role_diameter=mm_to_px(args.role_diameter, dpi),
        reminder_diameter=mm_to_px(args.reminder_diameter, dpi),
        dpi=dpi,
        close_packing=not args.grid,
    )


def _load_overrides(args) -> tuple[dict[str, int], dict[str, str]] | None:
    """Load the duplicate counts and icon lookup, or report the problem and return None."""
    try:
        return load_duplicates(args.duplicates), load_icon_lookup(args.icon_lookup)
    except jsonschema.ValidationError as e:
        print(f"[red]Error:[/] An override file does not match its schema: {escape(e.message)}")
    except (OSError, ValueError) as e:
        print(f"[red]Error:[/] Unable to load an override file: {escape(str(e))}")
    return None


def _load_components(component_package: str | None) -> TokenComponents | None:
    """Load the token components, or report the problem and return None."""
    try:
        components = TokenComponents(component_package)
    except (OSError, BadZipFile, WandException) as e:
        print(f"[red]Error:[/] Unable to load components from '{escape(str(component_package))}': {escape(str(e))}")
        return None
    if components.fallbacks:
        print(f"Using built-in components for: {escape(', '.join(components.fallbacks))}")
    return components


def _load_roles(args) -> tuple[ParsedScript, ScriptSource] | None:
    """Load and parse the script, or report the problem and return None."""
    try:
        source = load_script_source(args.script)
        parsed = parse_script(source)
    except ScriptError as e:
        print(f"[red]Error:[/] {escape(str(e))}")
        return None
    return parsed, source


def _resolve_official(roles: list[Role], lookup: dict[str, str]) -> list[Role]:
    """Fill roles from the official data, assign lookup icons, and finalize them.

    Bare references that are not official roles are reported and dropped. Raises OfficialDataError if the official
    data is needed but cannot be loaded.
    """
    known_ids = official_ids()
    official = None
    if needs_official_data(roles, known_ids):
        official = OfficialData()
        official.load()
    resolved = []
    for role in roles:
        needs_fill = role.is_reference() or (role.has_gaps() and role.normalized_id in known_ids)
        if official is not None and needs_fill and not official.fill_role(role) and role.is_reference():
            print(f"[red]Error:[/] '{escape(role.id)}' is not an official role and the script does not define it; "
                  "skipping.")
            continue
        if role.icon is None:
            role.icon = lookup.get(role.normalized_id)
        role.finalize()
        resolved.append(role)
    return resolved


def _open_icon(icon_path: Path | None, role: Role) -> Image | None:
    """Open a cached icon, deleting it and returning None if it cannot be read."""
    if icon_path is None:
        return None
    try:
        return Image(filename=str(icon_path))
    except WandException as e:
        print(f"[yellow]Warning:[/] The cached icon {escape(str(icon_path))} for {escape(role.name or role.id)} could "
              f"not be read ({escape(str(e))}); deleting it and creating the tokens without an icon.")
        icon_path.unlink(missing_ok=True)
        return None


def _render_role(role: Role, icon_path: Path | None, components: TokenComponents, tokens_dir: Path, args) -> int:
    """Render a role's token and reminder tokens, returning how many were written."""
    targets: list[tuple[Path, str | None]] = [(tokens_dir / f"{role.slug}.png", None)]
    targets += [
        (tokens_dir / f"{role.slug}-reminder-{number}.png", text)
        for number, text in enumerate(role.reminders or [], start=1)
    ]
    if args.incremental:
        targets = [(path, text) for path, text in targets if not path.exists()]
    if not targets:
        return 0
    icon = _open_icon(icon_path, role)
    try:
        for path, text in targets:
            if text is None:
                token = create_role_token(
                    icon, role, components, mm_to_px(args.role_diameter, args.dpi), args.skip_ability_text
                )
            else:
                token = create_reminder_token(icon, text, components, mm_to_px(args.reminder_diameter, args.dpi))
            with token:
                token.save(filename=str(path))
    finally:
        if icon is not None:
            icon.close()
    return len(targets)


def _make_tokens(
        roles: list[Role],
        components: TokenComponents,
        icons_dir: Path,
        tokens_dir: Path,
        args,
        progress: _Progress
) -> int:
    """Acquire icons and render the tokens for each distinct role, returning how many token files were written."""
    unique: dict[str, Role] = {}
    for role in roles:
        unique.setdefault(role.slug, role)

    progress.phase("Downloading icons...", total=len(unique))
    icons: dict[str, Path | None] = {}
    for slug, role in unique.items():
        progress.step(f"Getting icon for {escape(role.name or role.id)}")
        icons[slug] = acquire_icon(role, icons_dir, args.incremental)
        if icons[slug] is None:
            print(f"[yellow]Warning:[/] {escape(role.name or role.id)} has no icon; "
                  "creating its tokens without one.")
        progress.advance()

    progress.phase("Creating tokens...", total=len(unique))
    written = 0
    for slug, role in unique.items():
        progress.step(f"Creating tokens for {escape(role.name or role.id)}")
        written += _render_role(role, icons[slug], components, tokens_dir, args)
        progress.advance()
    return written


def _create(
        args,
        layout: SheetLayout,
        duplicates: dict[str, int],
        lookup: dict[str, str],
        components: TokenComponents,
        intermediate: Path
) -> int:
    """Run the pipeline from script to sheets, returning the exit code."""
    progress = _Progress()
    with Live(progress.group):
        progress.phase("Reading script...")
        loaded = _load_roles(args)
        if loaded is None:
            return 1
        parsed, source = loaded

        progress.phase("Resolving roles...")
        try:
            roles = _resolve_official(parsed.roles, lookup)
        except OfficialDataError as e:
            print(f"[red]Error:[/] {escape(str(e))}")
            return 1
        skipped = len(parsed.roles) - len(roles)
        if not roles:
            print("[red]Error:[/] No roles left to create tokens for.")
            return 1

        icons_dir = intermediate / "icons"
        tokens_dir = intermediate / f"tokens_{script_slug(parsed, source)}"
        icons_dir.mkdir(parents=True, exist_ok=True)
        tokens_dir.mkdir(parents=True, exist_ok=True)
        _make_tokens(roles, components, icons_dir, tokens_dir, args, progress)

        progress.phase("Laying out sheets...")
        role_count, reminder_count = build_sheets(roles, tokens_dir, Path(args.output_dir), layout, duplicates)
    print(f"[green]Created {role_count} role tokens and {reminder_count} reminder tokens; skipped {skipped} roles.[/]")
    return 0


def run() -> int:
    """Create print-n-play sheets from a script JSON."""
    args = _parse_args()
    output_dir = Path(args.output_dir)
    if output_dir.exists() and not output_dir.is_dir():
        print(f"[red]Error:[/] The output directory {escape(str(output_dir))} exists and is not a directory.")
        return 1
    layout = _build_layout(args)
    try:
        layout.validate()
    except LayoutError as e:
        print(f"[red]Error:[/] {escape(str(e))}")
        return 1
    overrides = _load_overrides(args)
    if overrides is None:
        return 1
    duplicates, lookup = overrides
    components = _load_components(args.components)
    if components is None:
        return 1
    try:
        intermediate = TemporaryDirectory() if args.intermediate_dir is None else nullcontext(args.intermediate_dir)
        with intermediate as intermediate_dir:
            return _create(args, layout, duplicates, lookup, components, Path(intermediate_dir))
    except (OSError, WandException) as e:  # Unwritable output dirs, or components (such as fonts) that fail to render
        print(f"[red]Error:[/] {escape(str(e))}")
        return 1
    finally:
        components.close()
