from pathlib import Path


def get_dependencies(dep_file: Path) -> set[Path]:
    if not dep_file.exists():
        return set()

    try:
        content = dep_file.read_text()

        colon_pos = content.find(":")
        if colon_pos == -1:
            return set()

        deps_part = content[colon_pos + 1 :].strip()
        deps_part = deps_part.replace("\\\n", " ").replace("\n", " ")

        deps = []
        current = []
        i = 0
        length = len(deps_part)

        while i < length:
            ch = deps_part[i]

            if ch == "\\" and i + 1 < length and deps_part[i + 1] == " ":
                current.append(" ")
                i += 2
                continue
            elif ch == " ":
                if current:
                    deps.append("".join(current))
                    current = []
                i += 1
            else:
                current.append(ch)
                i += 1

        if current:
            deps.append("".join(current))

        return set(
            Path(dep) for dep in deps if Path(dep).exists() and Path(dep).is_file()
        )

    except Exception:
        return set()


def needs_compile(src_file: Path, obj_file: Path, dep_file: Path) -> bool:
    if not obj_file.exists():
        return True

    if src_file.stat().st_mtime > obj_file.stat().st_mtime:
        return True

    if not dep_file.exists():
        return True

    if dep_file.stat().st_mtime > obj_file.stat().st_mtime:
        return True

    for dep in get_dependencies(dep_file):
        if not dep.exists():
            return True

        if dep.stat().st_mtime > obj_file.stat().st_mtime:
            return True

    return False
