# Docs

This directory contains project documentation, architecture artifacts, and reference materials for TunaCode.

## Folders

- `architecture/dependencies/` — generated dependency layer diagrams and reports.
- `codebase-map/structure/` — auto-generated codebase structure tree.
- `git/` — Git workflow practices and safety guidelines.
- `images/` — screenshots, diagrams, and UI assets.
- `modules/` — per-layer documentation (types, utils, infrastructure, configuration, tools, core, ui, skills).
- `reviews/` — PR review notes and code quality feedback.
- `ui/` — CSS architecture and theming guidelines.

## Key Documents

| Document | Purpose |
|----------|---------|
| `modules/index.md` | Module layer map and reading order (start here for architecture orientation) |
| `git/practices.md` | Git safety rules and non-destructive workflow practices |
| `ui/css-architecture.md` | CSS theming and NeXTSTEP-inspired design system |
| `codebase-map/structure/tree-structure.txt` | Auto-generated source tree structure |

## Markdown Metadata Note

- `README.md` is exempt from any Markdown frontmatter requirement.
- If a frontmatter rule is applied to docs pages in the future, do not require YAML frontmatter in the repository root `README.md`.

## Generated Artifacts

- `docs_audit.html` — documentation consistency audit report (review before cleanup)
