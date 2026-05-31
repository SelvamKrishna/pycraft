from pathlib import Path

from . import _cmd, _log, _deps, config


HEADER_EXTENSIONS = {".hpp", ".h", ".hh", ".hxx", ".h++"}


class PrecompiledHeader:
    def __init__(self, path: Path, prjcfg: config.ProjectConfig) -> None:
        self.path = path
        self._output = prjcfg.out_dir / (str(path.stem) + (".gch"))
        self._cmd = prjcfg.get_flags()
        self._lang = prjcfg.lang

        if config.is_windows() and prjcfg.cc in (config.Compiler.MSVC,):
            self._output = self._output.with_suffix(".pch")

        if not self.path.exists():
            _log.err(f"Precompiled header not found: {self.path}")
            raise FileNotFoundError

        if not self.path.is_file() or self.path.suffix not in HEADER_EXTENSIONS:
            _log.err(f"Invalid precompiled header: {self.path}")
            raise ValueError

        self._output.parent.mkdir(parents=True, exist_ok=True)

    def get_output(self) -> Path:
        return self._output

    def build(self) -> None:
        if not _deps.needs_compile(
            self.path, self._output, self._output.with_suffix(".d")
        ):
            _log.info(f"$file{str(self.path)}$0: $I(up-to-date)$0")
            return

        for dep_file in self._output.parent.iterdir():
            if not dep_file.is_file() or dep_file.suffix != ".d":
                continue

            if self.path in _deps.get_dependencies(dep_file):
                dep_file.unlink()

                if dep_file.with_suffix(".o").exists():
                    dep_file.with_suffix(".o").unlink()

        _log.info(f"Generating PCH: $file{str(self.path)}$0")

        result = _cmd.call_cmd(
            [
                *self._cmd,
                "-x",
                f"{self._lang.value}-header",
                "-MMD",
                "-c",
                str(self.path),
                "-o",
                str(self._output),
            ]
        )

        if result is not None:
            _log.err(f"Failed to generate precompiled header: \n\t{result}")

        _log.ok(f"Generated precompiled header: $file{self.path.name}$0")
