"""Point wand, ImageMagick, TLS, and the package data at the copies bundled beside a standalone binary.

The standalone builds ship an ``imagemagick`` directory and a ``botc_tokens_data`` directory next to the executable.
When the ImageMagick directory exists, the environment variables below must be set before ``wand`` is imported, which
is why ``botc_tokens/__init__.py`` calls :func:`activate` first thing. For ordinary pip installs neither directory
exists and nothing happens.
"""
# Standard Library
import os
from pathlib import Path
import platform
import sys
from typing import MutableMapping

# Third Party
import certifi

BUNDLE_DIR_NAME = "imagemagick"
DATA_DIR_NAME = "botc_tokens_data"


def _beside_executable(executable: str, name: str) -> Path | None:
    candidate = Path(executable).resolve().parent / name
    return candidate if candidate.is_dir() else None


def find_bundle(executable: str) -> Path | None:
    """Return the ImageMagick bundle directory beside the given executable, or None if there is none."""
    return _beside_executable(executable, BUNDLE_DIR_NAME)


def find_data_dir(executable: str) -> Path | None:
    """Return the package data directory beside the given executable, or None if there is none."""
    return _beside_executable(executable, DATA_DIR_NAME)


def _first_module_dir(bundle: Path, kind: str) -> Path | None:
    """Find the first ImageMagick module directory of the given kind (coders or filters)."""
    return next(iter(sorted(bundle.glob(f"lib/ImageMagick-7*/modules-*/{kind}"))), None)


def bundle_environment(bundle: Path, system: str) -> dict[str, str]:
    """Compute the environment variables that make wand and ImageMagick use the bundle.

    Args:
        bundle: The bundle directory.
        system: A ``platform.system()`` value: "Windows", "Darwin", or "Linux".

    Returns:
        The variables to set, only ever pointing at directories that exist.
    """
    windows = system == "Windows"
    env = {"MAGICK_HOME": str(bundle / "bin" if windows else bundle)}

    configure_dirs = [bundle / "etc" / "ImageMagick-7", bundle / "share" / "ImageMagick-7"]
    configure_dirs = [path for path in configure_dirs if path.is_dir()]
    if configure_dirs:
        env["MAGICK_CONFIGURE_PATH"] = (";" if windows else ":").join(str(path) for path in configure_dirs)

    for kind, variable in (("coders", "MAGICK_CODER_MODULE_PATH"), ("filters", "MAGICK_FILTER_MODULE_PATH")):
        module_dir = _first_module_dir(bundle, kind)
        if module_dir is not None:
            env[variable] = str(module_dir)

    fonts = bundle / "etc" / "fonts"
    if fonts.is_dir():
        env["FONTCONFIG_PATH"] = str(fonts)

    env["SSL_CERT_FILE"] = certifi.where()
    return env


def activate(
    executable: str | None = None,
    environ: MutableMapping[str, str] | None = None,
    system: str | None = None,
) -> dict[str, str]:
    """Apply the bundle environment for the bundle beside the executable, without overriding existing settings.

    Args:
        executable: The running executable; defaults to ``sys.executable``.
        environ: The environment to update; defaults to ``os.environ``.
        system: A ``platform.system()`` value; defaults to the current platform.

    Returns:
        The variables that were applied. Empty when there is no bundle.
    """
    executable = sys.executable if executable is None else executable
    environ = os.environ if environ is None else environ
    system = platform.system() if system is None else system

    bundle = find_bundle(executable)
    if bundle is None:
        return {}

    wanted = bundle_environment(bundle, system)
    if "MAGICK_HOME" in environ:
        wanted = {key: value for key, value in wanted.items() if not key.startswith("MAGICK_")}
    applied = {key: value for key, value in wanted.items() if key not in environ}
    environ.update(applied)

    if system == "Windows":
        # wand consults the ImageMagick registry key before MAGICK_HOME, and only falls back to searching PATH, so the
        # bundle must be first on PATH to win over a stale or foreign registry entry.
        bin_dir = str(bundle / "bin")
        applied["PATH"] = environ["PATH"] = ";".join(filter(None, (bin_dir, environ.get("PATH"))))
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is not None:
            add_dll_directory(bin_dir)
    return applied
