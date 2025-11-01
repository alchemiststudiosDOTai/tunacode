#!/bin/bash
# Compare this fork with upstream kimi-cli
# Usage: ./scripts/compare-upstream.sh

set -e

echo "================================================"
echo "  Fork Comparison Tool"
echo "================================================"
echo

# Detect version-aware sorter
if command -v gsort >/dev/null 2>&1; then
    SORT_CMD="gsort -V"
elif sort -V </dev/null >/dev/null 2>&1; then
    SORT_CMD="sort -V"
else
    # Python fallback for version sorting
    SORT_CMD='python3 -c "import sys; lines = sys.stdin.read().strip().split(\"\\n\"); print(\"\\n\".join(sorted(lines, key=lambda v: tuple(int(x) if x.isdigit() else 0 for x in v.split(\".\")[:3]))))"'
fi

# Fetch latest upstream
echo "Fetching upstream changes..."
git fetch upstream --tags

# Get current commits
FORK_COMMIT=$(git rev-parse --short HEAD)
UPSTREAM_COMMIT=$(git rev-parse --short upstream/main)
FORK_BASE=$(git rev-parse --short upstream-v0.45-base 2>/dev/null || echo "not-tagged")

echo
echo "Current Status:"
echo "   Fork commit:     $FORK_COMMIT"
echo "   Upstream commit: $UPSTREAM_COMMIT"
echo "   Fork base:       $FORK_BASE (upstream v0.45)"
echo

# Show version differences
echo "Versions:"
FORK_VERSION=$(grep "^version = " pyproject.toml | cut -d'"' -f2)
UPSTREAM_VERSION=$(git show upstream/main:pyproject.toml | grep "^version = " | cut -d'"' -f2)
echo "   Fork:     v$FORK_VERSION"
echo "   Upstream: v$UPSTREAM_VERSION"
echo

# Check for new upstream releases
echo "Upstream releases since fork base:"
git tag -l --sort=-version:refname | grep -E "^[0-9]+\.[0-9]+" | while read tag; do
    if [[ $(printf "%s\n%s\n" "$tag" "0.45" | eval "$SORT_CMD" | head -n1) != "$tag" ]]; then
        echo "   - $tag (NEW)"
    fi
done | head -10
echo

# Show commit counts
FORK_COMMITS=$(git rev-list --count HEAD ^upstream-v0.45-base 2>/dev/null || git rev-list --count HEAD)
UPSTREAM_NEW=$(git rev-list --count upstream/main ^upstream/main~100 2>/dev/null || echo "?")
echo "Commit counts:"
echo "   Fork additions:      $FORK_COMMITS commits"
echo "   Upstream recent:     $UPSTREAM_NEW commits (last 100)"
echo

# Show file differences
echo "File changes (fork vs upstream):"
CHANGED_FILES=$(git diff --name-only upstream/main HEAD | wc -l)
ADDED_FILES=$(git diff --name-status upstream/main HEAD | grep "^A" | wc -l)
MODIFIED_FILES=$(git diff --name-status upstream/main HEAD | grep "^M" | wc -l)
echo "   Total changed:  $CHANGED_FILES files"
echo "   Added:          $ADDED_FILES files"
echo "   Modified:       $MODIFIED_FILES files"
echo

# Show new files added in fork
echo "Files unique to fork:"
git diff --name-status upstream/main HEAD | grep "^A" | awk '{print "   - " $2}' | head -20
echo

# Check for notable upstream changes
echo "Recent upstream changes:"
git log --oneline upstream/main ^upstream-v0.45-base --no-merges 2>/dev/null | head -10 || \
git log --oneline upstream/main --no-merges | head -10
echo

echo "================================================"
echo "To see detailed diff: git diff upstream/main"
echo "To see file stats:    git diff --stat upstream/main"
echo "================================================"
