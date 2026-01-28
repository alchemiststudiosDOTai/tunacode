# Dependency Layers

Generated: 2026-01-28

## Layer Order (topological)

```
ui
core
infrastructure
tools
utils
configuration
constants
exceptions
types
```

## Layer-to-Layer Imports

| From | To | Count |
|------|----|-------|
| configuration | constants | 6 |
| configuration | exceptions | 1 |
| configuration | types | 4 |
| core | configuration | 16 |
| core | constants | 6 |
| core | exceptions | 4 |
| core | infrastructure | 1 |
| core | tools | 12 |
| core | types | 23 |
| core | utils | 6 |
| exceptions | types | 1 |
| tools | configuration | 4 |
| tools | exceptions | 4 |
| ui | core | 50 |
| utils | configuration | 2 |
| utils | types | 1 |
