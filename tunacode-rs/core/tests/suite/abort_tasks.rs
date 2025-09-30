use std::time::Duration;

use tunacode_core::protocol::EventMsg;
use tunacode_core::protocol::InputItem;
use tunacode_core::protocol::Op;
use core_test_support::responses::ev_function_call;
use core_test_support::responses::mount_sse_once_match;
use core_test_support::responses::sse;
use core_test_support::responses::start_mock_server;
use core_test_support::test_tunacode::test_tunacode;
use core_test_support::wait_for_event_with_timeout;
use serde_json::json;
use wiremock::matchers::body_string_contains;

/// Integration test: spawn a long‑running shell tool via a mocked Responses SSE
/// function call, then interrupt the session and expect TurnAborted.
#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn interrupt_long_running_tool_emits_turn_aborted() {
    let command = vec![
        "bash".to_string(),
        "-lc".to_string(),
        "sleep 60".to_string(),
    ];

    let args = json!({
        "command": command,
        "timeout_ms": 60_000
    })
    .to_string();
    let body = sse(vec![ev_function_call("call_sleep", "shell", &args)]);

    let server = start_mock_server().await;
    mount_sse_once_match(&server, body_string_contains("start sleep"), body).await;

    let tunacode = test_tunacode().build(&server).await.unwrap().tunacode;

    let wait_timeout = Duration::from_secs(5);

    // Kick off a turn that triggers the function call.
    tunacode
        .submit(Op::UserInput {
            items: vec![InputItem::Text {
                text: "start sleep".into(),
            }],
        })
        .await
        .unwrap();

    // Wait until the exec begins to avoid a race, then interrupt.
    wait_for_event_with_timeout(
        &tunacode,
        |ev| matches!(ev, EventMsg::ExecCommandBegin(_)),
        wait_timeout,
    )
    .await;

    tunacode.submit(Op::Interrupt).await.unwrap();

    // Expect TurnAborted soon after.
    wait_for_event_with_timeout(
        &tunacode,
        |ev| matches!(ev, EventMsg::TurnAborted(_)),
        wait_timeout,
    )
    .await;
}
