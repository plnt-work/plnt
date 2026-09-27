"""Build hook: ship registry/bundles inside the package as plnt/_bundles and
demo/workspaces as plnt/_demo.

Everything else is configured in pyproject.toml.
"""

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).parent


SHIPPED = [
    (ROOT / "registry" / "bundles", ROOT / "plnt" / "_bundles", "_bundles"),
    (ROOT / "demo" / "workspaces", ROOT / "plnt" / "_demo", "_demo"),
]


class BuildWithBundles(build_py):
    def run(self):
        super().run()
        for src, fallback, name in SHIPPED:
            if not src.is_dir():  # building from an sdist that already has them
                src = fallback
            if not src.is_dir():
                continue
            dest = Path(self.build_lib) / "plnt" / name
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(
                src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.py[cod]", ".*")
            )


setup(cmdclass={"build_py": BuildWithBundles})
