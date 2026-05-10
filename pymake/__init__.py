from . import _log
from ._cfg import *
from ._core import *


def init(silent: bool = False) -> None:
    _log.g_silent = silent


if __name__ == "__main__":
    _log.print_version()
