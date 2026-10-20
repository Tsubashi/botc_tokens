"""Tests for the unit conversion helpers."""
# Standard Library

# Third Party
import pytest

# Application Specific
from botc_tokens.helpers.units import mm_to_px, PAPER_SIZES_MM


@pytest.mark.parametrize(
    "mm, dpi, px",
    [(46.0, 300, 543), (26.0, 300, 307), (6.27, 300, 74), (215.9, 300, 2550), (279.4, 300, 3300), (25.4, 72, 72)],
)
def test_mm_to_px(mm, dpi, px):
    """Convert millimeters to pixels by rounding."""
    assert mm_to_px(mm, dpi) == px


def test_paper_sizes():
    """Offer the four named paper sizes in millimeters."""
    assert set(PAPER_SIZES_MM) == {"letter", "legal", "a4", "a5"}
    assert PAPER_SIZES_MM["a4"] == (210.0, 297.0)
