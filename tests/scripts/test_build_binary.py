"""Test the script that compiles the binary with Nuitka and archives it."""
# Standard Library
from pathlib import Path
import subprocess
import tarfile
import zipfile

# Third Party
import build_binary
from build_binary import archive_name, LAUNCHER, main, make_archive, nuitka_command, PACKAGE_DATA, platform_tag
import pytest


def test_launcher_exists():
    """The Nuitka entry point must not be named botc_tokens.py, or it shadows the package on Nuitka's path."""
    assert LAUNCHER.name == "launcher.py"
    assert LAUNCHER.is_file()


def test_package_data_points_at_the_installed_package():
    """The data directory Nuitka copies is the installed package's own."""
    assert (PACKAGE_DATA / "role_schema.json").is_file()


def test_nuitka_command_flags(tmp_path):
    """Build a standalone binary that includes the package and its data."""
    cmd = nuitka_command("py", tmp_path)
    assert cmd[:3] == ["py", "-m", "nuitka"]
    assert "--standalone" in cmd
    assert "--assume-yes-for-downloads" in cmd
    assert f"--output-dir={tmp_path}" in cmd
    assert "--include-package=botc_tokens" in cmd
    # Package data goes beside the executable, not into a botc_tokens/ folder that would collide with its name.
    assert "--include-package-data=botc_tokens" not in cmd
    assert cmd[cmd.index("--include-package=botc_tokens") + 1] == f"--include-data-dir={PACKAGE_DATA}=botc_tokens_data"
    assert "--include-package-data=certifi" not in cmd  # Nuitka includes certifi's CA bundle on its own
    assert "--output-filename=botc_tokens" in cmd
    assert cmd[-1] == str(LAUNCHER)


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Darwin", "arm64", "macos-arm64"),
        ("Windows", "AMD64", "windows-x86_64"),
        ("Linux", "x86_64", "linux-x86_64"),
        ("Linux", "aarch64", "linux-arm64"),
    ],
)
def test_platform_tag(system, machine, expected):
    """Normalise platform names into the archive tag."""
    assert platform_tag(system, machine) == expected


def test_platform_tag_rejects_unknown():
    """Unknown platforms are an error rather than a misnamed archive."""
    with pytest.raises(ValueError):
        platform_tag("Plan9", "mips")


def test_archive_name_extension():
    """Windows gets a zip, everything else a tarball that keeps permissions and symlinks."""
    assert archive_name("1.2.3", "Windows", "AMD64") == "botc_tokens-1.2.3-windows-x86_64.zip"
    assert archive_name("1.2.3", "Darwin", "arm64") == "botc_tokens-1.2.3-macos-arm64.tar.gz"


def _make_dist(tmp_path):
    dist = tmp_path / "botc_tokens.dist"
    (dist / "imagemagick" / "lib").mkdir(parents=True)
    (dist / "botc_tokens").write_text("binary")
    (dist / "imagemagick" / "lib" / "libMagickWand-7.Q16HDRI.10.dylib").write_text("lib")
    (dist / "imagemagick" / "lib" / "libMagickWand-7.Q16HDRI.dylib").symlink_to("libMagickWand-7.Q16HDRI.10.dylib")
    return dist


def test_make_archive_tar_keeps_symlinks(tmp_path):
    """Tarballs are rooted at botc_tokens/ and keep library symlinks as symlinks."""
    dist = _make_dist(tmp_path)
    archive = make_archive(dist, tmp_path / "out.tar.gz")
    with tarfile.open(archive) as tar:
        names = tar.getnames()
        link = tar.getmember("botc_tokens/imagemagick/lib/libMagickWand-7.Q16HDRI.dylib")
    assert "botc_tokens/botc_tokens" in names
    assert link.issym()


