use tunacode_app_server::run_main;
use tunacode_arg0::arg0_dispatch_or_else;
use tunacode_common::CliConfigOverrides;

fn main() -> anyhow::Result<()> {
    arg0_dispatch_or_else(|tunacode_linux_sandbox_exe| async move {
        run_main(tunacode_linux_sandbox_exe, CliConfigOverrides::default()).await?;
        Ok(())
    })
}
