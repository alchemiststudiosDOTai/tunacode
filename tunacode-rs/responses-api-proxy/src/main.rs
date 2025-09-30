use clap::Parser;
use tunacode_responses_api_proxy::Args as ResponsesApiProxyArgs;

#[ctor::ctor]
fn pre_main() {
    tunacode_process_hardening::pre_main_hardening();
}

pub fn main() -> anyhow::Result<()> {
    let args = ResponsesApiProxyArgs::parse();
    tunacode_responses_api_proxy::run_main(args)
}
