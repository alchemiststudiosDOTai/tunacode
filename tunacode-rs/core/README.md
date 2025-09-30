# tunacode-core

This crate implements the business logic for tunacode. It is designed to be used by the various tunacode UIs written in Rust.

## Dependencies

Note that `tunacode-core` makes some assumptions about certain helper utilities being available in the environment. Currently, this

### macOS

Expects `/usr/bin/sandbox-exec` to be present.

### Linux

Expects the binary containing `tunacode-core` to run the equivalent of `tunacode debug landlock` when `arg0` is `tunacode-linux-sandbox`. See the `tunacode-arg0` crate for details.

### All Platforms

Expects the binary containing `tunacode-core` to simulate the virtual `apply_patch` CLI when `arg1` is `--tunacode-run-as-apply-patch`. See the `tunacode-arg0` crate for details.
