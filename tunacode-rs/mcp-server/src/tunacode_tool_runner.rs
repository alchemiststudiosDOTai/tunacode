//! Asynchronous worker that executes a **tunacode** tool-call inside a spawned
//! Tokio task. Separated from `message_processor.rs` to keep that file small
//! and to make future feature-growth easier to manage.

use std::collections::HashMap;
use std::sync::Arc;

use crate::exec_approval::handle_exec_approval_request;
use crate::outgoing_message::OutgoingMessageSender;
use crate::outgoing_message::OutgoingNotificationMeta;
use crate::patch_approval::handle_patch_approval_request;
use mcp_types::CallToolResult;
use mcp_types::ContentBlock;
use mcp_types::RequestId;
use mcp_types::TextContent;
use serde_json::json;
use tokio::sync::Mutex;
use tunacode_core::ConversationManager;
use tunacode_core::NewConversation;
use tunacode_core::config::Config as tunacodeConfig;
use tunacode_core::protocol::AgentMessageEvent;
use tunacode_core::protocol::ApplyPatchApprovalRequestEvent;
use tunacode_core::protocol::Event;
use tunacode_core::protocol::EventMsg;
use tunacode_core::protocol::ExecApprovalRequestEvent;
use tunacode_core::protocol::InputItem;
use tunacode_core::protocol::Op;
use tunacode_core::protocol::Submission;
use tunacode_core::protocol::TaskCompleteEvent;
use tunacode_core::tunacodeConversation;
use tunacode_protocol::mcp_protocol::ConversationId;

pub(crate) const INVALID_PARAMS_ERROR_CODE: i64 = -32602;

/// Run a complete tunacode session and stream events back to the client.
///
/// On completion (success or error) the function sends the appropriate
/// `tools/call` response so the LLM can continue the conversation.
pub async fn run_tunacode_tool_session(
    id: RequestId,
    initial_prompt: String,
    config: tunacodeConfig,
    outgoing: Arc<OutgoingMessageSender>,
    conversation_manager: Arc<ConversationManager>,
    running_requests_id_to_tunacode_uuid: Arc<Mutex<HashMap<RequestId, ConversationId>>>,
) {
    let NewConversation {
        conversation_id,
        conversation,
        session_configured,
    } = match conversation_manager.new_conversation(config).await {
        Ok(res) => res,
        Err(e) => {
            let result = CallToolResult {
                content: vec![ContentBlock::TextContent(TextContent {
                    r#type: "text".to_string(),
                    text: format!("Failed to start tunacode session: {e}"),
                    annotations: None,
                })],
                is_error: Some(true),
                structured_content: None,
            };
            outgoing.send_response(id.clone(), result).await;
            return;
        }
    };

    let session_configured_event = Event {
        // Use a fake id value for now.
        id: "".to_string(),
        msg: EventMsg::SessionConfigured(session_configured.clone()),
    };
    outgoing
        .send_event_as_notification(
            &session_configured_event,
            Some(OutgoingNotificationMeta::new(Some(id.clone()))),
        )
        .await;

    // Use the original MCP request ID as the `sub_id` for the tunacode submission so that
    // any events emitted for this tool-call can be correlated with the
    // originating `tools/call` request.
    let sub_id = match &id {
        RequestId::String(s) => s.clone(),
        RequestId::Integer(n) => n.to_string(),
    };
    running_requests_id_to_tunacode_uuid
        .lock()
        .await
        .insert(id.clone(), conversation_id);
    let submission = Submission {
        id: sub_id.clone(),
        op: Op::UserInput {
            items: vec![InputItem::Text {
                text: initial_prompt.clone(),
            }],
        },
    };

    if let Err(e) = conversation.submit_with_id(submission).await {
        tracing::error!("Failed to submit initial prompt: {e}");
        // unregister the id so we don't keep it in the map
        running_requests_id_to_tunacode_uuid
            .lock()
            .await
            .remove(&id);
        return;
    }

    run_tunacode_tool_session_inner(
        conversation,
        outgoing,
        id,
        running_requests_id_to_tunacode_uuid,
    )
    .await;
}

pub async fn run_tunacode_tool_session_reply(
    conversation: Arc<tunacodeConversation>,
    outgoing: Arc<OutgoingMessageSender>,
    request_id: RequestId,
    prompt: String,
    running_requests_id_to_tunacode_uuid: Arc<Mutex<HashMap<RequestId, ConversationId>>>,
    conversation_id: ConversationId,
) {
    running_requests_id_to_tunacode_uuid
        .lock()
        .await
        .insert(request_id.clone(), conversation_id);
    if let Err(e) = conversation
        .submit(Op::UserInput {
            items: vec![InputItem::Text { text: prompt }],
        })
        .await
    {
        tracing::error!("Failed to submit user input: {e}");
        // unregister the id so we don't keep it in the map
        running_requests_id_to_tunacode_uuid
            .lock()
            .await
            .remove(&request_id);
        return;
    }

    run_tunacode_tool_session_inner(
        conversation,
        outgoing,
        request_id,
        running_requests_id_to_tunacode_uuid,
    )
    .await;
}

