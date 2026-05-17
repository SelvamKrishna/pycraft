from ._core import *
from . import _log


s_proj: Project | None = None


def init(projcfg: config.ProjectConfig, buildcfg: config.BuildConfig) -> None:
    global s_proj
    s_proj = Project(projcfg, buildcfg)

    _log.g_quiet = "--quiet" in sys.argv or "-q" in sys.argv


def build_project() -> None:
    global s_proj

    if s_proj is None:
        _log.err("$BPyMake$0 not initialized")
    else:
        s_proj.build()


def run_project() -> None:
    global s_proj

    if s_proj is None:
        _log.err("$BPyMake$0 not initialized")
    else:
        s_proj.run()


if __name__ == "__main__":
    from . import _log
    _log.print_version()
