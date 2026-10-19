"""Helpers for padding and acquiring role icons."""
# Standard Library
import math
from pathlib import Path

# Third Party
from rich import print
from rich.markup import escape
from wand.color import Color
from wand.exceptions import WandException
from wand.image import Image

# Application Specific
from .role import Role
from .web import decode_data_uri, fetch, FetchError, is_data_uri, is_url

PADDED_COVERAGE_LIMIT = 0.75
PAD_TARGET_COVERAGE = 0.70


def _trim(image: Image) -> Image | None:
    """Return a trimmed clone of the image, or None if the image is fully transparent."""
    trimmed = image.clone()
    trimmed.trim(color=Color("rgba(0,0,0,0)"), fuzz=0)
    if trimmed.page[2] < 0 or trimmed.page[3] < 0:
        # Fully transparent images trim to 1x1 with negative offsets
        trimmed.close()
        return None
    return trimmed


def is_blank(image: Image) -> bool:
    """Return whether the image is fully transparent."""
    trimmed = _trim(image)
    if trimmed is None:
        return True
    trimmed.close()
    return False


def pad_icon(image: Image) -> Image | None:
    """Return a padded copy of a tightly cropped icon, or None if the icon should be used as-is."""
    trimmed = _trim(image)
    if trimmed is None:
        return None
    content = max(trimmed.width, trimmed.height)
    if image.width == image.height and content <= PADDED_COVERAGE_LIMIT * image.width:
        trimmed.close()
        return None
    side = math.ceil(content / PAD_TARGET_COVERAGE)
    trimmed.reset_coords()
    padded = Image(width=side, height=side, background=Color("transparent"))
    padded.composite(trimmed, left=(side - trimmed.width) // 2, top=(side - trimmed.height) // 2)
    padded.format = image.format
    trimmed.close()
    return padded


def load_icon_bytes(icon: str) -> bytes:
    """Load the bytes of an icon from a URL, data URI, or local path."""
    if is_url(icon):
        return fetch(icon)
    if is_data_uri(icon):
        return decode_data_uri(icon)
    return Path(icon).read_bytes()


def acquire_icon(role: Role, icons_dir: Path, incremental: bool) -> Path | None:
    """Acquire, pad, and store a role's icon as a PNG, returning its path or None.

    Icons that cannot be loaded or are fully transparent are warned about and give None; nothing is cached for them.
    """
    if role.icon is None:
        return None
    target = icons_dir / f"{role.slug}.png"
    if incremental and target.exists():
        return target
    name = escape(role.name or role.id)
    try:
        with Image(blob=load_icon_bytes(role.icon)) as image:
            if is_blank(image):
                print(f"[yellow]Warning:[/] The {name} icon is fully transparent; ignoring it.")
                return None
            padded = pad_icon(image)
            result = padded or image
            result.format = "png"
            result.save(filename=str(target))
            if padded is not None:
                padded.close()
    except (FetchError, ValueError, OSError, WandException) as e:
        print(f"[yellow]Warning:[/] Could not load icon for {name}: {escape(str(e))}")
        return None
    return target
