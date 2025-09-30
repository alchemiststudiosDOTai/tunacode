use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;

use tunacode_core::tunacodeConversation;
use tunacode_core::protocol::FileChange;
use tunacode_core::protocol::Op;
use tunacode_core::protocol::ReviewDecision;
use mcp_types::ElicitRequest;
use mcp_types::ElicitRequestParamsRequestedSchema;
use mcp_types::JSONRPCErrorError;
use mcp_types::ModelContextProtocolRequest;
use mcp_types::RequestId;
use serde::Deserialize;
use serde::Serialize;
use serde_json::json;
use tracing::error;

use crate::tunacode_tool_runner::INVALID_PARAMS_ERROR_CODE;
use crate::outgoing_message::OutgoingMessageSender;

#[derive(Debug, Serialize)]
pub struct PatchApprovalElicitRequestParams {
    pub message: String,
    #[serde(rename = "requestedSchema")]
    pub requested_schema: ElicitRequestParamsRequestedSchema,
    pub tunacode_elicitation: String,
    pub tunacode_mcp_tool_call_id: String,
    pub tunacode_event_id: String,
    pub tunacode_call_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tunacode_reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tunacode_grant_root: Option<PathBuf>,
    pub tunacode_changes: HashMap<PathBuf, FileChange>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct PatchApprovalResponse {
    pub decision: ReviewDecision,
}

#[allow(clippy::too_many_arguments)]
pub(crate) async fn handle_patch_approval_request(
    call_id: String,
    reason: Option<String>,
    grant_root: Option<PathBuf>,
    changes: HashMap<PathBuf, FileChange>,
    outgoing: Arc<OutgoingMessageSender>,
    tunacode: Arc<tunacodeConversation>,
    request_id: RequestId,
    tool_call_id: String,
    event_id: String,
) {
    let mut message_lines = Vec::new();
    if let Some(r) = &reason {
        message_lines.push(r.clone());
    }
    message_lines.push("Allow tunacode to apply proposed code changes?".to_string());

    let params = PatchApprovalElicitRequestParams {
        message: message_lines.join("\n"),
        requested_schema: ElicitRequestParamsRequestedSchema {
            r#type: "object".to_string(),
            properties: json!({}),
            required: None,
        },
        tunacode_elicitation: "patch-approval".to_string(),
        tunacode_mcp_tool_call_id: tool_call_id.clone(),
        tunacode_event_id: event_id.clone(),
        tunacode_call_id: call_id,
        tunacode_reason: reason,
        tunacode_grant_root: grant_root,
        tunacode_changes: changes,
    };
    let params_json = match serde_json::to_value(&params) {
        Ok(value) => value,
        Err(err) => {
            let message = format!("Failed to serialize PatchApprovalElicitRequestParams: {err}");
            error!("{message}");

            outgoing
                .send_error(
                    request_id.clone(),
                    JSONRPCErrorError {
                        code: INVALID_PARAMS_ERROR_CODE,
                        message,
                        data: None,
                    },
                )
                .await;

            return;
        }
    };

    let on_response = outgoing
        .send_request(ElicitRequest::METHOD, Some(params_json))
        .await;

    // Listen for the response on a separate task so we don't block the main agent loop.
    {
        let tunacode = tunacode.clone();
        let event_id = event_id.clone();
        tokio::spawn(async move {
            on_patch_approval_response(event_id, on_response, tunacode).await;
        });
    }
}

pub(crate) async fn on_patch_approval_response(
    event_id: String,
    receiver: tokio::sync::oneshot::Receiver<mcp_types::Result>,
    tunacode: Arc<tunacodeConversation>,
) {
    let response = receiver.await;
    let value = match response {
        Ok(value) => value,
        Err(err) => {
            error!("request failed: {err:?}");
            if let Err(submit_err) = tunacode
                .submit(Op::PatchApproval {
                    id: event_id.clone(),
                    decision: ReviewDecision::Denied,
                })
                .await
            {
                error!("failed to submit denied PatchApproval after request failure: {submit_err}");
            }
            return;
        }
    };

    let response = serde_json::from_value::<PatchApprovalResponse>(value).unwrap_or_else(|err| {
        error!("failed to deserialize PatchApprovalResponse: {err}");
        PatchApprovalResponse {
            decision: ReviewDecision::Denied,
        }
    });

    if let Err(err) = tunacode
        .submit(Op::PatchApproval {
            id: event_id,
            decision: response.decision,
        })
        .await
    {
        error!("failed to submit PatchApproval: {err}");
    }
}
