# tunacode-linux-sandbox

This crate is responsible for producing:

- a `tunacode-linux-sandbox` standalone executable for Linux that is bundled with the Node.js version of the tunacode CLI
- a lib crate that exposes the business logic of the executable as `run_main()` so that
  - the `tunacode-exec` CLI can check if its arg0 is `tunacode-linux-sandbox` and, if so, execute as if it were `tunacode-linux-sandbox`
  - this should also be true of the `tunacode` multitool CLI
