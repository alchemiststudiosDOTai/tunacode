use crate::tunacode::tunacode;
use crate::error::Result as tunacodeResult;
use crate::protocol::Event;
use crate::protocol::Op;
use crate::protocol::Submission;

pub struct tunacodeConversation {
    tunacode: tunacode,
}

/// Conduit for the bidirectional stream of messages that compose a conversation
/// in tunacode.
impl tunacodeConversation {
    pub(crate) fn new(tunacode: tunacode) -> Self {
        Self { tunacode }
    }

    pub async fn submit(&self, op: Op) -> tunacodeResult<String> {
        self.tunacode.submit(op).await
    }

    /// Use sparingly: this is intended to be removed soon.
    pub async fn submit_with_id(&self, sub: Submission) -> tunacodeResult<()> {
        self.tunacode.submit_with_id(sub).await
    }

    pub async fn next_event(&self) -> tunacodeResult<Event> {
        self.tunacode.next_event().await
    }
}
