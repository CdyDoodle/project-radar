"""Small, comment-preserving edits to config.toml.

The config is heavily commented on purpose, and those comments are half its
value. A TOML round-trip would drop them, so edits are line-based and limited
to the two shapes radar needs: `key = value` in a section, and appending to a
string array.
"""
from __future__ import annotations

import re
from pathlib import Path

_HEADER = re.compile(r"^\s*\[([^\]]+)\]\s*(#.*)?$")


def _section_bounds(lines: list[str], section: str) -> tuple[int, int]:
    start = None
    for i, line in enumerate(lines):
        m = _HEADER.match(line)
        if m and m.group(1).strip() == section:
            start = i
            continue
        if start is not None and m:
            return start, i
    if start is None:
        raise KeyError(f"no [{section}] section in config.toml")
    return start, len(lines)


def _key_re(key: str) -> re.Pattern:
    quoted = re.escape(f'"{key}"')
    bare = re.escape(key)
    return re.compile(rf'^(\s*)({quoted}|{bare})(\s*=\s*)([^#\n]*?)(\s*(#.*)?)$')


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".") if value != int(value) else f"{value:.1f}"
    if isinstance(value, int):
        return str(value)
    return '"' + str(value).replace('"', '\\"') + '"'


def set_values(path: Path, section: str, values: dict, quote_keys: bool = False) -> list[str]:
    """Set keys in one section; add missing ones at its end. Returns changes made."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = _section_bounds(lines, section)
    changes = []
    pending = dict(values)
    for i in range(start + 1, end):
        for key in list(pending):
            m = _key_re(key).match(lines[i])
            if m:
                new = _fmt(pending.pop(key))
                if m.group(4).strip() != new:
                    changes.append(f"[{section}] {key}: {m.group(4).strip()} -> {new}")
                    lines[i] = f"{m.group(1)}{m.group(2)}{m.group(3)}{new}{m.group(5)}"
    if pending:
        # after the last non-blank line of the section
        insert_at = end
        while insert_at - 1 > start and not lines[insert_at - 1].strip():
            insert_at -= 1
        added = []
        for key, value in pending.items():
            name = f'"{key}"' if quote_keys or not re.fullmatch(r"[A-Za-z0-9_-]+", key) else key
            added.append(f"{name} = {_fmt(value)}")
            changes.append(f"[{section}] {key}: added = {_fmt(value)}")
        lines[insert_at:insert_at] = added
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changes


def append_to_array(path: Path, section: str, key: str, items: list[str]) -> list[str]:
    """Append strings to a multi-line string array, skipping ones already there."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = _section_bounds(lines, section)
    open_at = next((i for i in range(start + 1, end)
                    if re.match(rf"^\s*{re.escape(key)}\s*=\s*\[", lines[i])), None)
    if open_at is None:
        raise KeyError(f"no {key} = [...] in [{section}]")
    close_at = next(i for i in range(open_at, len(lines)) if lines[i].strip().startswith("]")
                    or lines[i].rstrip().endswith("]"))
    body = "\n".join(lines[open_at:close_at + 1])
    present = {s.lower() for s in re.findall(r'"([^"]+)"', body)}
    new = [x for x in items if x.lower() not in present]
    if not new:
        return []
    if close_at == open_at:                      # one-line array: users = ["a", "b"]
        lines[open_at] = lines[open_at].rstrip()[:-1].rstrip().rstrip(",")
        sep = ", " if lines[open_at].rstrip().endswith('"') else ""
        lines[open_at] += sep + ", ".join(f'"{x}"' for x in new) + "]"
    else:
        indent = re.match(r"^(\s*)", lines[close_at - 1]).group(1) or "  "
        lines[close_at:close_at] = [f'{indent}"{x}",' for x in new]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [f"[{section}] {key}: added {x}" for x in new]
