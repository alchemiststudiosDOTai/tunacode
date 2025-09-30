use std::collections::HashMap;
use std::path::PathBuf;

use tunacode_core::config::Config;
use tunacode_core::protocol::Event;
use tunacode_core::protocol::EventMsg;
use tunacode_core::protocol::SessionConfiguredEvent;
use tunacode_core::protocol::TaskCompleteEvent;
use serde_json::json;

use crate::event_processor::TunacodeStatus;
use crate::event_processor::EventProcessor;
use crate::event_processor::handle_last_message;
use tunacode_common::create_config_summary_entries;

pub(crate) struct EventProcessorWithJsonOutput {
    last_message_path: Option<PathBuf>,
}

impl EventProcessorWithJsonOutput {
    pub fn new(last_message_path: Option<PathBuf>) -> Self {
        Self { last_message_path }
    }
}

impl EventProcessor for EventProcessorWithJsonOutput {
    fn print_config_summary(&mut self, config: &Config, prompt: &str, _: &SessionConfiguredEvent) {
        let entries = create_config_summary_entries(config)
            .into_iter()
            .map(|(key, value)| (key.to_string(), value))
            .collect::<HashMap<String, String>>();
        #[expect(clippy::expect_used)]
        let config_json =
            serde_json::to_string(&entries).expect("Failed to serialize config summary to JSON");
        println!("{config_json}");

        let prompt_json = json!({
            "prompt": prompt,
        });
        println!("{prompt_json}");
    }

    fn process_event(&mut self, event: Event) -> TunacodeStatus {
        match event.msg {
            EventMsg::AgentMessageDelta(_) | EventMsg::AgentReasoningDelta(_) => {
                // Suppress streaming events in JSON mode.
                TunacodeStatus::Running
            }
            EventMsg::TaskComplete(TaskCompleteEvent { last_agent_message }) => {
                if let Some(output_file) = self.last_message_path.as_deref() {
                    handle_last_message(last_agent_message.as_deref(), output_file);
                }
                TunacodeStatus::InitiateShutdown
            }
            EventMsg::ShutdownComplete => TunacodeStatus::Shutdown,
            _ => {
                if let Ok(line) = serde_json::to_string(&event) {
                    println!("{line}");
                }
                TunacodeStatus::Running
            }
        }
    }
}
