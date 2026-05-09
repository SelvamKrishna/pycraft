from pathlib import Path

import pymake

PROJ_CFG = pymake.ProjectConfig(
    name="pymake_test",
    src_dir=Path.cwd() / "source",
    out_dir=Path.cwd() / "build",
)

if __name__ == "__main__":
    BUILD_CFG = pymake.CLI.get_build_config()

    pymake.init(is_verbose=BUILD_CFG.is_verbose)
    assert pymake.get_version() == 2

    pymake.Package(
        path=Path("external/raylib"),
        kind=pymake.PackageKind.GIT,
        link="https://github.com/raysan5/raylib.git",
    ).ensure()


    proj = pymake.Project(PROJ_CFG)
    proj.build(BUILD_CFG)

    if BUILD_CFG.should_run():
        proj.run(BUILD_CFG.run_args)
