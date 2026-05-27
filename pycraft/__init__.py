import shutil
import sys
from pathlib import Path

from . import _core, _log, _cmd, config

s_proj: _core.Project | None = None


def init(projcfg: config.ProjectConfig | Path, buildcfg: config.BuildConfig) -> None:
    global s_proj

    if isinstance(projcfg, Path):
        if not projcfg.exists():
            _log.err(f"Config file $dir`{projcfg}`$0 not found")

        match projcfg.suffix:
            case ".json":
                projcfg = config.ProjectConfig.load_from_json(projcfg)
            case _:
                _log.err(f"Unknown config file type: $file`{projcfg}`$0")

    s_proj = _core.Project(projcfg, buildcfg)
    _log.g_quiet = "--quiet" in sys.argv or "-q" in sys.argv


def build_project() -> None:
    global s_proj

    if s_proj is None:
        _log.err("$BPyMake$0 not initialized")
    else:
        s_proj.build()


def run_project() -> None:
    global s_proj

    if s_proj is None:
        _log.err("$BPyMake$0 not initialized")
    else:
        s_proj.run()


def remove_path(path: Path) -> None:
    if not path.exists():
        return

    if path.is_file():
        path.unlink()

    elif path.is_dir():
        path.rmdir() if len(list(path.iterdir())) == 0 else shutil.rmtree(path)

    _log.info(f"Removed $file`{path}`$0")


def copy_path(src: Path, dst: Path) -> None:
    _log.info(f"Copying $file`{src}`$0 to $file`{dst}`$0...")

    if not src.exists():
        _log.err(f"File $file`{src}`$0 does not exist")

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst) if src.is_file() else shutil.copytree(src, dst)


def move_path(src: Path, dst: Path) -> None:
    _log.info(f"Moving $file`{src}`$0 to $file`{dst}`$0...")

    if not src.exists():
        _log.err(f"File $file`{src}`$0 does not exist")

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, dst)


def run_cmd(cmd: list[str] | str, hide_output: bool = False) -> None:
    if isinstance(cmd, str):
        _cmd.call_cmd_s(cmd, hide_output)
    else:
        _cmd.call_cmd(cmd, hide_output)


def verify_cmd(cmd: str, ensure: bool = False) -> bool:
    _log.info(f"Checking if cli command $B{cmd}$0 is available...")
    result = _cmd.call_cmd_r([cmd, "--version"]) or ""

    if "not found" in result.lower():
        (_log.err if ensure else _log.warn)(result)
        return False
    else:
        _log.ok(f"Command found $B{cmd}$0")
        return True


if __name__ == "__main__":
    _log.print_version()
