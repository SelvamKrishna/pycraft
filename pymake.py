import sys
import time
import platform
import subprocess
import shutil
import colorama

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
        self.verbose = False
        self.cfg = cfg
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
            Log.err(
                f"Source directory $Y`{self.cfg.src_dir}`$_ does not exist"
            )

        srcs = [
            path for path in self.cfg.src_dir.rglob("*")
            if path.is_file() and path.suffix in SOURCE_EXTENSIONS
        ]

        if not srcs:
            Log.err(f"No source files found in $Y`{str(self.cfg.src_dir)}`$_")

        return sorted(srcs)

    def _compile_srcs(self) -> list[Path]:
        objects: list[Path | None] = [None] * len(self._collect_srcs())

        def compile_file(idx: int, src: Path) -> tuple[int, Path | None]:
            rel_path = src.relative_to(self.cfg.src_dir)
            obj = self.cfg.out_dir / rel_path.with_suffix(".o")
            obj.parent.mkdir(parents=True, exist_ok=True)

            if not Project._needs_compile(src, obj):
                return idx, obj

            cmd = [
                *self.exec_cmd,
                "-c", str(src.relative_to(Path.cwd())),
                "-o", str(obj.relative_to(Path.cwd()))
            ]

            code = run_cmd(cmd, check=False).returncode
            Log._result(
                f"$B`{src.name}`$_ -> $B`{obj.name}`$_", code, self.verbose
            )

            return idx, obj

        srcs = self._collect_srcs()

        with ThreadPoolExecutor(max_workers=self.cfg.parallel) as executor:
            futures = {
                executor.submit(compile_file, i, src): i
                for i, src in enumerate(srcs)
            }

            for future in as_completed(futures):
                idx, obj = future.result()
                objects[idx] = obj

        valid_objects = [obj for obj in objects if obj is not None]

        if len(valid_objects) != len(srcs):
            Log.err("Compilation failed", len(srcs) - len(valid_objects))

        return valid_objects

    def _link(self, objs: list[Path]) -> None:
        target = self.cfg.target()
        target.parent.mkdir(parents=True, exist_ok=True)

        obj_str = [str(obj.relative_to(Path.cwd())) for obj in objs]

        cmd = [
            *self.exec_cmd, *obj_str,
            "-o", str(target.relative_to(Path.cwd()))
        ]

        code = run_cmd(cmd, check=False).returncode

        if code == 0 and PLATFORM != "Windows":
            target.chmod(target.stat().st_mode | 0o111)

        Log._result(f"Link '$B{self.cfg.name}$_' to '$Y{target}$_'", code)

    def build(self, build_cfg: BuildConfig) -> None:
        if build_cfg.is_mode_run():
            return

        self.verbose = build_cfg.is_verbose

        if build_cfg.should_clean:
            if self.cfg.out_dir.exists():
                shutil.rmtree(self.cfg.out_dir)
                Log.ok(f"Cleaned `$Y{self.cfg.out_dir}$_`", self.verbose)
            self.cfg.out_dir.mkdir(parents=True, exist_ok=True)

        if build_cfg.is_mode_release():
            self.exec_cmd.extend(["-O2", "-DNDEBUG", "-s"])
        else:
            self.exec_cmd.extend(["-O0", "-g"])

        self.exec_cmd.extend(f"-D{ddf}" for ddf in self.cfg.defines)
        self.exec_cmd.extend(f"-I{dir}" for dir in self.cfg.inc_dirs)
        self.exec_cmd.extend(f"-L{dir}" for dir in self.cfg.lib_dirs)
        self.exec_cmd.extend(f"-l{lib}" for lib in self.cfg.libraries)

        start_time = time.time()
        objs = self._compile_srcs()

        if not objs:
            Log.err("No object files generated")

        self._link(objs)
        elapsed = time.time() - start_time

        Log.ok(f"Build successful! Took $C[{elapsed:.2f}s]$_")

    def run(self, arguments: list[str] | None = None) -> None:
        if arguments is None:
            arguments = []

        target = self.cfg.target()

        if not target.exists():
            Log.err(f"Target `{target}` not found. Please build first.")

        Log.print(f"Running: $C{target}$_")

        try:
            subprocess.check_call([str(target), *arguments])
        except KeyboardInterrupt:
            print()
            sys.exit(130)
        except FileNotFoundError:
            Log.err(f"Executable `{target}` not found or not executable")
        except Exception as e:
            Log.err(f"Failed to run executable: {e}")


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
                Log._pymake()
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
        Log._pymake()
        Log.print(colorama.Style.DIM, "=" * 80)
        Log.print(colorama.Style.BRIGHT, "Usage:")
        Log.print(f"    {sys.argv[0]} $C<command>$_ $D[options]$_")
        print()
        Log.print(colorama.Style.BRIGHT, "Commands:")
        Log.print(f"    $Cdebug$_       Build with debug symbols")
        Log.print(f"    $Crelease$_     Build optimized for release")
        Log.print(f"    $Crun$_         Run the built executable")
        print()
        Log.print(colorama.Style.BRIGHT, "Options:")
        Log.print(f"    $C-c, --clean$_   Clean before building")
        Log.print(f"    $C-r, --run$_     Run after building (for debug/release)")
        Log.print(f"    $C-v, --verbose$_ Show detailed build commands")
        Log.print(f"    $C-h, --help$_    Show this help message")
        print()


class Log:
    @classmethod
    def _pymake(cls) -> None:
        Log.print(colorama.Style.BRIGHT, f"PyMake v{VERSION}")

    @staticmethod
    def print(*args, **kwargs) -> None:
        message = " ".join(str(arg) for arg in args)

        TAGS_LUT: tuple[tuple[str, str], ...] = (
            ('$B', colorama.Style.BRIGHT),
            ('$D', colorama.Style.DIM),
            ('$R', colorama.Style.RESET_ALL),
            ('$G', colorama.Fore.GREEN),
            ('$Y', colorama.Fore.YELLOW),
            ('$R', colorama.Fore.RED),
            ('$C', colorama.Fore.CYAN),
            ('$M', colorama.Fore.MAGENTA),
            ('$_', colorama.Style.RESET_ALL),
        )

        for tag, color in TAGS_LUT:
            message = message.replace(tag, color)

        print(message, **kwargs)

    @classmethod
    def err(cls, message: str, err_code: int = 1) -> None:
        cls.print(f"$R[error:{err_code}]$_ $R{message}$_")
        sys.exit(err_code)

    @classmethod
    def ok(cls, message: str, show: bool = True) -> None:
        if show:
            cls.print(f"$G[ok]$_ {message}")

    @classmethod
    def _result(cls, message: str, code: int, show: bool = True) -> None:
        cls.ok(message, show) if code == 0 else cls.err(message, code)


def init() -> None:
    colorama.init(autoreset=True)


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            cmd, check=check, capture_output=True, text=True
        )

        if result.returncode != 0 and result.stderr:
            Log.print(colorama.Style.DIM, f"$ {' '.join(cmd)}")
            Log.print(result.stderr)

        return result

    except FileNotFoundError:
        Log.err(f"Command not found: {cmd[0]}")
    except Exception as e:
        Log.err(f"Failed to run command: {e}")

    sys.exit(1)


if __name__ == "__main__":
    Log._pymake()
