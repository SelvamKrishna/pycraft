import sys
from pathlib import Path

import pycraft
import pycraft.cli
import pycraft.package

if pycraft.config.is_windows():
    GLFW_LIB_DIR = Path("external/glfw/lib-mingw-w64")
    GLFW_LIB_NAME = "glfw3"
    ADDITIONAL_LIBS = ("opengl32", "gdi32", "winmm", "dwmapi", "ole32", "user32")

    pycraft.package.ArchivePackage(
        path=Path("external/glfw"),
        link="https://github.com/glfw/glfw/releases/download/3.4/glfw-3.4.bin.WIN64.zip",
    ).ensure(
        mod_fn=lambda path: [
            pycraft.remove_path(dir)
            for dir in path.iterdir()
            if dir.name.startswith("lib") and dir.name != "lib-mingw-w64"
        ]
    )

else:
    raise OSError(f"Unsupported platform: {sys.platform}")


PROJ = pycraft.config.ProjectConfig(
    name="opengl_app",
    standard="c++17",
    src_dir=Path("source"),
    inc_dirs=(
        Path("external/glfw/include"),
        Path("external/glad/include"),
    ),
    lib_dirs=(GLFW_LIB_DIR,),
    libraries=(GLFW_LIB_NAME,) + ADDITIONAL_LIBS,
)

pycraft.package.CustomPackage(
    path=Path("external/glad"),
    install_cmd="glad --profile=core --api=gl=3.3 --generator=c --out-path=./external/glad",
).ensure(
    pre_mod_fn=lambda _: [
        pycraft.verify_cmd("pip", ensure=True),
        pycraft.verify_cmd("glad", ensure=True),
    ],
    mod_fn=lambda path: [
        pycraft.move_path(path / "src" / "glad.c", PROJ.src_dir / "glad.c"),
        pycraft.remove_path(path / "src"),
    ],
)


BUILD_CFG = pycraft.cli.get_build_config()

with open("compile_flags.txt", "w") as f:
    f.write("\n".join(PROJ.get_flags()))


if __name__ == "__main__":
    pycraft.init(PROJ, BUILD_CFG)
    pycraft.build_project()
    pycraft.run_project() if BUILD_CFG.is_mode_run() else None
