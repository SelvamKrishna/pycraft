import subprocess

from . import _log


def call_cmd_r(cmd: list[str]) -> str | None:
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        return "$BFailed:$0 %s" % e.stderr
    except KeyboardInterrupt:
        return "$BProcess Interrupted [Ctrl-C]$0"
    except FileNotFoundError as _:
        return "$BNot found:$0 %s" % cmd[0]
    except PermissionError as e:
        return "$BPermission:$0 %s" % e.filename
    except Exception as e:
        return "$BUnknown:$0 %s" % str(e)

    return None


def call_cmd(cmd: list[str]) -> None:
    _log._cmd(cmd)
    result: str | None = call_cmd_r(cmd)

    if result is None:
        return

    if "ctrl-c" in result.lower():
        _log.warn(result)
        return

    _log.err(f"{result}, exiting...")


def call_cmd_s(cmd: str) -> None:
    return call_cmd(cmd.split())
