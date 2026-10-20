"""Helper functions and constants for converting physical units to pixels."""

DEFAULT_DPI: int = 300

PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "letter": (215.9, 279.4),
    "legal": (215.9, 355.6),
    "a4": (210.0, 297.0),
    "a5": (148.0, 210.0),
}

MM_PER_INCH = 25.4


def mm_to_px(mm: float, dpi: int) -> int:
    """Convert a length in millimeters to a whole number of pixels at the given DPI."""
    return round(mm / MM_PER_INCH * dpi)
