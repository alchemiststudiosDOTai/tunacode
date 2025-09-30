use std::sync::Arc;

use tunacode_core::tunacodeConversation;
use tunacode_core::ConversationManager;
use tunacode_core::NewConversation;
use tunacode_core::config::Config;
use tunacode_core::protocol::Op;
use tokio::sync::mpsc::UnboundedSender;
use tokio::sync::mpsc::unbounded_channel;

use crate::app_event::AppEvent;
use crate::app_event_sender::AppEventSender;

/// Spawn the agent bootstrapper and op forwarding loop, returning the
/// `UnboundedSender<Op>` used by the UI to submit operations.
pub(crate) fn spawn_agent(
    config: Config,
    app_event_tx: AppEventSender,
    server: Arc<ConversationManager>,
) -> UnboundedSender<Op> {
    let (tunacode_op_tx, mut tunacode_op_rx) = unbounded_channel::<Op>();

    let app_event_tx_clone = app_event_tx;
    tokio::spawn(async move {
        let NewConversation {
            conversation_id: _,
            conversation,
            session_configured,
        } = match server.new_conversation(config).await {
            Ok(v) => v,
            Err(e) => {
                // TODO: surface this error to the user.
                tracing::error!("failed to initialize tunacode: {e}");
                return;
            }
        };

        // Forward the captured `SessionConfigured` event so it can be rendered in the UI.
        let ev = tunacode_core::protocol::Event {
            // The `id` does not matter for rendering, so we can use a fake value.
            id: "".to_string(),
            msg: tunacode_core::protocol::EventMsg::SessionConfigured(session_configured),
        };
        app_event_tx_clone.send(AppEvent::TunacodeEvent(ev));

        let conversation_clone = conversation.clone();
        tokio::spawn(async move {
            while let Some(op) = tunacode_op_rx.recv().await {
                let id = conversation_clone.submit(op).await;
                if let Err(e) = id {
                    tracing::error!("failed to submit op: {e}");
                }
            }
        });

        while let Ok(event) = conversation.next_event().await {
            app_event_tx_clone.send(AppEvent::TunacodeEvent(event));
        }
    });

    tunacode_op_tx
}

/// Spawn agent loops for an existing conversation (e.g., a forked conversation).
/// Sends the provided `SessionConfiguredEvent` immediately, then forwards subsequent
/// events and accepts Ops for submission.
pub(crate) fn spawn_agent_from_existing(
    conversation: std::sync::Arc<tunacodeConversation>,
    session_configured: tunacode_core::protocol::SessionConfiguredEvent,
    app_event_tx: AppEventSender,
) -> UnboundedSender<Op> {
    let (tunacode_op_tx, mut tunacode_op_rx) = unbounded_channel::<Op>();

    let app_event_tx_clone = app_event_tx;
    tokio::spawn(async move {
        // Forward the captured `SessionConfigured` event so it can be rendered in the UI.
        let ev = tunacode_core::protocol::Event {
            id: "".to_string(),
            msg: tunacode_core::protocol::EventMsg::SessionConfigured(session_configured),
        };
        app_event_tx_clone.send(AppEvent::TunacodeEvent(ev));

        let conversation_clone = conversation.clone();
        tokio::spawn(async move {
            while let Some(op) = tunacode_op_rx.recv().await {
                let id = conversation_clone.submit(op).await;
                if let Err(e) = id {
                    tracing::error!("failed to submit op: {e}");
                }
            }
        });

        while let Ok(event) = conversation.next_event().await {
            app_event_tx_clone.send(AppEvent::TunacodeEvent(event));
        }
    });

    tunacode_op_tx
}
