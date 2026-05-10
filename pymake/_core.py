import sys
import time
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

from . import _log
from . import _cfg
from . import _cmd

SOURCE_EXTENSIONS: set = {".c", ".cc", ".cpp", ".c++", ".cxx"}

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

@dataclass
class ProjectConfig:
    name: str = "app"
    cc: str = "g++"
    standard: str = "c++23"
    cxx_flags: list[str] = field(default_factory=lambda: ["-Wall", "-Wextra", "-Wpedantic"])
    src_dir: Path = Path("source")
    out_dir: Path = Path("build")
    inc_dirs: list[Path] = field(default_factory=lambda: [Path("include")])
    lib_dirs: list[Path] = field(default_factory=lambda: [Path("external")])
    libraries: list[str] = field(default_factory=list)
    defines: list[str] = field(default_factory=list)
    parallel: int = _cfg.get_default_parallel_jobs()

    def __post_init__(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def target(self) -> Path:
        if _cfg.is_windows():
            return self.out_dir / f"{self.name}.exe"
        return self.out_dir / self.name

class Project:
    def __init__(self, prjcfg: ProjectConfig) -> None:
        self.prjcfg = prjcfg
        self.verbose = False
        self.exec_cmd = [
            self.prjcfg.cc, f"-std={self.prjcfg.standard}"
        ]

    def _needs_compile(self, src: Path, obj: Path) -> bool:
        if not obj.exists():
            return True
        return src.stat().st_mtime > obj.stat().st_mtime

    def _collect_srcs(self) -> list[Path]:
        if not self.prjcfg.src_dir.exists():
            _log.err(f"Source directory `{self.prjcfg.src_dir}` not found")
            return []

        srcs = [
            path for path in self.prjcfg.src_dir.rglob("*")
            if path.is_file() and path.suffix in SOURCE_EXTENSIONS
        ]

        if not srcs:
            _log.err(f"No source files found in {str(self.prjcfg.src_dir)}")
            return []

        return srcs

    def _compile_srcs(self) -> list[Path]:
        sources = self._collect_srcs()
        if not sources:
            return []

        objects: list[Path | None] = [None] * len(sources)
        failed = False

        def compile_file(idx: int, src: Path):
            rel_path = src.relative_to(self.prjcfg.src_dir)
            obj = self.prjcfg.out_dir / rel_path.with_suffix(".o")
            obj.parent.mkdir(parents=True, exist_ok=True)

            if not self._needs_compile(src, obj):
                if self.verbose:
                    _log.info(f"(up to date) {src.name} -> {obj.name}")
                return idx, obj, False

            cmd = self.exec_cmd + [
                "-c", str(src), "-o", str(obj)
            ]

            try:
                _cmd.call_cmd(cmd, check=True)
                _log.info(f"{src.name} -> {obj.name}")
                return idx, obj, False
            except:
                _log.err(f"Failed to compile {src.name}", exit=False)
                return idx, None, True

        with ThreadPoolExecutor(max_workers=self.prjcfg.parallel) as executor:
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
            _log.err("Compilation failed", 1)

        return valid_objects

    def _link(self, objs: list[Path]) -> None:
        target = self.prjcfg.target()
        target.parent.mkdir(parents=True, exist_ok=True)

        cmd = self.exec_cmd + [str(obj) for obj in objs] + ["-o", str(target)]

        try:
            _cmd.call_cmd(cmd, check=True)
            if not _cfg.is_windows():
                target.chmod(target.stat().st_mode | 0o111)
            _log.info(f"Project {self.prjcfg.name} built to `{target}`")
        except:
            _log.err(f"Failed to link project {self.prjcfg.name}")

    def build(self, buildcfg: BuildConfig) -> None:
        self.verbose = buildcfg.is_verbose
        self.exec_cmd.extend(self.prjcfg.cxx_flags)

        if buildcfg.is_mode_run():
            return

        if buildcfg.should_clean:
            if self.prjcfg.out_dir.exists():
                shutil.rmtree(self.prjcfg.out_dir)
                _log.info(f"Cleaned `{self.prjcfg.out_dir}`")
            self.prjcfg.out_dir.mkdir(parents=True, exist_ok=True)

        if buildcfg.is_mode_release():
            self.exec_cmd.extend(["-O2", "-DNDEBUG"])
            _log.info("Building in RELEASE mode")
        else:
            self.exec_cmd.extend(["-O0", "-g"])
            _log.info("Building in DEBUG mode")

        self.exec_cmd.extend(f"-D{ddf}" for ddf in self.prjcfg.defines)
        self.exec_cmd.extend(f"-I{dir}" for dir in self.prjcfg.inc_dirs)
        self.exec_cmd.extend(f"-L{dir}" for dir in self.prjcfg.lib_dirs)
        self.exec_cmd.extend(f"-l{lib}" for lib in self.prjcfg.libraries)

        start_time = time.time()
        objs = self._compile_srcs()

        if not objs:
            _log.err("No object files generated")

        self._link(objs)
        elapsed = time.time() - start_time

        _log.info(f"Build successful! ({elapsed:.2f}s)")

    def run(self, arguments: list[str] | None = None) -> None:
        if arguments is None:
            arguments = []

        target = self.prjcfg.target()

        if not target.exists():
            _log.err(f"Target `{target}` not found. Please build first.")

        _log.info(f"Running `{target}`")

        try:
            _cmd.call_cmd([str(target)] + arguments, capture=False)
        except KeyboardInterrupt:
            print()
            sys.exit(130)
