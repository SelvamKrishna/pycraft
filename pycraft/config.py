import platform
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from . import _log

VERSION: int = 2


class Language(Enum):
    C = "c"
    CPP = "c++"


class Compiler(Enum):
    GCC = "gcc"
    GXX = "g++"
    CLANG = "clang"
    CLANGXX = "clang++"
    MSVC = "cl"


@dataclass(frozen=True)
class _SysInfo:
    os: str = platform.system().lower()
    architecture: str = platform.machine().lower()
    library_ver: int = VERSION


_SYS_INFO = _SysInfo()


def is_64bit() -> bool:
    return sys.maxsize > 2**32


def is_windows() -> bool:
    return _SYS_INFO.os == "windows"


def is_linux() -> bool:
    return _SYS_INFO.os == "linux"


def is_macos() -> bool:
    return _SYS_INFO.os == "darwin"


def is_unix() -> bool:
    return is_linux() or is_macos()


def get_version() -> int:
    return VERSION


def get_architecture() -> str:
    return _SYS_INFO.architecture


@staticmethod
def get_default_parallel_jobs() -> int:
    import os

    try:
        cpu_count = os.cpu_count() or 4
        return max(1, cpu_count)
    except Exception as _:
        return 4


class BuildMode(Enum):
    DEBUG = "debug"
    RELEASE = "release"
    TEST = "test"
    RUN = "run"


@dataclass(frozen=True)
class BuildConfig:
    mode: BuildMode
    should_clean: bool = False
    should_run_after: bool = False
    run_args: list[str] | None = None

    def is_mode_debug(self) -> bool:
        return self.mode == BuildMode.DEBUG

    def is_mode_release(self) -> bool:
        return self.mode == BuildMode.RELEASE

    def is_mode_test(self) -> bool:
        return self.mode == BuildMode.TEST

    def is_mode_run(self) -> bool:
        return self.mode == BuildMode.RUN

    def should_run(self) -> bool:
        return self.is_mode_run() or self.should_run_after


@dataclass
class ProjectConfig:
    name: str = "app"
    cc: Compiler = Compiler.GXX
    lang: Language = Language.CPP
    version: int = 23
    cxx_flags: tuple[str, ...] = ("-Wall", "-Wextra", "-Wpedantic")
    src_dir: Path = Path("source")
    out_dir: Path = Path("build")
    test_dir: Path | None = None
    inc_dirs: tuple[Path, ...] = (Path("include"),)
    lib_dirs: tuple[Path, ...] = (Path("external"),)
    libraries: tuple[str, ...] = ()
    defines: tuple[str, ...] = ()
    parallel: int = get_default_parallel_jobs()
    pch_header: Path | None = None

    def __post_init__(self) -> None:
        if shutil.which(self.cc.value) is None:
            _log.err(f"Compiler $B`{self.cc}`$0 not found.")

        self.out_dir.mkdir(parents=True, exist_ok=True)

        if not self.src_dir.exists():
            _log.err(f"Source directory $dir`{self.src_dir}`$0 not found")

        if self.pch_header is not None and not self.pch_header.exists():
            _log.err(f"Precompiled header $dir`{self.pch_header}`$0 not found")

        self.target = self.out_dir / f"{self.name}"

        if is_windows():
            self.target = self.target.with_suffix(".exe")

    def get_flags(self) -> list[str]:
        return [
            str(self.cc.value),
            f"-std={self.lang.value}{self.version}",
            *self.cxx_flags,
            *[f"-D{ddf}" for ddf in self.defines],
            *[f"-I{inc}" for inc in self.inc_dirs],
        ]

    def get_link_flags(self, objs: list[Path]) -> list[str]:
        return [
            str(self.cc.value),
            f"-std={self.lang.value}{self.version}",
            *[f"-L{lld}" for lld in self.lib_dirs],
            *[str(obj) for obj in objs],
            *[f"-l{lib}" for lib in self.libraries],
            "-o",
            str(self.target),
        ]

    def generate_compile_cmds(self, file: Path) -> None:
        with open(file, "w") as f:
            f.write("\n".join(self.get_flags()[1:]))

    def configure_for_mode(self, mode: BuildMode) -> None:
        flags_to_add: list[str] = []

        match mode:
            case BuildMode.DEBUG:
                self.out_dir = self.out_dir / "debug"
                flags_to_add = ["-g"]

            case BuildMode.RELEASE:
                self.out_dir = self.out_dir / "release"
                flags_to_add = ["-O2", "-DNDEBUG"]

            case BuildMode.RUN:
                if (self.out_dir / "debug").exists():
                    self.out_dir = self.out_dir / "debug"
                else:
                    _log.err("Debug build not found. Run in debug mode first.")

            case BuildMode.TEST:
                self.out_dir = self.out_dir / "test"
                self.name = f"test_{self.name}"
                flags_to_add = ["-O0"]

                if self.test_dir is None:
                    _log.err("Test directory not specified.")
                    raise ValueError

                self.src_dir = self.test_dir

        self.target = self.out_dir / self.name

        self.cxx_flags = tuple(f for f in self.cxx_flags if f not in flags_to_add)
        self.cxx_flags += tuple(flags_to_add)

        if is_windows():
            self.target = self.target.with_suffix(".exe")
