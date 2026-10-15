"""Bundle the canonical router even on checkouts without symlink support."""
from pathlib import Path
import shutil
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildRouter(build_py):
    def run(self):
        super().run()
        source = Path(__file__).resolve().parent / "control-plane"
        target = Path(self.build_lib) / "solaris_intake" / "control-plane"
        target.mkdir(parents=True, exist_ok=True)
        for path in source.iterdir():
            if path.is_file() and path.suffix in {".py", ".json", ".md"}:
                shutil.copy2(path, target / path.name)


setup(cmdclass={"build_py": BuildRouter})
