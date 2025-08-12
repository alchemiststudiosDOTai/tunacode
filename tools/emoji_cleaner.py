#!/usr/bin/env python3
"""
emoji_cleaner.py

Usage:
  python tools/emoji_cleaner.py --dry-run
  python tools/emoji_cleaner.py --preview > changes.diff
  python tools/emoji_cleaner.py --apply

Features:
- Scans files under the repository root for emoji/pictograph characters
- Supports dry-run (lists matches), preview (prints unified diffs), and apply (writes changes)
- Respects exclude directories and file extensions
- Protects against applying on main/master branch or with an unclean working tree unless --confirm-apply
- Uses a conservative emoji regex to avoid removing accents, box-drawing, or CJK characters

Note: Run with --dry-run first. Inspect diffs before using --apply.
"""

import argparse
import difflib
import pathlib
import re
import subprocess
import sys
from typing import Iterable, List

# Conservative emoji/pictograph ranges (covers common emoji blocks)
EMOJI_PATTERN = (
    r"("
    r"[\U0001F300-\U0001F5FF]"  # Misc Symbols & Pictographs
    r"|[\U0001F600-\U0001F64F]"  # Emoticons
    r"|[\U0001F680-\U0001F6FF]"  # Transport & Map
    r"|[\U0001F700-\U0001F77F]"  # Alchemical Symbols
    r"|[\U0001F780-\U0001F7FF]"  # Geometric Shapes Extended
    r"|[\U0001F800-\U0001F8FF]"  # Supplemental Arrows-C (some symbols)
    r"|[\U0001F900-\U0001F9FF]"  # Supplemental Symbols & Pictographs
    r"|[\U0001FA00-\U0001FA6F]"  # Chess etc
    r"|[\U0001FA70-\U0001FAFF]"  # Symbols & Pictographs Extended-A
    r"|[\u2600-\u26FF]"  # Misc symbols
    r"|[\u2700-\u27BF]"  # Dingbats
    r"|\uFE0F"  # Variation Selector-16
    r")"
)
EMOJI_RE = re.compile(EMOJI_PATTERN)

# Default file extensions to scan
DEFAULT_EXTS = {".py", ".js", ".ts", ".md", ".json", ".html", ".css", ".yml", ".yaml", ".txt"}
DEFAULT_EXCLUDE_DIRS = {".git", "node_modules", "venv", ".venv", "dist", "build"}

# Files/globs to always skip by default (relative paths)
DEFAULT_WHITELIST = [
    # documentation/art and intentional box-drawing can stay
    "documentation/**",
    "docs/**",
    "memory-bank/**",
    ".claude/**",
    "llm-agent-tools/**",
]


def iter_files(root: pathlib.Path, exts: set, exclude_dirs: set) -> Iterable[pathlib.Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        if any(part in exclude_dirs for part in p.parts):
            continue
        yield p


def is_whitelisted(path: pathlib.Path, whitelists: List[str]) -> bool:
    # Simple glob-like check using pathlib.Path.match with pattern relative to repo root
    rel = str(path)
    for pattern in whitelists:
        try:
            if pathlib.Path(rel).match(pattern):
                return True
        except Exception:
            # fallback: substring
            if pattern.strip("* ") in rel:
                return True
    return False


def scrub_text(text: str) -> str:
    # Remove emoji/pictograph characters matched by EMOJI_RE
    return EMOJI_RE.sub("", text)


def git_branch_and_status():
    try:
        branch = (
            subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()
        )
    except Exception:
        branch = None
    try:
        status = subprocess.check_output(["git", "status", "--porcelain"]).decode().strip()
    except Exception:
        status = None
    return branch, status


def unified_diff_str(orig: str, new: str, path: str) -> str:
    orig_lines = orig.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, new_lines, fromfile=path, tofile=path + " (clean)")
    return "".join(diff)


def main(argv: List[str] = None):
    ap = argparse.ArgumentParser(
        description="Scan and optionally remove emoji from repository files"
    )
    ap.add_argument("--root", default=".", help="Repository root to scan (default: .)")
    ap.add_argument("--dry-run", action="store_true", help="Only list matches (no diffs)")
    ap.add_argument("--preview", action="store_true", help="Print unified diffs to stdout")
    ap.add_argument("--apply", action="store_true", help="Apply changes (writes files)")
    ap.add_argument(
        "--confirm-apply", action="store_true", help="Confirm apply even if on main or dirty"
    )
    ap.add_argument(
        "--ext",
        action="append",
        default=[],
        help="Additional file extensions to include (e.g. .rst)",
    )
    ap.add_argument(
        "--exclude-dir", action="append", default=[], help="Additional directories to exclude"
    )
    ap.add_argument(
        "--whitelist", action="append", default=[], help="Glob patterns to skip (relative)"
    )
    ap.add_argument(
        "--replace-with", default="", help="Replace emoji with this text instead of removing"
    )

    args = ap.parse_args(argv)
    root = pathlib.Path(args.root)
    exts = set(DEFAULT_EXTS)
    for e in args.ext:
        if not e.startswith("."):
            e = "." + e
        exts.add(e)
    exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
    for d in args.exclude_dir:
        exclude_dirs.add(d)
    whitelists = DEFAULT_WHITELIST + list(args.whitelist)

    files_changed = 0
    diffs = []

    for f in iter_files(root, exts, exclude_dirs):
        if is_whitelisted(f, whitelists):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Skipping {f} (read error: {e})", file=sys.stderr)
            continue
        if EMOJI_RE.search(text):
            new_text = EMOJI_RE.sub(args.replace_with, text)
            if args.dry_run:
                print(f"=== {f} ===")
                for m in EMOJI_RE.finditer(text):
                    start, end = m.span()
                    ctx = text[max(0, start - 40) : min(len(text), end + 40)].replace("\n", " ")
                    print(f"  {m.group(0)!r} -> context: {ctx}")
            else:
                diff = unified_diff_str(text, new_text, str(f))
                if diff:
                    diffs.append(diff)
                if args.apply:
                    # Defer writing until all checks pass
                    files_changed += 1

    if args.preview and diffs:
        print("\n\n".join(diffs))

    if args.apply:
        branch, status = git_branch_and_status()
        if branch in ("main", "master") and not args.confirm_apply:
            print(
                f"Refusing to apply on branch '{branch}'. Use --confirm-apply to override.",
                file=sys.stderr,
            )
            sys.exit(2)
        if status and status.strip() and not args.confirm_apply:
            print(
                "Working tree is not clean. Commit or stash changes before running with --apply, or pass --confirm-apply to force.",
                file=sys.stderr,
            )
            sys.exit(3)

        # Apply changes now (second pass to write files)
        written = 0
        for f in iter_files(root, exts, exclude_dirs):
            if is_whitelisted(f, whitelists):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError, PermissionError):
                continue
            if EMOJI_RE.search(text):
                new_text = EMOJI_RE.sub(args.replace_with, text)
                if new_text != text:
                    f.write_text(new_text, encoding="utf-8")
                    written += 1
        print(
            f"Applied changes to {written} files. Please review, git add and commit on your branch."
        )

    if not (args.dry_run or args.preview or args.apply):
        print("No action specified. Use --dry-run, --preview, or --apply. Use --help for details.")


if __name__ == "__main__":
    main()
