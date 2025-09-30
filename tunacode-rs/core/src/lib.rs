//! Root of the `tunacode-core` library.

// Prevent accidental direct writes to stdout/stderr in library code. All
// user-visible output must go through the appropriate abstraction (e.g.,
// the TUI or the tracing stack).
#![deny(clippy::print_stdout, clippy::print_stderr)]

mod apply_patch;
pub mod auth;
pub mod bash;
mod chat_completions;
mod client;
mod client_common;
pub mod tunacode;
mod tunacode_conversation;
pub mod token_data;
pub use tunacode_conversation::tunacodeConversation;
mod command_safety;
pub mod config;
pub mod config_edit;
pub mod config_profile;
pub mod config_types;
mod conversation_history;
pub mod custom_prompts;
mod environment_context;
pub mod error;
pub mod exec;
mod exec_command;
pub mod exec_env;
mod flags;
pub mod git_info;
pub mod landlock;
mod mcp_connection_manager;
mod mcp_tool_call;
mod message_history;
mod model_provider_info;
pub mod parse_command;
mod truncate;
mod unified_exec;
mod user_instructions;
pub use model_provider_info::BUILT_IN_OSS_MODEL_PROVIDER_ID;
pub use model_provider_info::ModelProviderInfo;
pub use model_provider_info::WireApi;
pub use model_provider_info::built_in_model_providers;
pub use model_provider_info::create_oss_provider_with_base_url;
mod conversation_manager;
mod event_mapping;
pub mod review_format;
pub use tunacode_protocol::protocol::InitialHistory;
pub use conversation_manager::ConversationManager;
pub use conversation_manager::NewConversation;
// Re-export common auth types for workspace consumers
pub use auth::AuthManager;
pub use auth::tunacodeAuth;
pub mod default_client;
pub mod model_family;
mod openai_model_info;
mod openai_tools;
pub mod plan_tool;
pub mod project_doc;
mod rollout;
pub(crate) mod safety;
pub mod seatbelt;
pub mod shell;
pub mod spawn;
pub mod terminal;
mod tool_apply_patch;
pub mod turn_diff_tracker;
pub use rollout::ARCHIVED_SESSIONS_SUBDIR;
pub use rollout::RolloutRecorder;
pub use rollout::SESSIONS_SUBDIR;
pub use rollout::SessionMeta;
pub use rollout::find_conversation_path_by_id_str;
pub use rollout::list::ConversationItem;
pub use rollout::list::ConversationsPage;
pub use rollout::list::Cursor;
mod function_tool;
mod state;
mod tasks;
mod user_notification;
pub mod util;

pub use apply_patch::tunacode_APPLY_PATCH_ARG1;
pub use command_safety::is_safe_command;
pub use safety::get_platform_sandbox;
// Re-export the protocol types from the standalone `tunacode-protocol` crate so existing
// `tunacode_core::protocol::...` references continue to work across the workspace.
pub use tunacode_protocol::protocol;
// Re-export protocol config enums to ensure call sites can use the same types
// as those in the protocol crate when constructing protocol messages.
pub use tunacode_protocol::config_types as protocol_config_types;

pub use client::ModelClient;
pub use client_common::Prompt;
pub use client_common::REVIEW_PROMPT;
pub use client_common::ResponseEvent;
pub use client_common::ResponseStream;
pub use tunacode::compact::content_items_to_text;
pub use tunacode::compact::is_session_prefix_message;
pub use tunacode_protocol::models::ContentItem;
pub use tunacode_protocol::models::LocalShellAction;
pub use tunacode_protocol::models::LocalShellExecAction;
pub use tunacode_protocol::models::LocalShellStatus;
pub use tunacode_protocol::models::ReasoningItemContent;
pub use tunacode_protocol::models::ResponseItem;

pub mod otel_init;
