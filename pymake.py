import sys
import platform
import colorama
import subprocess
import shutil

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pymake_cfg as cfg


def _get_target() -> Path:
    target = Path(cfg.OUT_DIR) / cfg.NAME
    if platform.system() == "Windows":
        target = target.with_suffix(".exe")
    return target


TARGET = _get_target()
OBJ_DIR = Path(cfg.OUT_DIR)
VALID_EXTENSIONS = {".c", ".cc", ".cpp", ".c++", ".cxx"}

flag_verbose = False


def _ansi_print(color: str, message: str, end: str = "\n") -> None:
    print(f"{color}{message}{colorama.Style.RESET_ALL}")


def _print_err(exit_code: int, message: str, flag_exit: bool = True) -> None:
    _ansi_print(colorama.Fore.RED, f"Error: {message}")
    if flag_exit:
        sys.exit(exit_code)


def _print_help_message() -> None:
    def _print_usage(cmd: str, desc: str) -> None:
        print(f"    {sys.argv[0]} {cmd} => ", end="")
        _ansi_print(colorama.Fore.BLUE, desc)

    def _print_flag(cmd: str, desc: str) -> None:
        print(f"    {cmd} => ", end="")
        _ansi_print(colorama.Fore.BLUE, desc)

    _ansi_print(colorama.Style.BRIGHT, f"PyMake v{cfg.VERSION}")

    _ansi_print(colorama.Style.BRIGHT, f"\nUsage:")
    _print_usage("[--help | -h]", "Show this help")
    _print_usage("debug [flags]", "Build with debug symbols")
    _print_usage("release [flags]", "Build optimized")
    _print_usage("run", "Run binary")

    _ansi_print(colorama.Style.BRIGHT, f"\nFlags:")
    _print_flag("--verbose | -v", "Show commands")
    _print_flag("--clean   | -c", "Clean build first")
    _print_flag("--run     | -r", "Run after build")

    print("")
    sys.exit(0)


def _run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    if flag_verbose:
        _ansi_print(colorama.Style.DIM, f"> {' '.join(str(c) for c in cmd)}")

    return subprocess.run(cmd, check=False)


class ProjectBuilder:
    def __init__(self, flag_clean: bool, is_mode_release: bool) -> None:
        self.out_dir = Path(cfg.OUT_DIR)
        self.src_dir = Path(cfg.SRC_DIR)
        self.mode_release: bool = is_mode_release

        self.sources = self._collect_srcs()

        if not self.sources:
            _print_err(1, "No sources found")

        self._prepare_dirs(flag_clean)
        self.exec_cmd = self._build_exec_cmd()

    def _prepare_dirs(self, flag_clean: bool):
        if flag_clean and self.out_dir.exists():
            shutil.rmtree(self.out_dir)

        self.out_dir.mkdir(parents=True, exist_ok=True)

        if not self.src_dir.exists():
            _print_err(1, f"Source directory `{self.src_dir}` not found")

    def _collect_srcs(self) -> list[Path]:
        return sorted(
            Path(source)
            for source in self.src_dir.rglob("*")
            if source.suffix in VALID_EXTENSIONS
        )

    def _build_exec_cmd(self) -> list[str]:
        exec_cmd = [cfg.CC, f"-std={cfg.STANDARD}", *cfg.CXX_FLAGS]

        if self.mode_release:
            exec_cmd.extend(["-O2", "-DNDEBUG", "-s"])
        else:
            exec_cmd.extend(["-O0", "-g"])

        exec_cmd.extend(f"-I{inc_dir}" for inc_dir in cfg.INC_DIRS)
        exec_cmd.extend(f"-D{define}" for define in cfg.DEFINES)
        exec_cmd.extend(f"-L{lib_dir}" for lib_dir in cfg.LIB_DIRS)
        exec_cmd.extend(f"-l{library}" for library in cfg.LIBRARIES)

        return exec_cmd

    @staticmethod
    def _need_recompile(src_path: Path, obj_path: Path) -> bool:
        return not obj_path.exists() or src_path.stat().st_mtime > obj_path.stat().st_mtime

    @staticmethod
    def _get_obj_path(source: Path) -> Path:
        relative_path = source.relative_to(Path(cfg.SRC_DIR))
        obj_path = OBJ_DIR / relative_path.with_suffix(".o")
        obj_path.parent.mkdir(parents=True, exist_ok=True)
        return obj_path

    def _compile_source(self, source: Path) -> Path:
        obj_path = self._get_obj_path(source)

        if not self._need_recompile(source, obj_path):
            return obj_path

        cmd_result = _run_cmd([
            *self.exec_cmd, "-c", str(source), "-o", str(obj_path)
        ])

        if cmd_result.returncode != 0:
            _print_err(cmd_result.returncode, f"Failed to compile `{source}`")

        return obj_path

    def _compile_all(self) -> list[Path]:
        with ThreadPoolExecutor(max_workers=cfg.PARALLEL) as pool:
            return list(pool.map(self._compile_source, self.sources))

    def _link(self, objects: list[Path]) -> None:
        obj_str = [str(obj) for obj in objects]
        cmd_result = _run_cmd([*self.exec_cmd, *obj_str, "-o", str(TARGET)])

        if cmd_result.returncode != 0:
            _print_err(cmd_result.returncode, "Failed to link")

    def build(self) -> None:
        self._link(self._compile_all())

    @staticmethod
    def run(arguments: list[str] | None = None) -> None:
        arguments = [] if arguments is None else arguments

        if not TARGET.exists():
            _print_err(1, f"Target `{TARGET}` not found")

        try:
            subprocess.run([str(TARGET), *arguments])
        except KeyboardInterrupt:
            print()
            sys.exit(130)


@dataclass(frozen=True)
class CLI:
    command: str
    verbose: bool
    release: bool
    clean: bool
    run_after: bool
    args: list[str]

    @staticmethod
    def parse() -> CLI:
        if len(sys.argv) <= 1:
            _print_help_message()

        main_cmd = sys.argv[1].strip().lower()

        if main_cmd in ("--help", "-h"):
            _print_help_message()

        if main_cmd not in {"debug", "release", "run"}:
            _print_err(1, f"Unknown command `{main_cmd}`")

        return CLI(
            command=main_cmd,
            verbose="--verbose" in sys.argv or "-v" in sys.argv,
            release=main_cmd == "release",
            clean=main_cmd == "release" or "--clean" in sys.argv or "-c" in sys.argv,
            run_after="--run" in sys.argv or "-r" in sys.argv,
            args=sys.argv[2:]
        )


def main() -> None:
    cli = CLI.parse()

    global flag_verbose
    flag_verbose = cli.verbose

    if cli.command == "run":
        ProjectBuilder.run(sys.argv[2:])
        sys.exit(0)

    builder = ProjectBuilder(cli.clean, cli.release)
    builder.build()

    if cli.run_after:
        builder.run()


if __name__ == "__main__":
    colorama.init(autoreset=True)
    main()
