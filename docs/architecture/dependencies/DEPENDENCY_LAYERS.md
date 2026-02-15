# Dependency Layers

Generated: 2026-02-15

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
| core | configuration | 16 |
| core | constants | 5 |
| core | exceptions | 3 |
| core | infrastructure | 3 |
| core | tools | 10 |
| core | types | 15 |
| core | utils | 6 |
| exceptions | types | 1 |
| infrastructure | types | 1 |
| tools | configuration | 5 |
| tools | exceptions | 10 |
| tools | infrastructure | 3 |
| ui | core | 58 |
| utils | configuration | 2 |
| utils | types | 2 |
