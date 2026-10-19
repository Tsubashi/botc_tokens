"""Lay out role and reminder tokens onto printable sheets."""
# Standard Library
from dataclasses import dataclass
from pathlib import Path

# Third Party
from rich import print
from rich.markup import escape

# Application Specific
from .printable import Printable
from .role import Role


class LayoutError(ValueError):
    """The sheet layout cannot hold any tokens."""


@dataclass
class SheetLayout:
    """Page geometry for printable sheets. All values are in pixels."""
    page_width: int
    page_height: int
    margin_horizontal: int
    margin_vertical: int
    padding: int
    role_diameter: int
    reminder_diameter: int
    dpi: int
    close_packing: bool

    def validate(self) -> None:
        """Raise LayoutError if the layout leaves no room for tokens."""
        printable_width = self.page_width - 2 * self.margin_horizontal
        printable_height = self.page_height - 2 * self.margin_vertical
        if printable_width <= 0:
            raise LayoutError("The horizontal margin is too large for the page width.")
        if printable_height <= 0:
            raise LayoutError("The vertical margin is too large for the page height.")
        for label, diameter in (("role", self.role_diameter), ("reminder", self.reminder_diameter)):
            if diameter > printable_width or diameter > printable_height:
                raise LayoutError(f"The {label} token diameter ({diameter}px) does not fit in the printable area.")

    def close_packing_fits(self, diameter: int) -> bool:
        """Return whether a close-packed inset row of tokens of this diameter fits in the printable width."""
        return self.page_width - 2 * self.margin_horizontal >= 1.5 * diameter + self.padding


def _close_packing(layout: SheetLayout, label: str, diameter: int) -> bool:
    """Return whether to close pack a sheet, warning and falling back to a grid if inset rows would be clipped."""
    if layout.close_packing and not layout.close_packing_fits(diameter):
        print(f"[yellow]Warning:[/] The page is too narrow to close pack {label} tokens; using a grid layout for them.")
        return False
    return layout.close_packing


def build_sheets(
        roles: list[Role],
        tokens_dir: Path,
        output_dir: Path,
        layout: SheetLayout,
        duplicates: dict[str, int]
) -> tuple[int, int]:
    """Place role and reminder tokens in script order and write roles.pdf and reminders.pdf.

    Args:
        roles: The finalized roles, in script order.
        tokens_dir: The directory containing the token images.
        output_dir: The directory to write the PDFs to.
        layout: The page layout.
        duplicates: The number of copies of each role token, keyed by normalized id.

    Returns:
        The number of role tokens and reminder tokens placed.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for basename in ("roles", "reminders"):  # A run that writes no pages of a kind must not leave an old sheet behind
        (output_dir / f"{basename}.pdf").unlink(missing_ok=True)
    common = {
        "page_width": layout.page_width,
        "page_height": layout.page_height,
        "margin_horizontal": layout.margin_horizontal,
        "margin_vertical": layout.margin_vertical,
        "padding": layout.padding,
        "dpi": layout.dpi,
    }
    role_sheet = Printable(output_dir, basename="roles", diameter=layout.role_diameter,
                           close_packing=_close_packing(layout, "role", layout.role_diameter), **common)
    reminder_sheet = Printable(output_dir, basename="reminders", diameter=layout.reminder_diameter,
                               close_packing=_close_packing(layout, "reminder", layout.reminder_diameter), **common)
    role_count = 0
    reminder_count = 0
    reminders_placed: set[str] = set()
    try:
        for role in roles:
            role_file = tokens_dir / f"{role.slug}.png"
            if role_file.exists():
                for _ in range(duplicates.get(role.normalized_id, 1)):
                    role_sheet.add_token(role_file)
                    role_count += 1
            else:
                print(f"[yellow]Warning:[/] No token found for {escape(role.id)}; skipping.")
            if role.slug in reminders_placed:  # Reminder tokens are placed once per role, however often it is listed
                continue
            reminders_placed.add(role.slug)
            for number in range(1, len(role.reminders) + 1):
                reminder_file = tokens_dir / f"{role.slug}-reminder-{number}.png"
                if reminder_file.exists():
                    reminder_sheet.add_token(reminder_file)
                    reminder_count += 1
        role_sheet.write()
        reminder_sheet.write()
    finally:
        role_sheet.close()
        reminder_sheet.close()
    return role_count, reminder_count
