# Dependency Layers

Generated: 2026-02-07

## Layer Order (topological)

```
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
| core | configuration | 15 |
| core | constants | 5 |
| core | exceptions | 5 |
| core | infrastructure | 7 |
| core | tools | 11 |
| core | types | 27 |
| core | utils | 5 |
| exceptions | types | 1 |
| infrastructure | types | 1 |
| tools | configuration | 5 |
| tools | exceptions | 10 |
| tools | infrastructure | 3 |
| ui | core | 50 |
| utils | configuration | 2 |
| utils | types | 1 |
