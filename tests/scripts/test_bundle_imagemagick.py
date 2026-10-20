"""Test the script that copies a conda-forge ImageMagick into the binary's bundle directory."""
# Standard Library
import json

# Third Party
from bundle_imagemagick import (
    add_wand_shims,
    bundle,
    collect_licenses,
    conda_layout,
    copy_dlls,
    copy_libraries,
    main,
    prune_ghostscript,
)
import pytest


def _touch(path, content="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _write_meta(prefix, name, version, source, license_name=None):
    record = {"name": name, "version": version, "link": {"source": str(source)}}
    if license_name:
        record["license"] = license_name
    _touch(prefix / "conda-meta" / f"{name}-{version}-h1.json", json.dumps(record))


def make_posix_prefix(root):
    """Build a fake POSIX conda prefix with the files the bundler cares about."""
    prefix = root / "prefix"
    lib = prefix / "lib"
    _touch(lib / "libMagickWand-7.Q16HDRI.10.dylib")
    (lib / "libMagickWand-7.Q16HDRI.dylib").symlink_to("libMagickWand-7.Q16HDRI.10.dylib")
    _touch(lib / "libpng16.so.16")
    _touch(lib / "libgs.10.dylib")
    _touch(lib / "libfoo.a")
    _touch(lib / "libfoo.la")
    _touch(lib / "pkgconfig" / "x.pc")
    _touch(lib / "ImageMagick-7.1.1" / "config-Q16HDRI" / "configure.xml")
    _touch(prefix / "bin" / "gs")
    _touch(prefix / "etc" / "ImageMagick-7" / "policy.xml")
    _touch(prefix / "share" / "ImageMagick-7" / "english.xml")
    _touch(prefix / "share" / "ghostscript" / "Resource" / "Init" / "gs_init.ps")
    _touch(prefix / "etc" / "fonts" / "fonts.conf")
    pkgs = root / "pkgs"
    _touch(pkgs / "imagemagick-7.1.1-h1" / "info" / "licenses" / "LICENSE", "ImageMagick license")
    _write_meta(prefix, "imagemagick", "7.1.1", pkgs / "imagemagick-7.1.1-h1", "ImageMagick")
    _write_meta(prefix, "zlib", "1.3", pkgs / "zlib-1.3-h2")
    return prefix


def make_windows_prefix(root):
    """Build a fake Windows conda prefix, where everything lives under Library."""
    prefix = root / "prefix"
    library = prefix / "Library"
    _touch(library / "bin" / "MagickWand-7.Q16HDRI-10.dll")
    _touch(library / "bin" / "MagickCore-7.Q16HDRI-10.dll")
    _touch(library / "bin" / "gsdll64.dll")
    _touch(library / "bin" / "gswin64c.exe")
    _touch(library / "bin" / "convert.exe")
    _touch(library / "lib" / "MagickWand.lib")
    _touch(library / "etc" / "ImageMagick-7" / "policy.xml")
    pkgs = root / "pkgs"
    _touch(pkgs / "imagemagick-7.1.1-h1" / "info" / "licenses" / "LICENSE", "ImageMagick license")
    _write_meta(prefix, "imagemagick", "7.1.1", pkgs / "imagemagick-7.1.1-h1", "ImageMagick")
    return prefix


def test_conda_layout_posix_uses_prefix(tmp_path):
    """POSIX envs keep lib, bin, etc, and share directly under the prefix."""
    layout = conda_layout(tmp_path, "Linux")
    assert (layout.lib, layout.bin, layout.etc, layout.share) == (
        tmp_path / "lib", tmp_path / "bin", tmp_path / "etc", tmp_path / "share",
    )


def test_conda_layout_windows_uses_library(tmp_path):
    """Windows envs put everything under Library."""
    layout = conda_layout(tmp_path, "Windows")
    assert layout.bin == tmp_path / "Library" / "bin"
    assert layout.etc == tmp_path / "Library" / "etc"


def test_copy_libraries_keeps_symlinks_and_skips_static(tmp_path):
    """Copy shared libraries and the ImageMagick tree, keep symlinks, and skip build leftovers."""
    prefix = make_posix_prefix(tmp_path)
    dest = tmp_path / "dest" / "lib"
    copied = copy_libraries(prefix / "lib", dest)
    assert (dest / "libMagickWand-7.Q16HDRI.dylib").is_symlink()
    assert (dest / "libMagickWand-7.Q16HDRI.10.dylib").is_file()
    assert (dest / "libpng16.so.16").is_file()
    assert (dest / "ImageMagick-7.1.1" / "config-Q16HDRI" / "configure.xml").is_file()
    assert not (dest / "libfoo.a").exists()
    assert not (dest / "libfoo.la").exists()
    assert not (dest / "pkgconfig").exists()
    assert dest / "libMagickWand-7.Q16HDRI.dylib" in copied


def test_copy_dlls_only_copies_dlls(tmp_path):
    """Only DLLs come across from a Windows bin directory."""
    prefix = make_windows_prefix(tmp_path)
    dest = tmp_path / "dest" / "bin"
    copied = copy_dlls(prefix / "Library" / "bin", dest)
    assert (dest / "MagickWand-7.Q16HDRI-10.dll").is_file()
    assert not (dest / "convert.exe").exists()
    assert len(copied) == 3


def test_add_wand_shims_creates_core_rl_names(tmp_path):
    """Create the DLL names wand looks for on Windows."""
    prefix = make_windows_prefix(tmp_path)
    shims = add_wand_shims(prefix / "Library" / "bin")
    assert (prefix / "Library" / "bin" / "CORE_RL_MagickWand_.dll").is_file()
    assert (prefix / "Library" / "bin" / "CORE_RL_MagickCore_.dll").is_file()
    assert len(shims) == 2


def test_add_wand_shims_missing_raises(tmp_path):
    """Fail loudly when the conda DLLs are not where expected."""
    with pytest.raises(FileNotFoundError, match="MagickWand"):
        add_wand_shims(tmp_path)


def test_prune_ghostscript_posix(tmp_path):
    """Remove Ghostscript libraries, binaries, and resources from a POSIX bundle."""
    prefix = make_posix_prefix(tmp_path)
    removed = prune_ghostscript(prefix)
    assert not (prefix / "lib" / "libgs.10.dylib").exists()
    assert not (prefix / "bin" / "gs").exists()
    assert not (prefix / "share" / "ghostscript").exists()
    assert (prefix / "lib" / "libMagickWand-7.Q16HDRI.10.dylib").exists()
    assert len(removed) == 3


def test_prune_ghostscript_windows(tmp_path):
    """Remove Ghostscript DLLs and executables from a Windows bundle."""
    prefix = make_windows_prefix(tmp_path)
    prune_ghostscript(prefix)
    assert not (prefix / "Library" / "bin" / "gsdll64.dll").exists()
    assert not (prefix / "Library" / "bin" / "gswin64c.exe").exists()
    assert (prefix / "Library" / "bin" / "MagickWand-7.Q16HDRI-10.dll").exists()


def test_prune_ghostscript_nothing_to_do(tmp_path):
    """A bundle without Ghostscript is left alone."""
    assert prune_ghostscript(tmp_path) == []


def test_collect_licenses_copies_texts_and_lists_packages(tmp_path):
    """Copy each package's license texts and list every package, even ones without texts."""
    prefix = make_posix_prefix(tmp_path)
    dest = tmp_path / "licenses"
    lines = collect_licenses(prefix, dest)
    assert (dest / "imagemagick-7.1.1" / "LICENSE").read_text() == "ImageMagick license"
    assert not (dest / "zlib-1.3").exists()
    assert lines == ["imagemagick 7.1.1 ImageMagick", "zlib 1.3 unknown"]
    assert (dest / "PACKAGES.txt").read_text().splitlines() == lines


def test_collect_licenses_accepts_extracted_package_dir(tmp_path):
    """Support conda's record shape, which names the package directory differently."""
    prefix = tmp_path / "prefix"
    pkg = tmp_path / "pkgs" / "libpng-1.6-h3"
    _touch(pkg / "info" / "licenses" / "LICENSE", "png license")
    record = {"name": "libpng", "version": "1.6", "extracted_package_dir": str(pkg), "license": "zlib"}
    _touch(prefix / "conda-meta" / "libpng-1.6-h3.json", json.dumps(record))
    lines = collect_licenses(prefix, tmp_path / "licenses")
    assert lines == ["libpng 1.6 zlib"]
    assert (tmp_path / "licenses" / "libpng-1.6" / "LICENSE").is_file()


def test_bundle_posix_end_to_end(tmp_path):
    """Produce the full POSIX bundle layout the runtime bootstrap expects."""
    prefix = make_posix_prefix(tmp_path)
    dist = tmp_path / "dist"
    result = bundle(prefix, dist, "Linux")
    assert result == dist / "imagemagick"
    assert (result / "lib" / "libMagickWand-7.Q16HDRI.dylib").is_symlink()
    assert (result / "etc" / "ImageMagick-7" / "policy.xml").is_file()
    assert (result / "share" / "ImageMagick-7" / "english.xml").is_file()
    assert (result / "etc" / "fonts" / "fonts.conf").is_file()
    assert not list(result.rglob("libgs*"))
    assert not (result / "share" / "ghostscript").exists()
    assert (dist / "THIRD_PARTY_LICENSES" / "PACKAGES.txt").is_file()


def test_bundle_windows_end_to_end(tmp_path):
    """Produce the Windows bundle layout with DLLs, shims, and config, minus Ghostscript."""
    prefix = make_windows_prefix(tmp_path)
    dist = tmp_path / "dist"
    result = bundle(prefix, dist, "Windows")
    assert (result / "bin" / "CORE_RL_MagickWand_.dll").is_file()
    assert (result / "bin" / "MagickCore-7.Q16HDRI-10.dll").is_file()
    assert (result / "etc" / "ImageMagick-7" / "policy.xml").is_file()
    assert not (result / "bin" / "gsdll64.dll").exists()
    assert not (result / "lib").exists()


def test_main_runs(tmp_path, capsys):
    """The command line entry point bundles and reports what it did."""
    prefix = make_posix_prefix(tmp_path)
    dist = tmp_path / "dist"
    assert main(["--prefix", str(prefix), "--dist", str(dist), "--system", "Linux"]) == 0
    assert (dist / "imagemagick" / "lib" / "libpng16.so.16").is_file()
    assert "imagemagick" in capsys.readouterr().out
