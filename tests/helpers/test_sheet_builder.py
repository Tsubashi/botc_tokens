"""Tests for the sheet builder."""
# Standard Library
import os
from shutil import copy

# Third Party
from pypdf import PdfReader
import pytest
from wand.image import Image

# Application Specific
from botc_tokens.helpers import sheet_builder
from botc_tokens.helpers.printable import Printable
from botc_tokens.helpers.role import Role
from botc_tokens.helpers.sheet_builder import build_sheets, LayoutError, SheetLayout


def _layout(**overrides):
    values = {
        "page_width": 512, "page_height": 512, "margin_horizontal": 0, "margin_vertical": 0, "padding": 0,
        "role_diameter": 64, "reminder_diameter": 32, "dpi": 300, "close_packing": True,
    }
    values.update(overrides)
    return SheetLayout(**values)


def _role(role_id, reminders=0):
    return Role(id=role_id, reminders=[f"R{n}" for n in range(reminders)])


@pytest.fixture()
def tokens_dir(tmp_path, test_data_dir):
    """Create token files for roles a, b (2 reminders), and legion."""
    folder = tmp_path / "tokens"
    folder.mkdir()
    icon = test_data_dir / "icons" / "1.png"
    for name in ("a", "b", "legion", "b-reminder-1", "b-reminder-2"):
        copy(icon, folder / f"{name}.png")
    return folder


def test_build_sheets_counts_and_files(tmp_path, tokens_dir):
    """Duplicates and reminders are counted and both PDFs are written."""
    roles = [_role("a"), _role("b", 2), _role("legion")]
    output = tmp_path / "out"
    counts = build_sheets(roles, tokens_dir, output, _layout(), {"legion": 3})
    assert counts == (5, 2)
    assert len(PdfReader(output / "roles.pdf").pages) == 1
    assert len(PdfReader(output / "reminders.pdf").pages) == 1


def test_build_sheets_missing_token_warns(tmp_path, tokens_dir, capsys):
    """A role without a token file is skipped with a warning."""
    counts = build_sheets([_role("a"), _role("ghost")], tokens_dir, tmp_path / "out", _layout(), {})
    assert counts == (1, 0)
    assert "Warning:" in capsys.readouterr().out


def test_build_sheets_no_reminders_no_pdf(tmp_path, tokens_dir):
    """No reminder files means no reminders.pdf."""
    output = tmp_path / "out"
    assert build_sheets([_role("a")], tokens_dir, output, _layout(), {}) == (1, 0)
    assert (output / "roles.pdf").exists()
    assert not (output / "reminders.pdf").exists()


def test_build_sheets_reminders_once_per_role(tmp_path, tokens_dir):
    """A role listed twice gets a role token per listing but its reminders only once."""
    assert build_sheets([_role("b", 2), _role("b", 2)], tokens_dir, tmp_path / "out", _layout(), {}) == (2, 2)


def test_build_sheets_removes_stale_pdfs(tmp_path, tokens_dir):
    """A sheet from an earlier run is removed when this run writes no pages of that kind."""
    output = tmp_path / "out"
    output.mkdir()
    (output / "reminders.pdf").write_text("stale")
    assert build_sheets([_role("a")], tokens_dir, output, _layout(), {}) == (1, 0)
    assert (output / "roles.pdf").exists()
    assert not (output / "reminders.pdf").exists()


def test_build_sheets_markup_in_id_is_escaped(tmp_path, tokens_dir, capsys):
    """Rich markup in a role id is printed literally in the missing-token warning instead of raising."""
    assert build_sheets([_role("[/x]")], tokens_dir, tmp_path / "out", _layout(), {}) == (0, 0)
    assert "No token found for [/x]" in capsys.readouterr().out.replace("\n", "")


def test_build_sheets_narrow_page_uses_grid(tmp_path, tokens_dir, monkeypatch, capsys):
    """A page too narrow for inset close-packed rows falls back to a grid for that sheet only."""
    packing = {}

    class SpyPrintable(Printable):
        """Record the packing each sheet is created with."""

        def __init__(self, output_dir, **kwargs):
            """Record the packing, then create the sheet."""
            packing[kwargs["basename"]] = kwargs["close_packing"]
            super().__init__(output_dir, **kwargs)

    monkeypatch.setattr(sheet_builder, "Printable", SpyPrintable)
    layout = _layout(page_width=90)  # Inset role rows need 1.5 * 64 = 96px; reminder rows need 48px
    assert build_sheets([_role("a"), _role("legion")], tokens_dir, tmp_path / "out", layout, {}) == (2, 0)
    assert packing == {"roles": False, "reminders": True}
    assert "too narrow to close pack role tokens" in capsys.readouterr().out.replace("\n", "")

    packing.clear()
    build_sheets([_role("a")], tokens_dir, tmp_path / "grid", _layout(page_width=90, close_packing=False), {})
    assert packing == {"roles": False, "reminders": False}


def test_layout_close_packing_fits():
    """Close packing fits when the printable width holds an inset row plus padding."""
    assert _layout(page_width=96).close_packing_fits(64)
    assert not _layout(page_width=95).close_packing_fits(64)
    assert not _layout(page_width=100, padding=5).close_packing_fits(64)
    assert _layout(page_width=120, margin_horizontal=12).close_packing_fits(64)
    assert not _layout(page_width=119, margin_horizontal=12).close_packing_fits(64)


def test_build_sheets_missing_reminder_skipped(tmp_path, tokens_dir):
    """Reminder files that do not exist are skipped."""
    assert build_sheets([_role("a", 2)], tokens_dir, tmp_path / "out", _layout(), {}) == (1, 0)


def test_layout_validate():
    """Impossible layouts raise LayoutError; valid ones do not."""
    _layout().validate()
    with pytest.raises(LayoutError):
        _layout(margin_horizontal=256).validate()
    with pytest.raises(LayoutError):
        _layout(margin_vertical=256).validate()
    with pytest.raises(LayoutError):
        _layout(role_diameter=513).validate()
    with pytest.raises(LayoutError):
        _layout(page_height=100, reminder_diameter=101).validate()


@pytest.mark.skipif(os.getenv("GITHUB_ACTIONS") == "true", reason="Required delegate is not installed in GH Actions.")
def test_page_pixel_size(tmp_path, tokens_dir):
    """The rendered page matches the layout's pixel size."""
    output = tmp_path / "out"
    build_sheets([_role("a")], tokens_dir, output, _layout(page_width=256, page_height=512), {})
    with Image(filename=output / "roles.pdf", resolution=(300, 300)) as img:
        assert img.size == (256, 512)
