import sys
import platform
from pathlib import Path
from dataclasses import dataclass

VERSION: int = 2
PLATFORM = platform.system().lower()


@dataclass(frozen=True)
class SysInfo:
    os: str
    arch: str
    python_version: str
    version: int


def is_windows() -> bool:
    return PLATFORM == "windows"


def is_linux() -> bool:
    return PLATFORM == "linux"


def is_macos() -> bool:
    return PLATFORM == "darwin"


def is_unix() -> bool:
    return is_linux() or is_macos()


def get_version() -> int:
    return VERSION


def get_architecture() -> str:
    return platform.machine().lower()


def get_system_info() -> SysInfo:
    return SysInfo(
        os=PLATFORM,
        arch=get_architecture(),
        python_version=sys.version.split()[0],
        version=VERSION,
    )


def get_default_parallel_jobs() -> int:
    import os
    try:
        cpu_count = os.cpu_count() or 4
        return max(1, cpu_count)
    except:
        return 4


def is_64bit() -> bool:
    return sys.maxsize > 2**32
