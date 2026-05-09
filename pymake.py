import sys
import time
import platform
import subprocess
import shutil

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum

VERSION: int = 2
PLATFORM = platform.system()
SOURCE_EXTENSIONS: set = {".c", ".cc", ".cpp", ".c++", ".cxx", ".cxx", ".c++"}


class BuildMode(Enum):
    DEBUG = 0
    RELEASE = 1
    RUN = 2


@dataclass(frozen=True)
class BuildConfig:
    mode: BuildMode
    should_clean: bool = False
    should_run_after: bool = False
    is_verbose: bool = False
    run_args: list[str] | None = None

    def is_mode_release(self) -> bool:
        return self.mode == BuildMode.RELEASE

    def is_mode_debug(self) -> bool:
        return self.mode == BuildMode.DEBUG

    def is_mode_run(self) -> bool:
        return self.mode == BuildMode.RUN

    def should_run(self) -> bool:
        return self.is_mode_run() or self.should_run_after


@dataclass(frozen=True)
class ProjectConfig:
    name: str = "app"
    cc: str = "g++"
    standard: str = "c++23"
    cxx_flags: tuple[str, ...] = ("-Wall", "-Wextra", "-Wpedantic")
    src_dir: Path = Path("source")
    out_dir: Path = Path("build")
    inc_dirs: tuple[Path, ...] = (Path("include"),)
    lib_dirs: tuple[Path, ...] = (Path("external"),)
    libraries: tuple[str, ...] = ()
    defines: tuple[str, ...] = ()
    parallel: int = 8

    def target(self) -> Path:
        if PLATFORM == "Windows":
            return self.out_dir / f"{self.name}.exe"
        return self.out_dir / self.name


