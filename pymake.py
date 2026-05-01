import subprocess
import colorama
from pathlib import Path

import pymake_cfg as cfg


def _color_print(color: str, text: str) -> None:
    print(f"{color}{text}{colorama.Style.RESET_ALL}")


def _run_cmd(cmd: str) -> None:
    _color_print(colorama.Fore.BLACK, f" > {cmd}")

    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        _color_print(colorama.Fore.RED, f" (X)\n\t{e}")


def _collect_sources() -> list[str]:
    files: list[str] = []

    for ext in ["c", "cc", "cpp", "c++", "cxx"]:
        for file in Path(cfg.SRC_DIR).glob(f"**/*.{ext}"):
            files.append(str(file))

    return files


TARGET = Path(cfg.OUT_DIR) / cfg.NAME
SOURCES = _collect_sources()


def _compile() -> None:
    if not Path(cfg.OUT_DIR).exists():
        Path(cfg.OUT_DIR).mkdir()

    flags = f"-std=c++{cfg.VER}"
    includes = ' '.join(f"-I{i}" for i in cfg.INCLUDES)
    defines = ' '.join(f"-D{d}" for d in cfg.DEFINES)
    links = ' '.join(f"-l{l}" for l in cfg.LINKS)

    _run_cmd(f"{cfg.CXX} {flags} {includes} {defines} -o {TARGET} {' '.join(SOURCES)} {links}")


colorama.init(autoreset=True)


def main() -> None:
    _compile()
    _run_cmd(f"{TARGET}")


if __name__ == "__main__":
    main()
