# This file is intentionally empty.
#
# This project uses the "src-layout" pattern where:
# - src/ is a container directory (NOT a Python package)
# - src/tunacode/ is the actual Python package
#
# This empty __init__.py exists only to satisfy some tooling that expects
# __init__.py files in directory hierarchies, but src/ itself is not imported.
#
# The actual package initialization is in src/tunacode/__init__.py
#
# Reference: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
