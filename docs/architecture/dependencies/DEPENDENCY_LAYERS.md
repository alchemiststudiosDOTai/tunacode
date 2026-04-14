# Dependency Layers

Generated: 2026-04-14

## Layer Order (topological)

```
configuration
constants
core
exceptions
infrastructure
skills
tools
types
ui
utils
```

## Layer-to-Layer Imports

| From | To | Count |
|------|----|-------|
| configuration | constants | 6 |
| configuration | exceptions | 1 |
| configuration | infrastructure | 2 |
| configuration | types | 6 |
| core | configuration | 9 |
| core | constants | 4 |
| core | exceptions | 3 |
| core | infrastructure | 3 |
| core | skills | 4 |
| core | tools | 7 |
| core | types | 15 |
| core | utils | 6 |
| exceptions | types | 1 |
| infrastructure | configuration | 1 |
| infrastructure | skills | 1 |
| infrastructure | types | 3 |
| skills | core | 1 |
| skills | infrastructure | 1 |
| tools | configuration | 4 |
| tools | exceptions | 7 |
| tools | infrastructure | 2 |
| tools | types | 1 |
| ui | configuration | 17 |
| ui | constants | 20 |
| ui | core | 20 |
| ui | exceptions | 1 |
| ui | skills | 9 |
| ui | types | 6 |
| ui | utils | 3 |
| utils | configuration | 2 |
| utils | types | 2 |
