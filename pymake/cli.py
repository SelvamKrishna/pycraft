import sys

from . import _log, config


def get_build_config() -> config.BuildConfig:
    if len(sys.argv) <= 1:
        print_help()
        sys.exit(0)

    command = sys.argv[1].strip().lower()

    match command:
        case "debug":
            mode = config.BuildMode.DEBUG
        case "release":
            mode = config.BuildMode.RELEASE
        case "run":
            mode = config.BuildMode.RUN
        case "--version" | "-v":
            _log.print_version()
            sys.exit(0)
        case _:
            print_help()
            sys.exit(0)

    return config.BuildConfig(
        mode,
        "--clean" in sys.argv or "-c" in sys.argv,
        "--run" in sys.argv or "-r" in sys.argv,
        sys.argv[2:] if mode == config.BuildMode.RUN else None,
    )


def print_help() -> None:
    _log.log("$D" + "=" * 80)
    _log.print_version()
    _log.log("$D" + "=" * 80)
    _log.log("$h1Usage:$0")
    _log.log(f"  {sys.argv[0]} $B<command>$0 $D[options]$0")
    _log.log("")
    _log.log("$h1Commands:$0")
    _log.log("  $Bdebug$0          Build with debug symbols (-O0 -g)")
    _log.log("  $Brelease$0        Build optimized for release (-O2 -DNDEBUG)")
    _log.log("  $Brun$0            Run the built executable")
    _log.log("")
    _log.log("$h1Options:$0")
    _log.log("  $B-c, --clean$0    Clean before building")
    _log.log("  $B-r, --run$0      Run after building")
    _log.log("  $B-q, --quiet$0    Disable verbose output messages")
    _log.log("  $B-h, --help$0     Show this help message")
    _log.log("  $B--version$0      Show version information")
    _log.log("")
    _log.log("$D" + "=" * 80)
