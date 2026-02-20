# Dependency Layers

Generated: 2026-02-20

## Layer Order (topological)

```
test_dead_code
ui
core
tools
utils
configuration
constants
exceptions
infrastructure
types
```

## Layer-to-Layer Imports

| From | To | Count |
|------|----|-------|
| configuration | constants | 6 |
| configuration | exceptions | 1 |
| configuration | infrastructure | 2 |
| configuration | types | 4 |
| core | configuration | 16 |
| core | constants | 5 |
| core | exceptions | 2 |
| core | infrastructure | 3 |
| core | tools | 8 |
| core | types | 16 |
| core | utils | 6 |
| exceptions | types | 1 |
| infrastructure | types | 1 |
| tools | configuration | 4 |
| tools | exceptions | 6 |
| tools | infrastructure | 3 |
| ui | core | 62 |
| utils | configuration | 2 |
| utils | types | 2 |