class Project:
    def __init__(self, cfg: ProjectConfig) -> None:
        self.cfg = cfg
        self.verbose = False
        self.exec_cmd = [
            self.cfg.cc, f"-std={self.cfg.standard}", *self.cfg.cxx_flags
        ]

    @staticmethod
    def _needs_compile(src: Path, obj: Path) -> bool:
        if not obj.exists():
            return True
        if src.stat().st_mtime > obj.stat().st_mtime:
            return True
        # TODO: Add support for header dependencies
        return False

    def _collect_srcs(self) -> list[Path]:
        if not self.cfg.src_dir.exists():
            Log.err(f"Source directory `{self.cfg.src_dir}` not found")

        srcs = [
            path for path in self.cfg.src_dir.rglob("*")
            if path.is_file() and path.suffix in SOURCE_EXTENSIONS
        ]

        if not srcs:
            Log.err(f"No source files found in {str(self.cfg.src_dir)}")

        return srcs

    def _compile_srcs(self) -> list[Path]:
        sources: list[Path] = self._collect_srcs()
        objects: list[Path | None] = [None] * len(sources)
        failed = False

        def compile_file(idx: int, src: Path) -> tuple[int, Path | None, bool]:
            rel_path = src.relative_to(self.cfg.src_dir)
            obj = self.cfg.out_dir / rel_path.with_suffix(".o")
            obj.parent.mkdir(parents=True, exist_ok=True)

            if not Project._needs_compile(src, obj):
                if self.verbose:
                    Log.info(f"(up to date) {src.name} -> {obj.name}")
                return idx, obj, False

            cmd = [
                *self.exec_cmd,
                "-c", str(src.relative_to(Path.cwd())),
                "-o", str(obj.relative_to(Path.cwd()))
            ]

            result = run_cmd(cmd, check=False)
            success = result.returncode == 0

            if success:
                Log.info(f"{src.name} -> {obj.name}")
            else:
                Log.err(
                    f"Failed to compile {src.name}", result.returncode, exit=False)

            return idx, obj if success else None, not success

        with ThreadPoolExecutor(max_workers=self.cfg.parallel) as executor:
            futures = {
                executor.submit(compile_file, i, src): i
                for i, src in enumerate(sources)
            }

            for future in as_completed(futures):
                idx, obj, has_error = future.result()
                objects[idx] = obj
                failed = failed or has_error

        valid_objects = [obj for obj in objects if obj is not None]

        if failed:
            Log.err("Compilation failed", 1)

        return valid_objects

    def _link(self, objs: list[Path]) -> None:
        target = self.cfg.target()
        target.parent.mkdir(parents=True, exist_ok=True)

        obj_str = [str(obj.relative_to(Path.cwd())) for obj in objs]

        cmd = [
            *self.exec_cmd, *obj_str,
            "-o", str(target.relative_to(Path.cwd()))
        ]

        result = run_cmd(cmd, check=False)
        code = result.returncode

        if code == 0 and PLATFORM != "Windows":
            target.chmod(target.stat().st_mode | 0o111)

        if code == 0:
            Log.info(f"Project {self.cfg.name} built to `{target}`")
        else:
            Log.err(f"Failed to link project {self.cfg.name}", code)

    def build(self, build_cfg: BuildConfig) -> None:
        self.verbose = Log.f_verbose = build_cfg.is_verbose

        if build_cfg.is_mode_run():
            return

        if build_cfg.should_clean:
            if self.cfg.out_dir.exists():
                shutil.rmtree(self.cfg.out_dir)
                Log.info(f"Cleaned `{self.cfg.out_dir}`")
            self.cfg.out_dir.mkdir(parents=True, exist_ok=True)

        if build_cfg.is_mode_release():
            self.exec_cmd.extend(["-O2", "-DNDEBUG", "-s"])
            Log.info("Building in __RELEASE__ mode")
        else:
            self.exec_cmd.extend(["-O0", "-g"])
            Log.info("Building in __DEBUG__ mode")

        self.exec_cmd.extend([f"-D{ddf}" for ddf in self.cfg.defines])
        self.exec_cmd.extend([f"-I{dir}" for dir in self.cfg.inc_dirs])
        self.exec_cmd.extend([f"-L{dir}" for dir in self.cfg.lib_dirs])
        self.exec_cmd.extend([f"-l{lib}" for lib in self.cfg.libraries])

        start_time = time.time()
        objs = self._compile_srcs()

        if not objs:
            Log.err("No object files generated")

        self._link(objs)
        elapsed = time.time() - start_time

        Log.info(f"Build successful! ({elapsed:.2f}s)")

    def run(self, arguments: list[str] | None = None) -> None:
        if arguments is None:
            arguments = []

        target = self.cfg.target()

        if not target.exists():
            Log.err(f"Target `{target}` not found.")

        Log.info(f"Running `{target}`")

        try:
            subprocess.run([str(target), *arguments], check=True)
        except KeyboardInterrupt:
            print()
            sys.exit(130)
        except FileNotFoundError:
            Log.err(f"Executable `{target}` not found")
        except subprocess.CalledProcessError as e:
            Log.err("Executable failed", e.returncode)
        except Exception as e:
            Log.err(f"Failed to run executable: {e}")


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
            Log.info(f"Removed package {self.name} from `{self.path}`")
        elif not suppress_warning:
            Log.warn(f"Package {self.name.upper()} not found")

    def _clone_from_git(self) -> None:
        Log.info(f"Cloning {self.name} from `{self.link}`...")
        self.uninstall(True)

        self.path.parent.mkdir(parents=True, exist_ok=True)

        result = run_cmd(
            ["git", "clone", "--depth", "1", self.link, str(self.path)], check=False)

        if result.returncode == 0:
            Log.info(f"Successfully cloned package {self.name}")
        else:
            Log.err(f"Failed to clone package {self.name}", result.returncode)

    def _install_from_web(self) -> None:
        Log.info(f"Downloading {self.name} from `{self.link}`...")
        self.uninstall(True)

        self.path.parent.mkdir(parents=True, exist_ok=True)

        result = run_cmd(
            ["curl", "-L", "--fail", self.link, "-o", str(self.path)], check=False)

        if result.returncode == 0:
            Log.info(f"Successfully downloaded package {self.name}")
        else:
            Log.err(
                f"Failed to download package {self.name}", result.returncode)

    def _install_from_archive(self) -> None:
        pass

    def _manual_help(self) -> None:
        Log.warn(f"Please install package {self.name}")
        Log.warn(f"Download link `{self.link}`")
        Log.warn(f"Package destination `{self.path.absolute()}`")
        sys.exit(1)

    def install(self) -> None:
        if self.check():
            Log.info(f"Package {self.name} already installed")
            return

        match self.kind:
            case PackageKind.WEB: self._install_from_web()
            case PackageKind.GIT: self._clone_from_git()
            case PackageKind.ARCHIVE: self._install_from_archive()
            case PackageKind.MANUAL: self._manual_help()

    def ensure(self) -> None:
        if not self.check():
            self.install()


