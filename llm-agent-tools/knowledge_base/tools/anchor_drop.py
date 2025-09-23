#!/usr/bin/env python3
"""
Drop a memory anchor:
- Inserts a CLAUDE_ANCHOR comment in the code with UUID key
- Appends entry in .claude/memory_anchors/anchors.json
"""

import json
import pathlib
import time
import uuid

LANG_PREFIX = {
    ".py": "#",
    ".js": "//",
    ".ts": "//",
    ".go": "//",
    ".c": "//",
    ".cpp": "//",
    ".java": "//",
    ".rs": "//",
    ".zig": "//",
    ".sql": "--",
    ".html": "<!--",
    ".htm": "<!--",
}
LANG_SUFFIX = {".html": " -->", ".htm": " -->"}


def drop_anchor(file_path, line_num, desc, kind="line"):
    root = pathlib.Path(".claude/memory_anchors")
    root.mkdir(parents=True, exist_ok=True)
    anchors_file = root / "anchors.json"

    # Load or init template
    data = {
        "version": 1,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "anchors": [],
    }
    if anchors_file.exists():
        with open(anchors_file, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print("Invalid anchors.json; reinitializing.")

    # Generate key
    key = str(uuid.uuid4())[:8]

    # New entry
    entry = {
        "key": key,
        "path": file_path,
        "line": line_num,
        "kind": kind,
        "description": desc,
        "status": "active",
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    data["anchors"].append(entry)
    data["generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Insert comment
    p = pathlib.Path(file_path)
    if not p.exists():
        print(f"File {file_path} not found.")
        return

    with open(p, "r") as f:
        text = f.readlines()

    if line_num < 1 or line_num > len(text) + 1:
        print(f"Invalid line {line_num} for file with {len(text)} lines.")
        return

    ext = p.suffix.lower()
    pre = LANG_PREFIX.get(ext, "//")
    post = LANG_SUFFIX.get(ext, "")
    comment = f"{pre} CLAUDE_ANCHOR[key={key}] {desc}{post}\n"
    text.insert(line_num - 1, comment)

    with open(p, "w") as f:
        f.writelines(text)

    # Write JSON
    with open(anchors_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Anchor {key} dropped at {file_path}:{line_num}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage: python anchor_drop.py <file> <line> <desc> [kind]")
        sys.exit(1)

    file_path = sys.argv[1]
    line_num = int(sys.argv[2])
    desc = sys.argv[3]
    kind = sys.argv[4] if len(sys.argv) > 4 else "line"
    drop_anchor(file_path, line_num, desc, kind)
