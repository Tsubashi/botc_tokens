"""Test the bootstrap that points wand at a bundled ImageMagick."""
# Standard Library
import os
import sys

# Third Party
import certifi

# Application Specific
from botc_tokens.helpers.bundled_imagemagick import (
    activate,
    bundle_environment,
    find_bundle,
    find_data_dir,
    installation_dir,
)


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
    assert find_bundle(tmp_path) == tmp_path / "imagemagick"


def test_find_bundle_absent(tmp_path):
    """Report no bundle when the directory is missing."""
    assert find_bundle(tmp_path) is None


def test_find_bundle_ignores_files_named_like_the_bundle(tmp_path):
    """Only a directory counts as a bundle."""
    (tmp_path / "imagemagick").write_text("not a directory")
    assert find_bundle(tmp_path) is None


class _Compiled:
    """Stand-in for Nuitka's __compiled__ object."""

    def __init__(self, containing_dir):
        self.containing_dir = containing_dir


def test_installation_dir_prefers_nuitka_containing_dir(tmp_path):
    """Nuitka tells us where the dist folder is; that beats every other guess."""
    assert installation_dir(compiled=_Compiled(str(tmp_path)), argv0="/elsewhere/botc_tokens") == tmp_path


def test_installation_dir_resolves_symlinked_argv0(tmp_path):
    """Without Nuitka's hint, follow the symlink users put on PATH back to the real executable's directory."""
    real = tmp_path / "real"
    real.mkdir()
    (real / "botc_tokens").write_text("")
    link_dir = tmp_path / "elsewhere"
    link_dir.mkdir()
    (link_dir / "botc_tokens").symlink_to(real / "botc_tokens")
    assert installation_dir(compiled=None, argv0=str(link_dir / "botc_tokens")) == real


def test_installation_dir_ignores_compiled_without_containing_dir(tmp_path):
    """An older Nuitka without containing_dir falls through to argv[0]."""
    (tmp_path / "botc_tokens").write_text("")
    assert installation_dir(compiled=object(), argv0=str(tmp_path / "botc_tokens")) == tmp_path


def test_installation_dir_defaults_do_not_find_a_bundle():
    """Under pytest the defaults resolve to the interpreter's directory, which holds no bundle."""
    assert find_bundle(installation_dir()) is None
    assert find_data_dir(installation_dir()) is None


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
    assert activate(tmp_path, environ, "Linux") == {}
    assert environ == {}


def test_activate_sets_variables(tmp_path):
    """Apply the bundle environment and report what was applied."""
    (tmp_path / "imagemagick").mkdir()
    environ = {}
    applied = activate(tmp_path, environ, "Linux")
    assert environ["MAGICK_HOME"] == str(tmp_path / "imagemagick")
    assert applied == environ


def test_activate_respects_existing_magick_home(tmp_path):
    """A user-provided MAGICK_HOME wins, and no bundle ImageMagick settings are layered on top."""
    (tmp_path / "imagemagick" / "etc" / "ImageMagick-7").mkdir(parents=True)
    environ = {"MAGICK_HOME": "/opt/homebrew/"}
    activate(tmp_path, environ, "Linux")
    assert environ["MAGICK_HOME"] == "/opt/homebrew/"
    assert "MAGICK_CONFIGURE_PATH" not in environ
    assert environ["SSL_CERT_FILE"] == certifi.where()


def test_activate_does_not_override_ssl_cert_file(tmp_path):
    """Keep a CA bundle the user chose themselves."""
    (tmp_path / "imagemagick").mkdir()
    environ = {"SSL_CERT_FILE": "/custom.pem"}
    activate(tmp_path, environ, "Linux")
    assert environ["SSL_CERT_FILE"] == "/custom.pem"


def test_activate_registers_dll_directory_on_windows(tmp_path, monkeypatch):
    """Register the DLL directory so dependent DLLs resolve on Windows."""
    (tmp_path / "imagemagick" / "bin").mkdir(parents=True)
    seen = []
    monkeypatch.setattr(os, "add_dll_directory", seen.append, raising=False)
    activate(tmp_path, {}, "Windows")
    assert seen == [str(tmp_path / "imagemagick" / "bin")]


def test_activate_skips_dll_registration_when_unsupported(tmp_path, monkeypatch):
    """Do not fail on a Windows layout when os.add_dll_directory is unavailable."""
    (tmp_path / "imagemagick" / "bin").mkdir(parents=True)
    monkeypatch.delattr(os, "add_dll_directory", raising=False)
    applied = activate(tmp_path, {}, "Windows")
    assert applied["MAGICK_HOME"] == str(tmp_path / "imagemagick" / "bin")


def test_activate_defaults_use_process_state(monkeypatch, tmp_path):
    """Default to the real installation directory, the real environment, and the real platform."""
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "botc_tokens")])
    assert activate() == {}


def test_find_data_dir_beside_executable(tmp_path):
    """Standalone binaries keep the package data in botc_tokens_data beside the executable."""
    (tmp_path / "botc_tokens_data").mkdir()
    assert find_data_dir(tmp_path) == tmp_path / "botc_tokens_data"


def test_find_data_dir_absent(tmp_path):
    """Pip installs have no such directory and fall back to package resources."""
    assert find_data_dir(tmp_path) is None


def test_package_data_dir_falls_back_to_package_resources():
    """Under pytest there is no bundled data directory, so data_dir is the package's own data folder."""
    import botc_tokens
    assert (botc_tokens.data_dir / "role_schema.json").is_file()
    assert (botc_tokens.component_path / "RoleName.ttf").is_file()


def test_activate_prepends_bundle_bin_to_path_on_windows(tmp_path):
    """Put the bundle first on PATH, since wand falls back to PATH when a registry key points elsewhere."""
    (tmp_path / "imagemagick" / "bin").mkdir(parents=True)
    environ = {"PATH": "C:\\Windows\\system32"}
    applied = activate(tmp_path, environ, "Windows")
    assert environ["PATH"] == f"{tmp_path / 'imagemagick' / 'bin'};C:\\Windows\\system32"
    assert applied["PATH"] == environ["PATH"]


def test_activate_sets_path_on_windows_when_missing(tmp_path):
    """A missing PATH is created rather than crashing."""
    (tmp_path / "imagemagick" / "bin").mkdir(parents=True)
    environ = {}
    activate(tmp_path, environ, "Windows")
    assert environ["PATH"] == str(tmp_path / "imagemagick" / "bin")


def test_activate_leaves_path_alone_elsewhere(tmp_path):
    """POSIX library lookup does not use PATH, so it is left untouched."""
    (tmp_path / "imagemagick").mkdir()
    environ = {"PATH": "/usr/bin"}
    activate(tmp_path, environ, "Linux")
    assert environ["PATH"] == "/usr/bin"


def test_activate_respects_existing_magick_home_on_windows(tmp_path, monkeypatch):
    """A user-set MAGICK_HOME on Windows must not get the bundle's bin directory on PATH or as a DLL directory."""
    (tmp_path / "imagemagick" / "bin").mkdir(parents=True)
    seen = []
    monkeypatch.setattr(os, "add_dll_directory", seen.append, raising=False)
    environ = {"MAGICK_HOME": "C:\\ImageMagick", "PATH": "C:\\Windows"}
    activate(tmp_path, environ, "Windows")
    assert environ["PATH"] == "C:\\Windows"
    assert seen == []
