import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import _cmd, _log, _pch, config

SOURCE_EXTENSIONS = {".cpp", ".c", ".cc", ".cxx", ".c++"}


class Project:
    def __init__(
        self, prjcfg: config.ProjectConfig, buildcfg: config.BuildConfig
    ) -> None:
        self.prjcfg: config.ProjectConfig = prjcfg
        self.buildcfg: config.BuildConfig = buildcfg

        if self.buildcfg.is_mode_test():
            self.prjcfg.configure_for_test()

        self._compile_cmd: list[str] = []
        self._link_cmd: list[str] = []
        self._base_cmd: list[str] = [
            self.prjcfg.cc.value,
            f"-std={self.prjcfg.standard}",
        ]

        if self.prjcfg.pch_header is not None:
            self._pch = _pch.PrecompiledHeader(self.prjcfg.pch_header, self.prjcfg)

    def build(self) -> None:
        if self.buildcfg.is_mode_run():
            return

        if self.buildcfg.should_clean:
            self.__clean_build_dir()

        self.__build_command(self.buildcfg.is_mode_release())

        if hasattr(self, "_pch"):
            self._pch.build()

        start_time = time.time()
        objects = self.__compile_all()

        _log.info(f"Building project $U$B{self.prjcfg.name}$0")

        if not objects:
            _log.err("No object files generated")

        self._link(objects)
        elapsed = time.time() - start_time

        _log.ok(f"Build successful! $B({elapsed:.2f}s)$0")

        if self.buildcfg.should_run_after:
            self.run(self.buildcfg.run_args)

    def __clean_build_dir(self) -> None:
        _log.info(f"Cleaning project $B$U{self.prjcfg.name}$0")
        try:
            if self.prjcfg.out_dir.exists():
                shutil.rmtree(self.prjcfg.out_dir)
                _log.ok(f"$DCleaned `{self.prjcfg.out_dir}`$0")
            self.prjcfg.out_dir.mkdir(parents=True, exist_ok=True)

        except PermissionError as e:
            _log.err(
                f"Permission denied while cleaning: $file{e.filename}$0", err_code=126
            )

        except Exception as e:
            _log.err(f"Failed to clean directory: $dir{e}$0")

    def __build_command(self, is_release: bool) -> None:
        self._compile_cmd = self._base_cmd.copy()
        self._compile_cmd.extend(self.prjcfg.cxx_flags)

        self._compile_cmd.append("-MMD")

        if is_release:
            self._compile_cmd.extend(["-O2", "-DNDEBUG"])
            _log.info("Building in $h1RELEASE$0 mode")
        else:
            self._compile_cmd.extend(["-O0", "-g"])
            _log.info("Building in $h1DEBUG$0 mode")

        for define in self.prjcfg.defines:
            self._compile_cmd.append(f"-D{define}")

        for inc_dir in self.prjcfg.inc_dirs:
            self._compile_cmd.append(f"-I{inc_dir}")

        self._link_cmd = self._base_cmd.copy()

        for lib_dir in self.prjcfg.lib_dirs:
            self._link_cmd.append(f"-L{lib_dir}")

    def __parse_dependency(self, dep_file: Path) -> set[Path]:
        if not dep_file.exists():
            return set()

        try:
            DEPS_READ = dep_file.read_text().split(":", 1)[1]
            DEPS_READ = DEPS_READ.strip().replace("\\ ", " ").split()
            deps: list[Path] = []

            i: int = 0

            while i < len(DEPS_READ):
                path: str = DEPS_READ[i]

                while not Path(path).is_file() and i < len(DEPS_READ):
                    i += 1
                    path += " " + DEPS_READ[i]

                deps.append(Path(path))
                i += 1

            return set(deps)

        except Exception:
            pass

        return set()

    def __needs_compile(self, src: Path, obj: Path, dep_file: Path) -> bool:
        if not obj.exists():
            return True

        if src.stat().st_mtime > obj.stat().st_mtime:
            return True

        for dep in self.__parse_dependency(dep_file):
            if not dep.exists():
                return True

            if dep.stat().st_mtime > obj.stat().st_mtime:
                return True

        return False

    def __collect_srcs(self) -> list[Path]:
        if not self.prjcfg.src_dir.exists():
            _log.err(f"Source directory $dir`{self.prjcfg.src_dir}`$0 not found")
            return []

        srcs = [
            path
            for path in self.prjcfg.src_dir.rglob("*")
            if path.is_file() and path.suffix in SOURCE_EXTENSIONS
        ]

        if not srcs:
            _log.err(f"No source files found in $dir{self.prjcfg.src_dir}$0")
            return []

        return sorted(srcs)

    def __compile_file(self, src: Path) -> Path | None:
        rel_path = src.relative_to(self.prjcfg.src_dir)
        obj = self.prjcfg.out_dir / rel_path.with_suffix(".o")
        dep_file = self.prjcfg.out_dir / rel_path.with_suffix(".d")
        obj.parent.mkdir(parents=True, exist_ok=True)

        if not self.__needs_compile(src, obj, dep_file):
            return obj

        cmd = self._compile_cmd.copy() + ["-c", str(src), "-o", str(obj)]

        _log.info(f"Compiling: $file{src.name}$0")
        result = _cmd.call_cmd(cmd)

        if result is not None:
            _log.err(f"Failed to compile $file{src.name}$0")

        _log.ok(f"Compiled: $file{src.name}$0")
        return obj

    def __compile_all(self) -> list[Path]:
        sources = self.__collect_srcs()
        if not sources:
            return []

        _log.info(
            f"Compiling $B{len(sources)} file(s)$0 with $B{self.prjcfg.parallel} jobs$0"
        )

        objects: list[Path] = []
        failed = False

        with ThreadPoolExecutor(max_workers=self.prjcfg.parallel) as executor:
            futures = {
                executor.submit(self.__compile_file, src): src for src in sources
            }

            for future in as_completed(futures):
                src = futures[future]
                try:
                    obj = future.result()
                    if obj is not None:
                        objects.append(obj)
                    else:
                        failed = True
                except Exception as e:
                    _log.err(f"Exception compiling $file{src.name}$0: {e}")
                    failed = True

        if failed:
            _log.err("Compilation failed", 1)

        return objects

    def _link(self, objs: list[Path]) -> None:
        if not objs:
            _log.err("No object files to link")

        self.prjcfg.target.parent.mkdir(parents=True, exist_ok=True)

        link_cmd = self._link_cmd.copy()

        if self.prjcfg.pch_header is not None:
            link_cmd.extend(["-include", str(self.prjcfg.pch_header)])

        link_cmd.extend([str(obj) for obj in objs])

        for lib in self.prjcfg.libraries:
            link_cmd.append(f"-l{lib}")

        link_cmd.extend(["-o", str(self.prjcfg.target)])

        result = _cmd.call_cmd(link_cmd)
        if not config.is_windows():
            self.prjcfg.target.chmod(self.prjcfg.target.stat().st_mode | 0o111)
        _log.info(f"Linked: $file{self.prjcfg.target}$0")

        if result is not None:
            _log.err(f"Failed to link project $U{self.prjcfg.name}$0: \n\t{result}")

    def run(self, arguments: list[str] | None = None) -> None:
        if arguments is None:
            arguments = []

        if not self.prjcfg.target.exists():
            _log.err(
                f"Target $file`{self.prjcfg.target}`$0 not found. $DPlease build first.$0"
            )

        start_time = time.time()
        _log.info(f"Running $B$U{self.prjcfg.name}$0: $file`{self.prjcfg.target}`$0")

        result = _cmd.call_cmd([str(self.prjcfg.target)] + arguments, hide_output=False)

        if result is not None:
            _log.err(f"Failed to run project $U{self.prjcfg.name}$0: \n\t{result}")

        elapsed = time.time() - start_time
        _log.ok(f"Run successful! $B({elapsed:.2f}s)$0")
