"""Guards for the user documentation."""
# Standard Library
from pathlib import Path
import re

REPO_ROOT = Path(__file__).parent.parent


def test_readme_python_version_matches_pyproject():
    """The README names the same minimum Python version the package requires."""
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    minimum = re.search(r'requires-python\s*=\s*">=([\d.]+)"', pyproject).group(1)
    readme = " ".join((REPO_ROOT / "README.md").read_text(encoding="utf-8").split())
    assert f"Python {minimum} or newer" in readme
