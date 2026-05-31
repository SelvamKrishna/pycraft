# TODO

## TEST

- [x] **PCH support :**
  - Some compiler's expect `-include header` as a flag to precompile header

## BUGS

- [x] **Dependency Parsing :**
  - Under `Project().__parse_dependency()` line `content[1].strip().split()` will fail
  - Path's like _C:\My Project\include\foo.h_ will not work due to white spaces

## FEAT

- [x] **Generating `compile_commands.json` :**
  - Used by `clangd` and `clang-tidy` for code completion and linting

- [ ] **Object file hashing :**
  - Store **build flags** used for compiling object files
  - Hash _compiler_, _cxx-flags_, _defines_, _includes_, _libraries_, _pch_ flags
  - When **hashes don't match, recompile** object file

- [ ] **Static and Shared library building support :**
  - `ProjectConfig()` should also take output type as an argument
  - **Shared libraries :** `*.so` or `*.dll`
  - **Static libraries :** `*.a` or `*.lib`

- [ ] **File watching :**
  - Detect changes in source files and recompile them automatically
  - `pymake build.py watch` command will start **Watcher mode**
  - **Watcher mode** runs in background and recompiles changed files as they are saved
