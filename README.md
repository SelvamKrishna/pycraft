# PyCraft v2 - README

## What is PyCraft?

PyCraft is a _simple_, _lightweight_ utility for **C / C++** build systems.

## Features

- **Simple configuration** - Configure your project in _Python_
- **Parallel compilation** - Builds multiple files simultaneously
- **Smart rebuilding** - Recompiles only changed files
- **Package manager** - Install and manage external libraries

## Quick Start

1. **Add `pycraft` into your current working directory**

```shell
git clone https://github.com/SelvamKrishna/pycraft.git pycraft
```

```txt
your-project/
|- source/
|- include/
|- .../
|- pycraft/
```

2. **Create a Python file `build.py`**

```python
from pathlib import Path

import pycraft
import pycraft.cli

PROJ = pycraft.config.ProjectConfig(
    name="example",
    cc=pycraft.config.Compiler.GXX,
    standard="c++23",
    src_dir=Path("source"),  # path to source files
    out_dir=Path("build"),  # path to build files
    inc_dirs=(Path("include"),),  # paths to include directories
    lib_dirs=(Path("external"),),  # paths to library directories
    # ... more project configuration
)

if __name__ == "__main__":
    assert pycraft.config.get_version() == 2

    # get build configuration from command line
    BUILD_CFG = pycraft.cli.get_build_config()

    pycraft.init(PROJ, BUILD_CFG)
    pycraft.build_project()
    pycraft.run_project() if BUILD_CFG.is_mode_run() else None
```

3. **Build and Run**

```shell
python build.py debug -r -c
```

## Requirements

- Python 3.7+
- Compiler _(any supported by PyCraft)_
