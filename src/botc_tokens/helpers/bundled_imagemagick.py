"""Point wand, ImageMagick, TLS, and the package data at the copies bundled beside a standalone binary.

The standalone builds ship an ``imagemagick`` directory and a ``botc_tokens_data`` directory next to the executable.
When the ImageMagick directory exists, the environment variables below must be set before ``wand`` is imported, which
is why ``botc_tokens/__init__.py`` calls :func:`activate` first thing. For ordinary pip installs neither directory
exists and nothing happens.
"""
# Standard Library
import builtins
import os
from pathlib import Path
import platform
import sys
from typing import MutableMapping

# Third Party
import certifi

BUNDLE_DIR_NAME = "imagemagick"
DATA_DIR_NAME = "botc_tokens_data"


def installation_dir(compiled: object | None = None, argv0: str | None = None) -> Path:
    """Return the directory the program runs from.

    Under Nuitka, ``__compiled__.containing_dir`` names the dist folder, whatever path the user launched through.
    ``sys.executable`` is useless there: Nuitka points it at a ``python`` that does not exist beside argv[0], so a
    symlink on PATH would make it resolve to the wrong directory. Without Nuitka, follow argv[0] through symlinks.

    Args:
        compiled: Nuitka's ``__compiled__`` object; defaults to the one in this module's namespace, if any.
        argv0: The program path as invoked; defaults to ``sys.argv[0]``.
    """
    if compiled is None:
        compiled = globals().get("__compiled__", getattr(builtins, "__compiled__", None))
    containing_dir = getattr(compiled, "containing_dir", None)
    if containing_dir:
        return Path(containing_dir)
    return Path(os.path.realpath(sys.argv[0] if argv0 is None else argv0)).parent


def _beside(install_dir: Path, name: str) -> Path | None:
    candidate = install_dir / name
    return candidate if candidate.is_dir() else None


def find_bundle(install_dir: Path) -> Path | None:
    """Return the ImageMagick bundle directory inside the installation directory, or None if there is none."""
    return _beside(install_dir, BUNDLE_DIR_NAME)


def find_data_dir(install_dir: Path) -> Path | None:
    """Return the package data directory inside the installation directory, or None if there is none."""
    return _beside(install_dir, DATA_DIR_NAME)


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
    install_dir: Path | None = None,
    environ: MutableMapping[str, str] | None = None,
    system: str | None = None,
) -> dict[str, str]:
    """Apply the bundle environment for the bundle in the installation directory, without overriding existing settings.

    Args:
        install_dir: Where the program runs from; defaults to :func:`installation_dir`.
        environ: The environment to update; defaults to ``os.environ``.
        system: A ``platform.system()`` value; defaults to the current platform.

    Returns:
        The variables that were applied. Empty when there is no bundle.
    """
    install_dir = installation_dir() if install_dir is None else install_dir
    environ = os.environ if environ is None else environ
    system = platform.system() if system is None else system

    bundle = find_bundle(install_dir)
    if bundle is None:
        return {}

    wanted = bundle_environment(bundle, system)
    if "MAGICK_HOME" in environ:
        wanted = {key: value for key, value in wanted.items() if not key.startswith("MAGICK_")}
    applied = {key: value for key, value in wanted.items() if key not in environ}
    environ.update(applied)

    if system == "Windows" and "MAGICK_HOME" in applied:
        # wand consults the ImageMagick registry key before MAGICK_HOME, and only falls back to searching PATH, so the
        # bundle must be first on PATH to win over a stale or foreign registry entry.
        bin_dir = str(bundle / "bin")
        applied["PATH"] = environ["PATH"] = ";".join(filter(None, (bin_dir, environ.get("PATH"))))
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is not None:
            add_dll_directory(bin_dir)
    return applied
