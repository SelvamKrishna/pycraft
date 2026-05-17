import sys
import shutil
from pathlib import Path

import pymake
import pymake.cli
import pymake.package
import pymake._cmd

if pymake.config.is_windows():
    GLFW_LIB_DIR = Path("external/glfw/lib-mingw-w64")
    GLFW_LIB_NAME = "glfw3"
    ADDITIONAL_LIBS = (
        "opengl32", "gdi32", "winmm", "dwmapi", "ole32", "user32")

    pymake.package.ArchivePackage(
        path=Path("external/glfw"),
        link="https://github.com/glfw/glfw/releases/download/3.4/glfw-3.4.bin.WIN64.zip"
    ).ensure(
        lambda path: [
            shutil.rmtree(dir)
            for dir in path.iterdir()
            if dir.name.startswith("lib") and dir.name != "lib-mingw-w64"
        ]
    )

elif pymake.config.is_linux():
    GLFW_LIB_DIR = Path("external/glfw/lib-linux")
    GLFW_LIB_NAME = "glfw"
    ADDITIONAL_LIBS = (
        "GL", "X11", "Xrandr", "Xi", "Xxf86vm", "Xcursor", "Xinerama", "pthread", "dl", "m",)
    GLFW_TAR_NAME = "glfw-3.4.tar.gz"
    GLFW_URL = "https://github.com/glfw/glfw/releases/download/3.4/glfw-3.4.tar.gz"

    def build_glfw(package_path: Path) -> None:
        archive = package_path / "glfw-3.4.tar.gz"
        if archive.exists():
            pymake._cmd.call_cmd(["tar", "xzf", str(archive)], check=True)

        source_dir = package_path / "glfw-3.4"
        build_dir = source_dir / "build"

        lib_dir = package_path / "lib-linux"
        lib_dir.mkdir(exist_ok=True)

        build_dir.mkdir(exist_ok=True)
        pymake._cmd.call_cmd(
            ["cmake", "..", f"-DCMAKE_INSTALL_PREFIX={package_path.absolute()}", "-DBUILD_SHARED_LIBS=OFF"],
            check=True)
        pymake._cmd.call_cmd(["make", "-j4"], check=True)

        for lib in build_dir.glob("src/libglfw*.a"):
            shutil.copy(lib, lib_dir)

    pymake.package.CustomPackage(
        path=Path("external/glfw"),
        install_cmd=f"wget {GLFW_URL} -O external/glfw/glfw-3.4.tar.gz"
    ).ensure(build_glfw)

else:
    raise OSError(f"Unsupported platform: {sys.platform}")


PROJ = pymake.config.ProjectConfig(
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

pymake.package.CustomPackage(
    path=Path("external/glad"),
    install_cmd="glad --profile=core --api=gl=3.3 --generator=c --out-path=./external/glad"
).ensure(lambda path: (path / "src/glad.c").move("source/glad.c") and (path / "src").rmdir())

BUILD_CFG = pymake.cli.get_build_config()

if __name__ == "__main__":
    pymake.init(PROJ, BUILD_CFG)
    pymake.build_project()
