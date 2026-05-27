import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import _cmd, _log, config

SOURCE_EXTENSIONS = {".cpp", ".c", ".cc", ".cxx", ".c++"}


class Project:
    def __init__(
        self, prjcfg: config.ProjectConfig, buildcfg: config.BuildConfig
    ) -> None:
        self.prjcfg = prjcfg
        self.buildcfg: config.BuildConfig = buildcfg
        self._compile_cmd: list[str] = []
        self._link_cmd: list[str] = []
        self._pch_path: Path | None = None
        self._base_cmd: list[str] = [
            self.prjcfg.cc.value,
            f"-std={self.prjcfg.standard}",
        ]

    def build(self) -> None:
        if self.buildcfg.is_mode_run():
            return

        if self.buildcfg.should_clean:
            self.__clean()

        _log.info(f"Building project $U$B{self.prjcfg.name}$0")

        self.__build_command(self.buildcfg.is_mode_release())
        self.__pch()

        start_time = time.time()
        objects = self.__compile_all()

        if not objects:
            _log.err("No object files generated")

        self._link(objects)
        elapsed = time.time() - start_time

        _log.ok(f"Build successful! $B({elapsed:.2f}s)$0")

        if self.buildcfg.should_run_after:
            self.run(self.buildcfg.run_args)

    def __clean(self) -> None:
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

    def __pch(self) -> None:
        if self.prjcfg.pch_header is None or not self.prjcfg.pch_header.exists():
            return

        include_flag = f"-include{self.prjcfg.pch_header.stem}"
        pch_output = (
            self.prjcfg.out_dir
            / f"{self.prjcfg.pch_header.stem}.{'pch' if config.is_windows() else 'gch'}"
        )

        cmd = self._compile_cmd.copy() + [
            "-c",
            str(self.prjcfg.pch_header),
            "-o",
            str(pch_output),
        ]

        result = _cmd.call_cmd(cmd)
        self._pch_path = pch_output
        _log.info(f"Precompiled header: $file{pch_output}$0")
        self._compile_cmd.append(include_flag)

        if result is not None:
            _log.warn(
                f"Failed to precompile header: \n\t{result}, continuing without PCH"
            )
            self._pch_path = None
        else:
            _log.ok("Precompiled header generated")

    def __parse_dependency(self, dep_file: Path) -> set[Path]:
        if not dep_file.exists():
            return set()

        try:
            content = dep_file.read_text().split(":", 1)
            if len(content) < 2:
                return set()

            return set(Path(dep) for dep in content[1].strip().split())

        except Exception:
            pass

        return set()

    def __needs_compile(self, src: Path, obj: Path, dep_file: Path) -> bool:
        if not obj.exists():
            return True

        if src.stat().st_mtime > obj.stat().st_mtime:
            return True

        for dep in self.__parse_dependency(dep_file):
            if Path(dep).exists() and Path(dep).stat().st_mtime > obj.stat().st_mtime:
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
        compiled_count = 0
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
                        compiled_count += 1
                    else:
                        failed = True
                except Exception as e:
                    _log.err(f"Exception compiling $file{src.name}$0: {e}")
                    failed = True

        if failed:
            _log.err("Compilation failed", 1)

        _log.ok(f"Successfully compiled $B{compiled_count}/{len(sources)}$0 files")

        return objects

    def _link(self, objs: list[Path]) -> None:
        if not objs:
            _log.err("No object files to link")

        self.prjcfg.target.parent.mkdir(parents=True, exist_ok=True)

        link_cmd = self._link_cmd.copy()
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

        result = _cmd.call_cmd([str(self.prjcfg.target)] + arguments)

        if result is not None:
            _log.err(f"Failed to run project $U{self.prjcfg.name}$0: \n\t{result}")

        elapsed = time.time() - start_time
        _log.ok(f"Run successful! $B({elapsed:.2f}s)$0")
