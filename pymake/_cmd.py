import subprocess

from . import _log


def call_cmd(cmd: list[str], check: bool = True, capture_output: bool = False) -> None:
    _log._cmd(cmd)

    try:
        subprocess.run(cmd, check=check, capture_output=capture_output)
    except FileNotFoundError as _:
        _log.exit_or_continue(f"Command not found: $B{cmd[0]}$0")
    except PermissionError as e:
        _log.err(f"Permission denied: {e.filename}", err_code=126)
    except subprocess.CalledProcessError as e:
        _log.err(f"Command failed: {' '.join(e.cmd)}")
    except Exception as e:
        raise e


def call_cmd_s(cmd: str, check: bool = True) -> None:
    return call_cmd(cmd.split(), check)
