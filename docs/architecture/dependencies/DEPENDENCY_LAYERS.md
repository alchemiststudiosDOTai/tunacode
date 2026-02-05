# Dependency Layers

Generated: 2026-02-04

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
| core | configuration | 15 |
| core | constants | 6 |
| core | exceptions | 5 |
| core | infrastructure | 4 |
| core | tools | 11 |
| core | types | 21 |
| core | utils | 5 |
| exceptions | types | 1 |
| tools | configuration | 4 |
| tools | exceptions | 10 |
| ui | core | 50 |
| utils | configuration | 2 |
| utils | types | 1 |
