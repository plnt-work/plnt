"""Build hook: ship registry/bundles inside the package as plnt/_bundles.

Everything else is configured in pyproject.toml.
"""

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).parent


class BuildWithBundles(build_py):
    def run(self):
        super().run()
        src = ROOT / "registry" / "bundles"
        if not src.is_dir():  # building from an sdist that already has them
            src = ROOT / "plnt" / "_bundles"
        if not src.is_dir():
            return
        dest = Path(self.build_lib) / "plnt" / "_bundles"
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(
            src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.py[cod]", ".*")
        )


setup(cmdclass={"build_py": BuildWithBundles})
