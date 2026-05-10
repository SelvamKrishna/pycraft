import subprocess
from . import _log


def call_cmd(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    try:
        if capture:
            result = subprocess.run(
                cmd, check=check, capture_output=True, text=True)
            if result.returncode != 0 and result.stderr:
                _log.err(result.stderr.strip(), exit=False)
            return result
        else:
            return subprocess.run(cmd, check=check)
    except FileNotFoundError:
        _log.err(f"Command not found: {cmd[0]}")
        raise
    except subprocess.CalledProcessError as e:
        _log.err(
            f"Command failed with exit code {e.returncode}: {' '.join(cmd)}", exit=False)
        raise
    except Exception as e:
        _log.err(f"Unexpected error: {e}")
        raise
