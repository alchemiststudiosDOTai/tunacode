# tunacode-git-tooling

Helpers for interacting with git.

```rust,no_run
use std::path::Path;

use tunacode_git_tooling::{create_ghost_commit, restore_ghost_commit, CreateGhostCommitOptions};

let repo = Path::new("/path/to/repo");

// Capture the current working tree as an unreferenced commit.
let ghost = create_ghost_commit(&CreateGhostCommitOptions::new(repo))?;

// Later, undo back to that state.
restore_ghost_commit(repo, &ghost)?;
```

Pass a custom message with `.message("…")` or force-include ignored files with
`.force_include(["ignored.log".into()])`.
