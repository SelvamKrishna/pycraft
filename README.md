# PyMake v1 - README

## What is PyMake?

PyMake is a _simple_, _lightweight_ utility for **C / C++** build systems.

## Features

- **Simple configuration** - Define your project in Python
- **Parallel compilation** - Builds multiple files simultaneously
- **Colored output** - Clear, readable build logs
- **Zero dependencies** - Uses only Python standard library
- **Smart rebuilding** - Only recompiles changed files

## Quick Start

1. **Add `pymake.py` into your current working directory**

```txt
your-project/
|-source/
|-include/
|-.../
|-pymake.py
```

2. **Create a Python file `build.py`**

```python
from pathlib import Path
import pymake

PROJ_CFG = pymake.ProjectConfig(
    name="pymake_test",
    src_dir=Path.cwd() / "source",# your source directory
    out_dir=Path.cwd() / "build", # your output directory
    # you can also specify includes, library, defines etc.
)

if __name__ == "__main__":
    assert pymake.VERSION == 1

    BUILD_CFG = pymake.CLI.get_build_config() # gets build config from environment arguments
    # BUILD_CFG = pymake.BuildConfig(mode=BUILD_CFG.mode, should_run_after=True) # manual build config

    pymake.init(verbose=BUILD_CFG.is_verbose) # for process logging

    proj = pymake.Project(PROJ_CFG)
    proj.build(BUILD_CFG)

    if BUILD_CFG.should_run():
        proj.run(BUILD_CFG.run_args)
```

3. **Build and Run**

```shell
python build.py debug -r -c -v
```

## Requirements

- Python 3.7+
- Compiler (gcc/g++/clang++)
