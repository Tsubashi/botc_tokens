"""Test the bootstrap that points wand at a bundled ImageMagick."""
# Standard Library
import os
import sys

# Third Party
import certifi

# Application Specific
from botc_tokens.helpers.bundled_imagemagick import activate, bundle_environment, find_bundle


def _make_full_layout(bundle):
    """Create every optional directory the bootstrap knows about."""
    (bundle / "etc" / "ImageMagick-7").mkdir(parents=True)
    (bundle / "share" / "ImageMagick-7").mkdir(parents=True)
    modules = bundle / "lib" / "ImageMagick-7.1.1" / "modules-Q16HDRI"
    (modules / "coders").mkdir(parents=True)
    (modules / "filters").mkdir(parents=True)
    (bundle / "etc" / "fonts").mkdir(parents=True)
    return modules


def test_find_bundle_beside_executable(tmp_path):
    """Find the bundle directory that sits beside the executable."""
    (tmp_path / "imagemagick").mkdir()
    assert find_bundle(str(tmp_path / "botc_tokens")) == tmp_path / "imagemagick"


def test_find_bundle_absent(tmp_path):
    """Report no bundle when the directory is missing."""
    assert find_bundle(str(tmp_path / "botc_tokens")) is None


def test_find_bundle_ignores_files_named_like_the_bundle(tmp_path):
    """Only a directory counts as a bundle."""
    (tmp_path / "imagemagick").write_text("not a directory")
    assert find_bundle(str(tmp_path / "botc_tokens")) is None


def test_find_bundle_follows_symlinked_executable(tmp_path):
    """Resolve symlinks so a launcher on PATH still finds the real bundle."""
    real = tmp_path / "real"
    real.mkdir()
    (real / "imagemagick").mkdir()
    (real / "botc_tokens").write_text("")
    link_dir = tmp_path / "elsewhere"
    link_dir.mkdir()
    (link_dir / "botc_tokens").symlink_to(real / "botc_tokens")
    assert find_bundle(str(link_dir / "botc_tokens")) == real / "imagemagick"


def test_posix_environment_full_layout(tmp_path):
    """Set every variable when the bundle has every directory."""
    modules = _make_full_layout(tmp_path)
    env = bundle_environment(tmp_path, "Linux")
    assert env["MAGICK_HOME"] == str(tmp_path)
    expected_configure = f"{tmp_path / 'etc' / 'ImageMagick-7'}:{tmp_path / 'share' / 'ImageMagick-7'}"
    assert env["MAGICK_CONFIGURE_PATH"] == expected_configure
    assert env["MAGICK_CODER_MODULE_PATH"] == str(modules / "coders")
    assert env["MAGICK_FILTER_MODULE_PATH"] == str(modules / "filters")
    assert env["FONTCONFIG_PATH"] == str(tmp_path / "etc" / "fonts")
    assert env["SSL_CERT_FILE"] == certifi.where()


def test_windows_environment_uses_bin_and_semicolons(tmp_path):
    """Point MAGICK_HOME at the DLL directory and join paths with semicolons on Windows."""
    (tmp_path / "bin").mkdir()
    (tmp_path / "etc" / "ImageMagick-7").mkdir(parents=True)
    (tmp_path / "share" / "ImageMagick-7").mkdir(parents=True)
    env = bundle_environment(tmp_path, "Windows")
    assert env["MAGICK_HOME"] == str(tmp_path / "bin")
    expected_configure = f"{tmp_path / 'etc' / 'ImageMagick-7'};{tmp_path / 'share' / 'ImageMagick-7'}"
    assert env["MAGICK_CONFIGURE_PATH"] == expected_configure


def test_environment_omits_missing_directories(tmp_path):
    """Never point ImageMagick at directories that do not exist."""
    env = bundle_environment(tmp_path, "Darwin")
    assert set(env) == {"MAGICK_HOME", "SSL_CERT_FILE"}


def test_activate_without_bundle_is_noop(tmp_path):
    """Leave the environment alone for ordinary pip installs."""
    environ = {}
    assert activate(str(tmp_path / "botc_tokens"), environ, "Linux") == {}
    assert environ == {}


def test_activate_sets_variables(tmp_path):
    """Apply the bundle environment and report what was applied."""
    (tmp_path / "imagemagick").mkdir()
    environ = {}
    applied = activate(str(tmp_path / "botc_tokens"), environ, "Linux")
    assert environ["MAGICK_HOME"] == str(tmp_path / "imagemagick")
    assert applied == environ


def test_activate_respects_existing_magick_home(tmp_path):
    """A user-provided MAGICK_HOME wins, and no bundle ImageMagick settings are layered on top."""
    (tmp_path / "imagemagick" / "etc" / "ImageMagick-7").mkdir(parents=True)
    environ = {"MAGICK_HOME": "/opt/homebrew/"}
    activate(str(tmp_path / "botc_tokens"), environ, "Linux")
    assert environ["MAGICK_HOME"] == "/opt/homebrew/"
    assert "MAGICK_CONFIGURE_PATH" not in environ
    assert environ["SSL_CERT_FILE"] == certifi.where()


def test_activate_does_not_override_ssl_cert_file(tmp_path):
    """Keep a CA bundle the user chose themselves."""
    (tmp_path / "imagemagick").mkdir()
    environ = {"SSL_CERT_FILE": "/custom.pem"}
    activate(str(tmp_path / "botc_tokens"), environ, "Linux")
    assert environ["SSL_CERT_FILE"] == "/custom.pem"


def test_activate_registers_dll_directory_on_windows(tmp_path, monkeypatch):
    """Register the DLL directory so dependent DLLs resolve on Windows."""
    (tmp_path / "imagemagick" / "bin").mkdir(parents=True)
    seen = []
    monkeypatch.setattr(os, "add_dll_directory", seen.append, raising=False)
    activate(str(tmp_path / "botc_tokens"), {}, "Windows")
    assert seen == [str(tmp_path / "imagemagick" / "bin")]


def test_activate_skips_dll_registration_when_unsupported(tmp_path, monkeypatch):
    """Do not fail on a Windows layout when os.add_dll_directory is unavailable."""
    (tmp_path / "imagemagick" / "bin").mkdir(parents=True)
    monkeypatch.delattr(os, "add_dll_directory", raising=False)
    applied = activate(str(tmp_path / "botc_tokens"), {}, "Windows")
    assert applied["MAGICK_HOME"] == str(tmp_path / "imagemagick" / "bin")


def test_activate_defaults_use_process_state(monkeypatch, tmp_path):
    """Default to the running executable, the real environment, and the real platform."""
    monkeypatch.setattr(sys, "executable", str(tmp_path / "botc_tokens"))
    assert activate() == {}