async fn run_tunacode_tool_session_inner(
    tunacode: Arc<tunacodeConversation>,
    outgoing: Arc<OutgoingMessageSender>,
    request_id: RequestId,
    running_requests_id_to_tunacode_uuid: Arc<Mutex<HashMap<RequestId, ConversationId>>>,
) {
    let request_id_str = match &request_id {
        RequestId::String(s) => s.clone(),
        RequestId::Integer(n) => n.to_string(),
    };

    // Stream events until the task needs to pause for user interaction or
    // completes.
    loop {
        match tunacode.next_event().await {
            Ok(event) => {
                outgoing
                    .send_event_as_notification(
                        &event,
                        Some(OutgoingNotificationMeta::new(Some(request_id.clone()))),
                    )
                    .await;

                match event.msg {
                    EventMsg::ExecApprovalRequest(ExecApprovalRequestEvent {
                        command,
                        cwd,
                        call_id,
                        reason: _,
                    }) => {
                        handle_exec_approval_request(
                            command,
                            cwd,
                            outgoing.clone(),
                            tunacode.clone(),
                            request_id.clone(),
                            request_id_str.clone(),
                            event.id.clone(),
                            call_id,
                        )
                        .await;
                        continue;
                    }
                    EventMsg::Error(err_event) => {
                        // Return a response to conclude the tool call when the tunacode session reports an error (e.g., interruption).
                        let result = json!({
                            "error": err_event.message,
                        });
                        outgoing.send_response(request_id.clone(), result).await;
                        break;
                    }
                    EventMsg::ApplyPatchApprovalRequest(ApplyPatchApprovalRequestEvent {
                        call_id,
                        reason,
                        grant_root,
                        changes,
                    }) => {
                        handle_patch_approval_request(
                            call_id,
                            reason,
                            grant_root,
                            changes,
                            outgoing.clone(),
                            tunacode.clone(),
                            request_id.clone(),
                            request_id_str.clone(),
                            event.id.clone(),
                        )
                        .await;
                        continue;
                    }
                    EventMsg::TaskComplete(TaskCompleteEvent { last_agent_message }) => {
                        let text = match last_agent_message {
                            Some(msg) => msg,
                            None => "".to_string(),
                        };
                        let result = CallToolResult {
                            content: vec![ContentBlock::TextContent(TextContent {
                                r#type: "text".to_string(),
                                text,
                                annotations: None,
                            })],
                            is_error: None,
                            structured_content: None,
                        };
                        outgoing.send_response(request_id.clone(), result).await;
                        // unregister the id so we don't keep it in the map
                        running_requests_id_to_tunacode_uuid
                            .lock()
                            .await
                            .remove(&request_id);
                        break;
                    }
                    EventMsg::SessionConfigured(_) => {
                        tracing::error!("unexpected SessionConfigured event");
                    }
                    EventMsg::AgentMessageDelta(_) => {
                        // TODO: think how we want to support this in the MCP
                    }
                    EventMsg::AgentReasoningDelta(_) => {
                        // TODO: think how we want to support this in the MCP
                    }
                    EventMsg::AgentMessage(AgentMessageEvent { .. }) => {
                        // TODO: think how we want to support this in the MCP
                    }
                    EventMsg::AgentReasoningRawContent(_)
                    | EventMsg::AgentReasoningRawContentDelta(_)
                    | EventMsg::TaskStarted(_)
                    | EventMsg::TokenCount(_)
                    | EventMsg::AgentReasoning(_)
                    | EventMsg::AgentReasoningSectionBreak(_)
                    | EventMsg::McpToolCallBegin(_)
                    | EventMsg::McpToolCallEnd(_)
                    | EventMsg::McpListToolsResponse(_)
                    | EventMsg::ListCustomPromptsResponse(_)
                    | EventMsg::ExecCommandBegin(_)
                    | EventMsg::ExecCommandOutputDelta(_)
                    | EventMsg::ExecCommandEnd(_)
                    | EventMsg::BackgroundEvent(_)
                    | EventMsg::StreamError(_)
                    | EventMsg::PatchApplyBegin(_)
                    | EventMsg::PatchApplyEnd(_)
                    | EventMsg::TurnDiff(_)
                    | EventMsg::WebSearchBegin(_)
                    | EventMsg::WebSearchEnd(_)
                    | EventMsg::GetHistoryEntryResponse(_)
                    | EventMsg::PlanUpdate(_)
                    | EventMsg::TurnAborted(_)
                    | EventMsg::ConversationPath(_)
                    | EventMsg::UserMessage(_)
                    | EventMsg::ShutdownComplete
                    | EventMsg::EnteredReviewMode(_)
                    | EventMsg::ExitedReviewMode(_) => {
                        // For now, we do not do anything extra for these
                        // events. Note that
                        // send(tunacode_event_to_notification(&event)) above has
                        // already dispatched these events as notifications,
                        // though we may want to do give different treatment to
                        // individual events in the future.
                    }
                }
            }
            Err(e) => {
                let result = CallToolResult {
                    content: vec![ContentBlock::TextContent(TextContent {
                        r#type: "text".to_string(),
                        text: format!("tunacode runtime error: {e}"),
                        annotations: None,
                    })],
                    is_error: Some(true),
                    // TODO(mbolin): Could present the error in a more
                    // structured way.
                    structured_content: None,
                };
                outgoing.send_response(request_id.clone(), result).await;
                break;
            }
        }
    }
}