class CLI:
    @staticmethod
    def get_build_config() -> BuildConfig:
        if len(sys.argv) <= 1:
            CLI.print_help()
            sys.exit(0)

        command = sys.argv[1].strip().lower()

        match command:
            case "debug": mode = BuildMode.DEBUG
            case "release": mode = BuildMode.RELEASE
            case "run": mode = BuildMode.RUN
            case "--version" | "-v":
                Log.print_version()
                sys.exit(0)
            case _:
                CLI.print_help()
                sys.exit(0)

        return BuildConfig(
            mode,
            "--clean" in sys.argv or "-c" in sys.argv,
            "--run" in sys.argv or "-r" in sys.argv,
            "--verbose" in sys.argv or "-v" in sys.argv,
            sys.argv[2:] if mode == BuildMode.RUN else None
        )

    @staticmethod
    def print_help() -> None:
        Log.print_version()
        Log.print("=" * 80)
        Log.print("Usage:")
        Log.print(f"  {sys.argv[0]} <command> [options]")
        print()
        Log.print("Commands:")
        Log.print(f"  debug          Build with debug symbols")
        Log.print(f"  release        Build optimized for release")
        Log.print(f"  run            Run the built executable")
        print()
        Log.print("Options:")
        Log.print(f"  -c, --clean    Clean before building")
        Log.print(f"  -r, --run      Run after building")
        Log.print(f"  -v, --verbose  Show detailed build output")
        Log.print(f"  -h, --help     Show this help message")
        print()
        Log.print("=" * 80)


class Log:
    f_verbose: bool = False

    @classmethod
    def print_version(cls) -> None:
        cls.print(f"PyMake v{VERSION}")

    @staticmethod
    def print(*args, **kwargs) -> None:
        message = " ".join(str(arg) for arg in args)
        print(message, **kwargs)

    @classmethod
    def err(cls, message: str, err_code: int = 1, exit: bool = True) -> None:
        cls.print(f"[ERROR:{err_code}]: {message}")
        if exit:
            sys.exit(err_code)

    @classmethod
    def warn(cls, message: str) -> None:
        cls.print(f"[WARNING]: {message}")

    @classmethod
    def info(cls, message: str) -> None:
        if cls.f_verbose:
            cls.print(f"[INFO]: {message}")


def init(is_verbose: bool = False) -> None:
    Log.f_verbose = is_verbose


def get_version() -> int:
    return VERSION


def get_platform() -> str:
    return PLATFORM


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            cmd, check=check, capture_output=True, text=True
        )

        if result.returncode != 0 and result.stderr:
            Log.print(result.stderr.strip())

        return result

    except FileNotFoundError:
        Log.err(f"Command not found: {cmd[0]}")
    except Exception as e:
        Log.err(f"Failed to run command: {e}")

    return subprocess.CompletedProcess(cmd, 1, "", "")  # unreachable


if __name__ == "__main__":
    Log.print_version()
