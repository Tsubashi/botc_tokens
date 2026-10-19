"""Tests for the icon helper."""
# Standard Library
import base64

# Third Party
from wand.color import Color
from wand.drawing import Drawing
from wand.image import Image

# Application Specific
from botc_tokens.helpers import icons
from botc_tokens.helpers.icons import acquire_icon, load_icon_bytes, pad_icon
from botc_tokens.helpers.role import Role
from botc_tokens.helpers.web import FetchError

ICON_URL = "https://example.com/icon.webp"


def make_image(width, height, content=None):
    """Make a transparent image, optionally with a centered opaque content rectangle (w, h)."""
    image = Image(width=width, height=height, background=Color("transparent"))
    if content:
        with Drawing() as drawing:
            drawing.fill_color = Color("red")
            left = (width - content[0]) // 2
            top = (height - content[1]) // 2
            drawing.rectangle(left=left, top=top, width=content[0] - 1, height=content[1] - 1)
            drawing(image)
    return image


def test_pad_icon_pads_tight_image(test_data_dir):
    """A tightly cropped icon is padded onto a square canvas at 70% coverage."""
    with Image(filename=str(test_data_dir / "icons" / "tight.webp")) as image:
        padded = pad_icon(image)
    assert padded is not None
    with padded:
        assert padded.width == padded.height == 58
        assert padded[29, 29].alpha == 1.0
        assert padded[0, 0].alpha == 0.0


def test_pad_icon_leaves_padded_image(test_data_dir):
    """An already padded icon is left alone."""
    with Image(filename=str(test_data_dir / "icons" / "padded.png")) as image:
        assert pad_icon(image) is None


def test_pad_icon_skips_fully_transparent():
    """A fully transparent icon is left alone."""
    with make_image(20, 20) as image:
        assert pad_icon(image) is None


def test_pad_icon_non_square_with_margin():
    """A non-square icon is padded to a square even when it has margins."""
    with make_image(100, 60, content=(30, 30)) as image:
        padded = pad_icon(image)
    assert padded is not None
    with padded:
        assert padded.width == padded.height == 43
        assert padded[21, 21].alpha == 1.0


def test_load_icon_bytes_sources(tmp_path, fake_web):
    """Icons load from URLs, data URIs, and local paths."""
    fake_web.routes[ICON_URL] = b"from-url"
    assert load_icon_bytes(ICON_URL) == b"from-url"
    uri = "data:image/png;base64," + base64.b64encode(b"from-uri").decode()
    assert load_icon_bytes(uri) == b"from-uri"
    path = tmp_path / "icon.bin"
    path.write_bytes(b"from-file")
    assert load_icon_bytes(str(path)) == b"from-file"


def test_acquire_icon_downloads_and_pads(tmp_path, fake_web, test_data_dir):
    """A downloaded tight icon is padded and stored as a square PNG."""
    fake_web.routes[ICON_URL] = (test_data_dir / "icons" / "tight.webp").read_bytes()
    target = acquire_icon(Role(id="Tight", icon=ICON_URL), tmp_path, incremental=False)
    assert target == tmp_path / "tight.png"
    with Image(filename=str(target)) as image:
        assert image.format == "PNG"
        assert image.width == image.height == 58


def test_acquire_icon_keeps_padded_icon(tmp_path, test_data_dir):
    """An already padded local icon is stored without resizing."""
    source = test_data_dir / "icons" / "padded.png"
    target = acquire_icon(Role(id="Padded", icon=str(source)), tmp_path, incremental=False)
    with Image(filename=str(target)) as image:
        assert image.width == image.height == 100


def test_acquire_icon_incremental_reuses(tmp_path, fake_web):
    """An existing icon is reused in incremental mode without fetching."""
    target = tmp_path / "reuse.png"
    target.write_bytes(b"existing")
    assert acquire_icon(Role(id="Reuse", icon=ICON_URL), tmp_path, incremental=True) == target
    assert fake_web.calls == []
    assert target.read_bytes() == b"existing"


def test_acquire_icon_no_icon(tmp_path):
    """A role without an icon yields None and writes nothing."""
    assert acquire_icon(Role(id="Bare"), tmp_path, incremental=False) is None
    assert list(tmp_path.iterdir()) == []


def test_acquire_icon_bad_bytes_warns(tmp_path, fake_web, capsys):
    """Bytes that are not an image produce a warning and None."""
    fake_web.routes[ICON_URL] = b"<html>"
    assert acquire_icon(Role(id="Bad", name="Bad", icon=ICON_URL), tmp_path, incremental=False) is None
    assert "Could not load icon for Bad" in capsys.readouterr().out


def test_acquire_icon_missing_file_warns(tmp_path, capsys):
    """A missing local file produces a warning, falling back to the id when unnamed."""
    role = Role(id="Gone", icon=str(tmp_path / "missing.png"))
    assert acquire_icon(role, tmp_path, incremental=False) is None
    assert "Could not load icon for Gone" in capsys.readouterr().out


def test_acquire_icon_fetch_error_warns(tmp_path, monkeypatch, capsys):
    """A failed fetch produces a warning and None."""
    def fail(url):
        raise FetchError("boom")

    monkeypatch.setattr(icons, "fetch", fail)
    assert acquire_icon(Role(id="Net", name="Net", icon=ICON_URL), tmp_path, incremental=False) is None
    assert "boom" in capsys.readouterr().out
