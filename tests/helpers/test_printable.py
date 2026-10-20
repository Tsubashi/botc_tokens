"""Tests for the printable sheet writer."""
# Third Party
from pypdf import PdfReader
import pytest

# Application Specific
from botc_tokens.helpers.printable import Printable


def _write(tmp_path, token, count, **kwargs):
    printable = Printable(tmp_path, **kwargs)
    for _ in range(count):
        printable.add_token(token)
    printable.write()
    printable.close()
    return PdfReader(tmp_path / f"{kwargs.get('basename', 'page')}.pdf")


def test_printable_dpi(tmp_path, test_data_dir):
    """The dpi determines the PDF page size in points."""
    reader = _write(tmp_path, test_data_dir / "icons" / "1.png", 1, page_width=300, page_height=150,
                    margin_horizontal=0, margin_vertical=0, dpi=150)
    assert float(reader.pages[0].mediabox.width) == pytest.approx(300 * 72 / 150, abs=0.5)


def test_printable_page_overflow(tmp_path, test_data_dir):
    """Tokens that do not fit on a page continue on a new page."""
    reader = _write(tmp_path, test_data_dir / "icons" / "1.png", 5, page_width=128, page_height=64,
                    margin_horizontal=0, margin_vertical=0, diameter=64)
    assert len(reader.pages) > 1


def test_printable_grid_layout(tmp_path, test_data_dir):
    """The grid layout places tokens in aligned rows."""
    reader = _write(tmp_path, test_data_dir / "icons" / "1.png", 5, page_width=128, page_height=128,
                    margin_horizontal=0, margin_vertical=0, diameter=64, close_packing=False)
    assert len(reader.pages) == 2


def test_printable_default_diameter(tmp_path, test_data_dir):
    """Without a diameter, the first token's largest dimension is used."""
    reader = _write(tmp_path, test_data_dir / "icons" / "1.png", 1, margin_horizontal=0, margin_vertical=0)
    assert len(reader.pages) == 1
