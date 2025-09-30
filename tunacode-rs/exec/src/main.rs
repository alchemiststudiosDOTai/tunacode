//! Entry-point for the `tunacode-exec` binary.
//!
//! When this CLI is invoked normally, it parses the standard `tunacode-exec` CLI
//! options and launches the non-interactive tunacode agent. However, if it is
//! invoked with arg0 as `tunacode-linux-sandbox`, we instead treat the invocation
//! as a request to run the logic for the standalone `tunacode-linux-sandbox`
//! executable (i.e., parse any -s args and then run a *sandboxed* command under
//! Landlock + seccomp.
//!
//! This allows us to ship a completely separate set of functionality as part
//! of the `tunacode-exec` binary.
use clap::Parser;
use tunacode_arg0::arg0_dispatch_or_else;
use tunacode_common::CliConfigOverrides;
use tunacode_exec::Cli;
use tunacode_exec::run_main;

#[derive(Parser, Debug)]
struct TopCli {
    #[clap(flatten)]
    config_overrides: CliConfigOverrides,

    #[clap(flatten)]
    inner: Cli,
}

fn main() -> anyhow::Result<()> {
    arg0_dispatch_or_else(|tunacode_linux_sandbox_exe| async move {
        let top_cli = TopCli::parse();
        // Merge root-level overrides into inner CLI struct so downstream logic remains unchanged.
        let mut inner = top_cli.inner;
        inner
            .config_overrides
            .raw_overrides
            .splice(0..0, top_cli.config_overrides.raw_overrides);

        run_main(inner, tunacode_linux_sandbox_exe).await?;
        Ok(())
    })
}
