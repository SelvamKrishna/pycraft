import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from . import _cmd, _log, _deps, _pch, config

SOURCE_EXTENSIONS = {".cpp", ".c", ".cc", ".cxx", ".c++"}


class Project:
    def __init__(
        self, prjcfg: config.ProjectConfig, buildcfg: config.BuildConfig
    ) -> None:
        self.prjcfg: config.ProjectConfig = prjcfg
        self.buildcfg: config.BuildConfig = buildcfg
        self._compile_cmd: list[str] = self.prjcfg.get_flags()

        if self.prjcfg.pch_header is not None:
            self._pch = _pch.PrecompiledHeader(self.prjcfg.pch_header, self.prjcfg)

    def __compile_file(self, src: Path) -> Path | None:
        obj_file = self.prjcfg.out_dir / (src.stem + ".o")
        dep_file = self.prjcfg.out_dir / (src.stem + ".d")

        if not _deps.needs_compile(src, obj_file, dep_file):
            _log.info(f"$file{src}$0: $I(up-to-date)$0")
            return obj_file

        _log.info(f"Compiling: $file{src}$0")

        cmd = [
            *self._compile_cmd,
            "-MMD",
            "-c",
            str(src),
            "-o",
            str(obj_file),
        ]

        if hasattr(self, "_pch") and self._pch:
            cmd.extend(["-include", str(self._pch.path)])

        result = _cmd.call_cmd(cmd)

        if result is not None:
            _log.err(f"Failed to compile $file{src.name}$0")

        _log.ok(f"Compiled: $file{src.name}$0")
        return obj_file

    def __compile_all(self) -> list[Path]:
        sources = [
            path
            for path in self.prjcfg.src_dir.rglob("*")
            if path.is_file() and path.suffix in SOURCE_EXTENSIONS
        ]

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

        if failed:
            _log.err("Compilation failed", 1)

        return objects

    def __link(self, objs: list[Path]) -> None:
        if not objs:
            _log.err("No object files to link")

        link_cmd = self.prjcfg.get_link_flags(objs)
        result = _cmd.call_cmd(link_cmd)

        if not config.is_windows():
            self.prjcfg.target.chmod(self.prjcfg.target.stat().st_mode | 0o111)
        _log.info(f"Linked: $file{self.prjcfg.target}$0")

        if result is not None:
            _log.err(f"Failed to link project $U{self.prjcfg.name}$0: \n\t{result}")

    def build(self) -> None:
        if self.buildcfg.is_mode_run():
            return

        self.prjcfg.out_dir.mkdir(parents=True, exist_ok=True)

        if hasattr(self, "_pch"):
            self._pch.build()

        start_time = time.time()
        objects = self.__compile_all()

        _log.info(f"Building project $U$B{self.prjcfg.name}$0")

        if not objects:
            _log.err("No object files generated")

        self.__link(objects)
        elapsed = time.time() - start_time

        _log.ok(f"Build successful! $B({elapsed:.2f}s)$0")

        if self.buildcfg.should_run_after:
            self.run(self.buildcfg.run_args)

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
