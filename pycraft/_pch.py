from pathlib import Path

from . import _cmd, _log, config


HEADER_EXTENSIONS = {".hpp", ".h", ".hh", ".hxx", ".h++"}


class PrecompiledHeader:
    def __init__(self, path: Path, prjcfg: config.ProjectConfig) -> None:
        self._path = path
        self._output = prjcfg.out_dir / (path.name + ".gch")
        self._cmd = prjcfg.get_flags()
        self._lang = prjcfg.get_lang()

        if config.is_windows() and prjcfg.cc in (config.Compiler.MSVC,):
            self._output = self._output.with_suffix(".pch")

    def __post_init__(self) -> None:
        if not self._path.exists():
            _log.err(f"Precompiled header not found: {self._path}")
            raise FileNotFoundError

        if not self._path.is_file() or self._path.suffix not in HEADER_EXTENSIONS:
            _log.err(f"Invalid precompiled header: {self._path}")
            raise ValueError

    def get_output(self) -> Path:
        return self._output

    def __requires_compile(self) -> bool:
        return True

    def build(self) -> None:
        if not self.__requires_compile():
            _log.info(f"Using cached PCH: $file{str(self._path)}$0")
            return

        _log.info(f"Generating PCH: $file{str(self._path)}$0")

        result = _cmd.call_cmd(
            [
                *self._cmd,
                "-x",
                self._lang,
                "-MMD",
                "-c",
                str(self._path),
                "-o",
                str(self._output),
            ]
        )

        if result is not None:
            _log.err(f"Failed to generate precompiled header: \n\t{result}")

        _log.ok(f"Generated precompiled header: $file{self._path.name}$0")
