import sys

from . import _cfg

g_silent: bool = False

_COLOR_ENABLED = sys.stdout.isatty()

_LUT: tuple[tuple[str, str], ...] = (
    ("$0", "\033[0m" if _COLOR_ENABLED else ""),
    ("$B", "\033[1m" if _COLOR_ENABLED else ""),
    ("$D", "\033[2m" if _COLOR_ENABLED else ""),
    ("$I", "\033[3m" if _COLOR_ENABLED else ""),
    ("$U", "\033[4m" if _COLOR_ENABLED else ""),

    ("$link", "\033[1;4m" if _COLOR_ENABLED else ""),
    ("$file", "\033[1;3m" if _COLOR_ENABLED else ""),
    ("$dir", "\033[2;3m" if _COLOR_ENABLED else ""),

    ("$h1", "\033[4;34m" if _COLOR_ENABLED else ""),
)

_ERROR = f"\033[1;31m[ERROR:%d]\033[0m" if _COLOR_ENABLED else "[ERROR:%d]"
_WARNING = f"\033[1;33m[WARNING]\033[0m" if _COLOR_ENABLED else "[WARNING]"
_INFO = f"\033[1;32m[INFO]\033[0m" if _COLOR_ENABLED else "[INFO]"


def _format_text(text: str) -> str:
    if not _COLOR_ENABLED:
        for code, _ in _LUT:
            text = text.replace(code, "")
    else:
        for code, color in _LUT:
            text = text.replace(code, color)

    return text


def log(*args, **kwargs) -> None:
    message = " ".join(str(arg) for arg in args)
    print(_format_text(message), **kwargs)
    print("\033[0m", end="", flush=True)


def print_version() -> None:
    log(f"$BPyMake v{_cfg.VERSION}$0", end="\n")


def err(message: str, err_code: int = 1, exit: bool = True) -> None:
    log(f"{_ERROR % err_code}: {message}")
    if exit:
        sys.exit(err_code)


def warn(message: str) -> None:
    if not g_silent:
        log(f"{_WARNING}: {message}")


def info(message: str) -> None:
    if not g_silent:
        log(f"{_INFO}: {message}")