def test_make_archive_zip(tmp_path):
    """Zips are rooted at botc_tokens/ too."""
    dist = _make_dist(tmp_path)
    archive = make_archive(dist, tmp_path / "out.zip")
    with zipfile.ZipFile(archive) as archive_file:
        names = archive_file.namelist()
    assert "botc_tokens/botc_tokens" in names
    assert all(name.startswith("botc_tokens/") for name in names)


def _fake_compile(tmp_path, record):
    def run(cmd, check):
        record.append(cmd)
        output_dir = Path(next(arg for arg in cmd if arg.startswith("--output-dir=")).split("=", 1)[1])
        dist = output_dir / "launcher.dist"
        dist.mkdir(parents=True)
        (dist / "botc_tokens").write_text("binary")
        return subprocess.CompletedProcess(cmd, 0)

    return run


def test_main_compiles_bundles_and_archives(tmp_path, monkeypatch, capsys):
    """Compile, bundle ImageMagick, copy the project license, and write the archive."""
    commands = []
    bundled = []
    monkeypatch.setattr(build_binary.subprocess, "run", _fake_compile(tmp_path, commands))
    monkeypatch.setattr(build_binary, "bundle", lambda prefix, dist, system: bundled.append((prefix, dist, system)))
    monkeypatch.setattr(build_binary, "version", "9.9.9")
    license_file = tmp_path / "LICENSE"
    license_file.write_text("MIT")
    monkeypatch.setattr(build_binary, "PROJECT_LICENSE", license_file)
    output_dir = tmp_path / "out"

    result = main(["--output-dir", str(output_dir), "--conda-prefix", str(tmp_path / "env"), "--system", "Linux",
                   "--machine", "x86_64"])

    assert result == 0
    assert len(commands) == 1 and "--standalone" in commands[0]
    assert bundled == [(tmp_path / "env", output_dir / "botc_tokens.dist", "Linux")]
    assert not (output_dir / "launcher.dist").exists()
    assert (output_dir / "botc_tokens.dist" / "LICENSE").read_text() == "MIT"
    archive = output_dir / "botc_tokens-9.9.9-linux-x86_64.tar.gz"
    assert archive.is_file()
    assert str(archive) in capsys.readouterr().out


def test_main_replaces_a_stale_dist(tmp_path, monkeypatch):
    """A leftover botc_tokens.dist from an earlier build is replaced, not merged into."""
    monkeypatch.setattr(build_binary.subprocess, "run", _fake_compile(tmp_path, []))
    monkeypatch.setattr(build_binary, "version", "9.9.9")
    monkeypatch.setattr(build_binary, "PROJECT_LICENSE", tmp_path / "missing-LICENSE")
    output_dir = tmp_path / "out"
    stale = _make_dist(output_dir)
    (stale / "stale-file").write_text("old")

    assert main(["--output-dir", str(output_dir), "--system", "Linux", "--machine", "x86_64"]) == 0
    assert not (output_dir / "botc_tokens.dist" / "stale-file").exists()
    assert (output_dir / "botc_tokens.dist" / "botc_tokens").is_file()


def test_main_skip_compile_without_prefix_warns(tmp_path, monkeypatch, capsys):
    """Reuse an existing dist and warn that no ImageMagick was bundled."""
    def fail(*args, **kwargs):
        raise AssertionError("Nuitka must not run with --skip-compile")

    monkeypatch.setattr(build_binary.subprocess, "run", fail)
    monkeypatch.setattr(build_binary, "version", "9.9.9")
    monkeypatch.setattr(build_binary, "PROJECT_LICENSE", tmp_path / "missing-LICENSE")
    output_dir = tmp_path / "out"
    _make_dist(output_dir)

    result = main(["--output-dir", str(output_dir), "--skip-compile", "--system", "Windows", "--machine", "AMD64"])

    assert result == 0
    output = capsys.readouterr().out
    assert "Warning" in output and "ImageMagick" in output
    assert "LICENSE" in output
    assert (output_dir / "botc_tokens-9.9.9-windows-x86_64.zip").is_file()
