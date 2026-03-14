# Dependency Layers

Generated: 2026-03-14

## Layer Order (topological)

```
configuration
constants
core
exceptions
infrastructure
skills
test_dead_code
tools
types
ui
utils
```

## Layer-to-Layer Imports

| From | To | Count |
|------|----|-------|
| configuration | constants | 7 |
| configuration | exceptions | 1 |
| configuration | infrastructure | 2 |
| configuration | types | 4 |
| core | configuration | 15 |
| core | constants | 5 |
| core | exceptions | 2 |
| core | infrastructure | 3 |
| core | skills | 4 |
| core | tools | 9 |
| core | types | 17 |
| core | utils | 6 |
| exceptions | types | 1 |
| infrastructure | skills | 1 |
| infrastructure | types | 2 |
| skills | core | 1 |
| skills | infrastructure | 1 |
| tools | configuration | 3 |
| tools | exceptions | 6 |
| tools | infrastructure | 3 |
| tools | types | 1 |
| ui | core | 61 |
| ui | skills | 8 |
| utils | configuration | 2 |
| utils | types | 2 |
