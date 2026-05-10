from pathlib import Path

import pymake
import pymake.cli
import pymake.pck

PROJ_CFG = pymake.ProjectConfig(
    name="pymake_test",
    src_dir=Path.cwd() / "source",
    out_dir=Path.cwd() / "build",
)

if __name__ == "__main__":
    BUILD_CFG = pymake.cli.get_build_config()

    pymake.init(silent=not BUILD_CFG.is_verbose)
    assert pymake._cfg.get_version() == 2

    pymake.pck.Package(
        path=Path("external/raylib"),
        kind=pymake.pck.PackageKind.GIT,
        link="https://github.com/raysan5/raylib.git",
    ).ensure()

    proj = pymake.Project(PROJ_CFG)
    proj.build(BUILD_CFG)

    if BUILD_CFG.should_run():
        proj.run(BUILD_CFG.run_args)
