from pathlib import Path

import pycraft
import pycraft.cli
import pycraft.package

PROJ = pycraft.config.ProjectConfig(
    name="opengl_app",
    standard="c++17",
    test_dir=Path("test"),
    inc_dirs=(Path("external/glfw/include"), Path("external/glad/include")),
    lib_dirs=(Path("external/glfw/lib-mingw-w64"),),
    libraries=("glfw3", "opengl32", "gdi32", "winmm", "dwmapi", "ole32", "user32"),
)


def install_packages() -> None:
    pycraft.package.ArchivePackage(
        path=Path("external/glfw"),
        link="https://github.com/glfw/glfw/releases/download/3.4/glfw-3.4.bin.WIN64.zip",
    ).ensure(
        post_mod_fn=lambda path: [
            pycraft.remove_path(dir)
            for dir in path.iterdir()
            if dir.name.startswith("lib") and dir.name != "lib-mingw-w64"
        ]
    )

    pycraft.package.CustomPackage(
        path=Path("external/glad"),
        install_cmd="glad --profile=core --api=gl=3.3 --generator=c --out-path=./external/glad",
    ).ensure(
        pre_mod_fn=lambda _: [
            pycraft.verify_cmd("pip", ensure=True),
            pycraft.verify_cmd("glad", ensure=True),
        ],
        post_mod_fn=lambda path: [
            pycraft.move_path(path / "src" / "glad.c", PROJ.src_dir / "glad.c"),
            pycraft.remove_path(path / "src"),
        ],
    )


if __name__ == "__main__":
    BUILD_CFG = pycraft.cli.get_build_config()
    install_packages()

    with open("compile_flags.txt", "w") as f:
        f.write("\n".join(PROJ.get_flags()))

    pycraft.init(PROJ, BUILD_CFG)
    # pycraft.init(Path("build_cfg.json"), BUILD_CFG)
    pycraft.build_project()
    pycraft.run_project() if BUILD_CFG.is_mode_run() else None
