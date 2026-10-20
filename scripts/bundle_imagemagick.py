"""Copy a conda-forge ImageMagick environment into the bundle directory beside a standalone botc_tokens binary.

The layout produced here is what ``botc_tokens.helpers.bundled_imagemagick`` expects at runtime::

    <dist>/imagemagick/lib/        shared libraries (POSIX) plus the ImageMagick-7* tree if present
    <dist>/imagemagick/bin/        DLLs plus wand-compatible CORE_RL_* shims (Windows)
    <dist>/imagemagick/etc/ImageMagick-7/, share/ImageMagick-7/, etc/fonts/
    <dist>/THIRD_PARTY_LICENSES/   license texts of every conda package, and PACKAGES.txt

Ghostscript is removed because botc_tokens only writes PDFs and Ghostscript's AGPL license should not ride along.
"""
# Standard Library
import argparse
from dataclasses import dataclass
import fnmatch
import json
from pathlib import Path
import platform
import shutil
import sys

BUNDLE_DIR_NAME = "imagemagick"
LICENSES_DIR_NAME = "THIRD_PARTY_LICENSES"
LIBRARY_PATTERNS = ("*.so", "*.so.*", "*.dylib")
GHOSTSCRIPT_PATTERNS = ("libgs.*", "libgs-*", "gsdll*", "gs", "gs.exe", "gswin*")
CONFIG_SUBDIRS = (("etc", "ImageMagick-7"), ("share", "ImageMagick-7"), ("etc", "fonts"))


@dataclass
class CondaLayout:
    """Where a conda environment keeps its libraries, binaries, and configuration."""

    lib: Path
    bin: Path
    etc: Path
    share: Path


def conda_layout(prefix: Path, system: str) -> CondaLayout:
    """Describe the environment layout; Windows environments root everything under ``Library``."""
    root = prefix / "Library" if system == "Windows" else prefix
    return CondaLayout(lib=root / "lib", bin=root / "bin", etc=root / "etc", share=root / "share")


def _matches(name: str, patterns) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def _copy_entry(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        dest.symlink_to(source.readlink())
    elif source.is_dir():
        shutil.copytree(source, dest, symlinks=True)
    else:
        shutil.copy2(source, dest)


def copy_libraries(source_lib: Path, dest_lib: Path) -> list[Path]:
    """Copy shared libraries and the ImageMagick-7* tree, keeping symlinks and skipping build leftovers."""
    copied = []
    for entry in sorted(source_lib.iterdir()):
        wanted = (entry.is_dir() and fnmatch.fnmatch(entry.name, "ImageMagick-7*")) or (
            not entry.is_dir() and _matches(entry.name, LIBRARY_PATTERNS)
        )
        if wanted:
            _copy_entry(entry, dest_lib / entry.name)
            copied.append(dest_lib / entry.name)
    return copied


def copy_dlls(source_bin: Path, dest_bin: Path) -> list[Path]:
    """Copy only the DLLs from a Windows bin directory."""
    copied = []
    for entry in sorted(source_bin.glob("*.dll")):
        _copy_entry(entry, dest_bin / entry.name)
        copied.append(dest_bin / entry.name)
    return copied


def add_wand_shims(dest_bin: Path) -> list[Path]:
    """Copy the conda-forge DLLs to the CORE_RL_* names that wand searches for under MAGICK_HOME."""
    shims = []
    pairs = (("MagickWand-*.dll", "CORE_RL_MagickWand_.dll"), ("MagickCore-*.dll", "CORE_RL_MagickCore_.dll"))
    for pattern, shim_name in pairs:
        source = next(iter(sorted(dest_bin.glob(pattern))), None)
        if source is None:
            raise FileNotFoundError(f"No DLL matching {pattern} in {dest_bin}")
        shutil.copy2(source, dest_bin / shim_name)
        shims.append(dest_bin / shim_name)
    return shims


def prune_ghostscript(bundle_dir: Path) -> list[Path]:
    """Delete Ghostscript libraries, executables, and resources anywhere under the bundle."""
    removed = []
    for entry in sorted(bundle_dir.rglob("*"), reverse=True):
        is_resources = entry.name == "ghostscript" and entry.parent.name == "share"
        if is_resources or _matches(entry.name, GHOSTSCRIPT_PATTERNS):
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            removed.append(entry)
    return removed


def collect_licenses(prefix: Path, dest: Path) -> list[str]:
    """Copy each conda package's license texts into dest and write a PACKAGES.txt listing.

    Raises:
        FileNotFoundError: If a package's directory is gone (for example a cached env without ``pkgs``), since the
            archive would then silently ship without the license texts the project promises.
    """
    lines = []
    for record_path in sorted((prefix / "conda-meta").glob("*.json")):
        record = json.loads(record_path.read_text())
        name, version = record["name"], record["version"]
        lines.append(f"{name} {version} {record.get('license') or 'unknown'}")
        package_dir = record.get("link", {}).get("source") or record.get("extracted_package_dir")
        if not package_dir or not Path(package_dir).is_dir():
            # A restored environment cache has no package directories, and then no license texts could be shipped.
            raise FileNotFoundError(f"Package directory for {name} {version} is missing: {package_dir!r}")
        licenses = Path(package_dir) / "info" / "licenses"
        if licenses.is_dir():
            shutil.copytree(licenses, dest / f"{name}-{version}", dirs_exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "PACKAGES.txt").write_text("\n".join(lines) + "\n")
    return lines


def bundle(prefix: Path, dist: Path, system: str) -> Path:
    """Build the complete bundle inside dist and return the bundle directory."""
    layout = conda_layout(prefix, system)
    bundle_dir = dist / BUNDLE_DIR_NAME
    bundle_dir.mkdir(parents=True, exist_ok=True)

    if system == "Windows":
        copy_dlls(layout.bin, bundle_dir / "bin")
        add_wand_shims(bundle_dir / "bin")
    else:
        copy_libraries(layout.lib, bundle_dir / "lib")

    root = layout.lib.parent
    for parts in CONFIG_SUBDIRS:
        source = root.joinpath(*parts)
        if source.is_dir():
            shutil.copytree(source, bundle_dir.joinpath(*parts), symlinks=True, dirs_exist_ok=True)

    prune_ghostscript(bundle_dir)
    collect_licenses(prefix, dist / LICENSES_DIR_NAME)
    return bundle_dir


def main(argv: list[str] | None = None) -> int:
    """Run the bundler from the command line."""
    parser = argparse.ArgumentParser(description="Bundle a conda-forge ImageMagick beside a botc_tokens binary.")
    parser.add_argument("--prefix", required=True, type=Path, help="The conda environment prefix to copy from.")
    parser.add_argument("--dist", required=True, type=Path, help="The Nuitka dist directory to copy into.")
    parser.add_argument("--system", default=platform.system(), help="platform.system() value to lay out for.")
    args = parser.parse_args(argv)

    bundle_dir = bundle(args.prefix, args.dist, args.system)
    file_count = sum(1 for entry in bundle_dir.rglob("*") if not entry.is_dir())
    print(f"Bundled {file_count} files into {bundle_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
