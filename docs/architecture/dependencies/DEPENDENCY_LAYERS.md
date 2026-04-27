# Dependency Layers

Generated: 2026-04-27

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
| core | tools | 6 |
| core | types | 10 |
| core | utils | 6 |
| exceptions | types | 1 |
| infrastructure | configuration | 1 |
| infrastructure | skills | 1 |
| infrastructure | types | 3 |
| skills | core | 1 |
| skills | infrastructure | 1 |
| tools | configuration | 2 |
| tools | exceptions | 7 |
| tools | infrastructure | 2 |
| ui | configuration | 17 |
| ui | constants | 19 |
| ui | core | 18 |
| ui | exceptions | 1 |
| ui | skills | 9 |
| ui | types | 6 |
| ui | utils | 3 |
| utils | configuration | 2 |
