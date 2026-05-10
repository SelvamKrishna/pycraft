import shutil
import sys
from pathlib import Path
from enum import Enum

from . import _log
from . import _cmd

class PackageKind(Enum):
    WEB = 1
    GIT = 2
    ARCHIVE = 3
    MANUAL = 4

class Package:
    def __init__(self, path: Path, kind: PackageKind, link: str) -> None:
        self.name = path.name
        self.path = path
        self.kind = kind
        self.link = link

    def check(self) -> bool:
        return self.path.exists() and any(self.path.iterdir())

    def uninstall(self, suppress_warning: bool = False) -> None:
        if self.path.exists():
            shutil.rmtree(self.path)
            _log.info(f"Removed package {self.name} from `{self.path}`")
        elif not suppress_warning:
            _log.warn(f"Package {self.name} not found")

    def _clone_from_git(self) -> None:
        _log.info(f"Cloning {self.name} from `{self.link}`...")
        self.uninstall(True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _cmd.call_cmd(["git", "clone", "--depth", "1", self.link, str(self.path)], check=True)
        _log.info(f"Successfully cloned package {self.name}")

    def _install_from_web(self) -> None:
        _log.info(f"Downloading {self.name} from `{self.link}`...")
        self.uninstall(True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _cmd.call_cmd(["curl", "-L", "--fail", self.link, "-o", str(self.path)], check=True)
        _log.info(f"Successfully downloaded package {self.name}")

    def _install_from_archive(self) -> None:
        import tempfile
        import tarfile
        import zipfile

        _log.info(f"Extracting {self.name} from `{self.link}`...")
        self.uninstall(True)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
            tmp_path = Path(tmp.name)
            _cmd.call_cmd(["curl", "-L", "--fail", self.link, "-o", str(tmp_path)], check=True)

            if self.link.endswith(('.tar.gz', '.tgz')):
                with tarfile.open(tmp_path, 'r:gz') as tar:
                    tar.extractall(self.path.parent)
            elif self.link.endswith('.zip'):
                with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                    zip_ref.extractall(self.path.parent)
            else:
                shutil.move(str(tmp_path), self.path)

            tmp_path.unlink()

        extracted = list(self.path.parent.glob("*"))
        if len(extracted) == 1 and extracted[0].is_dir() and extracted[0].name != self.name:
            shutil.move(str(extracted[0]), str(self.path))

        _log.info(f"Successfully extracted package {self.name}")

    def _manual_help(self) -> None:
        _log.warn(f"Please install package {self.name} manually")
        _log.warn(f"Download from: {self.link}")
        _log.warn(f"Install to: {self.path.absolute()}")
        sys.exit(0)

    def install(self) -> None:
        self.uninstall(True)

        if self.kind == PackageKind.WEB:
            self._install_from_web()
        elif self.kind == PackageKind.GIT:
            self._clone_from_git()
        elif self.kind == PackageKind.ARCHIVE:
            self._install_from_archive()
        elif self.kind == PackageKind.MANUAL:
            self._manual_help()

    def ensure(self) -> None:
        if not self.check():
            self.install()
