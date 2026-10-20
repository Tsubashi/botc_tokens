"""Compile botc_tokens into a standalone binary with Nuitka, bundle ImageMagick beside it, and archive the result.

Usage (from the repository root, with the package and the ``build`` extra installed)::

    python scripts/build_binary.py --conda-prefix /path/to/env/with/imagemagick --output-dir build/nuitka

Without ``--conda-prefix`` the binary still builds but needs a system ImageMagick (via MAGICK_HOME) at runtime.
"""
# Standard Library
import argparse
from importlib.resources import files as package_files
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile

# Third Party
from bundle_imagemagick import bundle

# Application Specific
from botc_tokens.__version__ import version

LAUNCHER = Path(__file__).resolve().parent / "nuitka" / "launcher.py"
PROJECT_LICENSE = Path(__file__).resolve().parent.parent / "LICENSE"
BINARY_NAME = "botc_tokens"
DIST_NAME = f"{BINARY_NAME}.dist"
# Package data cannot live in a botc_tokens/ folder beside an executable of the same name, so it goes here instead and
# botc_tokens.helpers.bundled_imagemagick.find_data_dir picks it up at runtime.
PACKAGE_DATA = Path(str(package_files("botc_tokens") / "data"))
DATA_DIR_NAME = "botc_tokens_data"
COMPILED_DIST_NAME = f"{LAUNCHER.stem}.dist"
ARCHIVE_ROOT = "botc_tokens"
SYSTEM_TAGS = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}
MACHINE_TAGS = {"AMD64": "x86_64", "x86_64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}


def nuitka_command(python: str, output_dir: Path) -> list[str]:
    """Build the Nuitka command line for a standalone build into output_dir."""
    return [
        python, "-m", "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        f"--output-dir={output_dir}",
        "--include-package=botc_tokens",
        f"--include-data-dir={PACKAGE_DATA}={DATA_DIR_NAME}",
        f"--output-filename={BINARY_NAME}",
        str(LAUNCHER),
    ]


def platform_tag(system: str, machine: str) -> str:
    """Turn platform.system() and platform.machine() values into the archive tag, like macos-arm64."""
    if system not in SYSTEM_TAGS or machine not in MACHINE_TAGS:
        raise ValueError(f"Unsupported platform: {system} {machine}")
    return f"{SYSTEM_TAGS[system]}-{MACHINE_TAGS[machine]}"


def archive_name(version_string: str, system: str, machine: str) -> str:
    """Name the archive for a version and platform; zip on Windows, tar.gz elsewhere."""
    extension = "zip" if system == "Windows" else "tar.gz"
    return f"botc_tokens-{version_string}-{platform_tag(system, machine)}.{extension}"


def make_archive(dist: Path, archive: Path) -> Path:
    """Archive the dist directory under a top-level botc_tokens/ folder, keeping symlinks and permissions."""
    if archive.name.endswith(".tar.gz"):
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(dist, arcname=ARCHIVE_ROOT)
    else:
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for entry in sorted(dist.rglob("*")):
                zip_file.write(entry, f"{ARCHIVE_ROOT}/{entry.relative_to(dist)}")
    return archive


def main(argv: list[str] | None = None) -> int:
    """Run the build from the command line."""
    parser = argparse.ArgumentParser(description="Build a standalone botc_tokens binary.")
    parser.add_argument("--output-dir", type=Path, default=Path("build") / "nuitka", help="Where Nuitka builds.")
    parser.add_argument("--conda-prefix", type=Path, default=None, help="A conda env containing ImageMagick to bundle.")
    parser.add_argument("--skip-compile", action="store_true", help="Reuse an existing dist instead of running Nuitka.")
    parser.add_argument("--system", default=platform.system(), help="platform.system() value to build for.")
    parser.add_argument("--machine", default=platform.machine(), help="platform.machine() value to build for.")
    args = parser.parse_args(argv)

    dist = args.output_dir / DIST_NAME
    if not args.skip_compile:
        subprocess.run(nuitka_command(sys.executable, args.output_dir), check=True)
        # Nuitka names the dist folder after the launcher script, so rename it after the binary instead.
        shutil.rmtree(dist, ignore_errors=True)
        (args.output_dir / COMPILED_DIST_NAME).rename(dist)

    if args.conda_prefix is None:
        print("Warning: no --conda-prefix given, so no ImageMagick was bundled; the binary needs MAGICK_HOME.")
    else:
        bundle(args.conda_prefix, dist, args.system)

    if PROJECT_LICENSE.is_file():
        shutil.copy2(PROJECT_LICENSE, dist / "LICENSE")
    else:
        print(f"Warning: {PROJECT_LICENSE} not found, so no LICENSE was added to the archive.")

    archive = make_archive(dist, args.output_dir / archive_name(version, args.system, args.machine))
    print(f"Wrote {archive}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
