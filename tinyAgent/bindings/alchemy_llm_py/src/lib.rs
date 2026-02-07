use std::collections::HashMap;

use futures::StreamExt;
use once_cell::sync::Lazy;
use pyo3::prelude::*;
use pythonize::{depythonize, pythonize};
use serde::Deserialize;
use serde_json::Value;

use alchemy_llm::types as a;

static RUNTIME: Lazy<tokio::runtime::Runtime> = Lazy::new(|| {
    tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .expect("failed to build tokio runtime")
});

// ------------------------------
// Input types (tinyagent-ish)
// ------------------------------

#[derive(Debug, Clone, Deserialize)]
struct PyModelConfig {
    id: String,
    base_url: String,
    #[serde(default)]
    provider: Option<String>,
    #[serde(default)]
    name: Option<String>,
    #[serde(default)]
    headers: Option<HashMap<String, String>>,
    #[serde(default)]
    reasoning: Option<bool>,
    #[serde(default)]
    context_window: Option<u32>,
    #[serde(default)]
    max_tokens: Option<u32>,
}

#[derive(Debug, Clone, Deserialize)]
struct PyTool {
    name: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    parameters: Value,
}

#[derive(Debug, Clone, Deserialize)]
struct PyContext {
    #[serde(default)]
    system_prompt: String,
    #[serde(default)]
    messages: Vec<PyMessage>,
    #[serde(default)]
    tools: Option<Vec<PyTool>>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "role")]
enum PyMessage {
    #[serde(rename = "user")]
    User {
        #[serde(default)]
        content: Vec<PyUserBlock>,
        #[serde(default)]
        timestamp: Option<i64>,
    },

    #[serde(rename = "assistant")]
    Assistant {
        #[serde(default)]
        content: Vec<Option<PyAssistantBlock>>,
        #[serde(default)]
        stop_reason: Option<String>,
        #[serde(default)]
        timestamp: Option<i64>,
    },

    #[serde(rename = "tool_result")]
    ToolResult {
        tool_call_id: String,
        #[serde(default)]
        tool_name: String,
        #[serde(default)]
        content: Vec<PyUserBlock>,
        #[serde(default)]
        details: Option<Value>,
        #[serde(default)]
        is_error: Option<bool>,
        #[serde(default)]
        timestamp: Option<i64>,
    },
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type")]
enum PyUserBlock {
    #[serde(rename = "text")]
    Text {
        text: String,
        #[serde(default)]
        text_signature: Option<String>,
    },

    // tinyagent uses images as URLs; alchemy-llm expects bytes. We currently reject these.
    #[serde(rename = "image")]
    Image {
        url: String,
        #[serde(default)]
        mime_type: Option<String>,
    },
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type")]
enum PyAssistantBlock {
    #[serde(rename = "text")]
    Text {
        text: String,
        #[serde(default)]
        text_signature: Option<String>,
    },

    #[serde(rename = "thinking")]
    Thinking {
        thinking: String,
        #[serde(default)]
        thinking_signature: Option<String>,
    },

    #[serde(rename = "tool_call")]
    ToolCall {
        #[serde(default)]
        id: String,
        name: String,
        #[serde(default)]
        arguments: Value,
        #[serde(default)]
        partial_json: Option<String>,
    },
}

#[derive(Debug, Clone, Deserialize, Default)]
struct PyOptions {
    #[serde(default)]
    api_key: Option<String>,
    #[serde(default)]
    temperature: Option<f64>,
    #[serde(default)]
    max_tokens: Option<u32>,
}

// ------------------------------
// Conversion helpers
// ------------------------------

fn stop_reason_from_py(s: Option<&str>) -> a::StopReason {
    match s.unwrap_or("") {
        "length" => a::StopReason::Length,
        "tool_calls" | "tool_use" => a::StopReason::ToolUse,
        "error" => a::StopReason::Error,
        "aborted" => a::StopReason::Aborted,
        "complete" | "stop" | "" => a::StopReason::Stop,
        _ => a::StopReason::Stop,
    }
}

fn stop_reason_to_py(sr: a::StopReason) -> &'static str {
    match sr {
        a::StopReason::Stop => "complete",
        a::StopReason::Length => "length",
        a::StopReason::ToolUse => "tool_calls",
        a::StopReason::Error => "error",
        a::StopReason::Aborted => "aborted",
    }
}

fn py_provider_to_alchemy(provider: Option<String>) -> a::Provider {
    let p = provider.unwrap_or_else(|| "custom".to_string());
    p.parse::<a::Provider>().unwrap_or(a::Provider::Custom(p))
}

fn user_blocks_to_text(blocks: &[PyUserBlock]) -> Result<String, String> {
    let mut parts: Vec<String> = Vec::new();
    for b in blocks {
        match b {
            PyUserBlock::Text { text, .. } => parts.push(text.clone()),
            PyUserBlock::Image { url, .. } => {
                return Err(format!(
                    "image blocks are not supported by alchemy_llm_py yet (got url: {url})"
                ));
            }
        }
    }
    Ok(parts.join("\n"))
}

fn assistant_block_to_content(block: &PyAssistantBlock) -> a::Content {
    match block {
        PyAssistantBlock::Text {
            text,
            text_signature,
        } => a::Content::Text {
            inner: a::TextContent {
                text: text.clone(),
                text_signature: text_signature.clone(),
            },
        },
        PyAssistantBlock::Thinking {
            thinking,
            thinking_signature,
        } => a::Content::Thinking {
            inner: a::ThinkingContent {
                thinking: thinking.clone(),
                thinking_signature: thinking_signature.clone(),
            },
        },
        PyAssistantBlock::ToolCall {
            id,
            name,
            arguments,
            ..
        } => a::Content::ToolCall {
            inner: a::ToolCall {
                id: id.clone(),
                name: name.clone(),
                arguments: arguments.clone(),
                thought_signature: None,
            },
        },
    }
}

fn message_to_alchemy(msg: PyMessage, provider: &a::Provider, model_id: &str) -> Result<a::Message, String> {
    match msg {
        PyMessage::User { content, timestamp } => {
            let text = user_blocks_to_text(&content)?;
            Ok(a::Message::User(a::UserMessage {
                content: a::UserContent::Text(text),
                timestamp: timestamp.unwrap_or(0),
            }))
        }
        PyMessage::Assistant {
            content,
            stop_reason,
            timestamp,
        } => {
            let mut out: Vec<a::Content> = Vec::new();
            for b in content.into_iter().flatten() {
                out.push(assistant_block_to_content(&b));
            }

            Ok(a::Message::Assistant(a::AssistantMessage {
                content: out,
                api: a::Api::OpenAICompletions,
                provider: provider.clone(),
                model: model_id.to_string(),
                usage: a::Usage::default(),
                stop_reason: stop_reason_from_py(stop_reason.as_deref()),
                error_message: None,
                timestamp: timestamp.unwrap_or(0),
            }))
        }
        PyMessage::ToolResult {
            tool_call_id,
            tool_name,
            content,
            details,
            is_error,
            timestamp,
        } => {
            let mut out: Vec<a::ToolResultContent> = Vec::new();
            for b in content {
                match b {
                    PyUserBlock::Text { text, text_signature } => {
                        out.push(a::ToolResultContent::Text(a::TextContent {
                            text,
                            text_signature,
                        }));
                    }
                    PyUserBlock::Image { url, .. } => {
                        return Err(format!(
                            "image blocks in tool results are not supported yet (got url: {url})"
                        ));
                    }
                }
            }

            Ok(a::Message::ToolResult(a::ToolResultMessage {
                tool_call_id,
                tool_name,
                content: out,
                details,
                is_error: is_error.unwrap_or(false),
                timestamp: timestamp.unwrap_or(0),
            }))
        }
    }
}

fn content_to_py_value(c: &a::Content) -> Value {
    match c {
        a::Content::Text { inner } => serde_json::json!({
            "type": "text",
            "text": inner.text,
            "text_signature": inner.text_signature,
        }),
        a::Content::Thinking { inner } => serde_json::json!({
            "type": "thinking",
            "thinking": inner.thinking,
            "thinking_signature": inner.thinking_signature,
        }),
        a::Content::ToolCall { inner } => serde_json::json!({
            "type": "tool_call",
            "id": inner.id,
            "name": inner.name,
            "arguments": inner.arguments,
        }),
        a::Content::Image { inner } => serde_json::json!({
            "type": "image",
            "mime_type": inner.mime_type,
            "data_base64": inner.to_base64(),
        }),
    }
}

fn assistant_message_to_py_value(m: &a::AssistantMessage) -> Value {
    serde_json::json!({
        "role": "assistant",
        "content": m.content.iter().map(content_to_py_value).collect::<Vec<_>>(),
        "stop_reason": stop_reason_to_py(m.stop_reason),
        "timestamp": m.timestamp,
        "api": m.api.to_string(),
        "provider": m.provider.to_string(),
        "model": m.model,
        // intentionally omit usage for now (tinyagent doesn't require it)
        "error_message": m.error_message,
    })
}

fn tool_call_to_py_value(tc: &a::ToolCall) -> Value {
    serde_json::json!({
        "type": "tool_call",
        "id": tc.id,
        "name": tc.name,
        "arguments": tc.arguments,
    })
}

fn event_to_py_value(e: &a::AssistantMessageEvent) -> Value {
    use a::AssistantMessageEvent as E;

    match e {
        E::Start { partial } => serde_json::json!({
            "type": "start",
            "partial": assistant_message_to_py_value(partial),
        }),
        E::TextStart {
            content_index,
            partial,
        } => serde_json::json!({
            "type": "text_start",
            "content_index": content_index,
            "partial": assistant_message_to_py_value(partial),
        }),
        E::TextDelta {
            content_index,
            delta,
            partial,
        } => serde_json::json!({
            "type": "text_delta",
            "content_index": content_index,
            "delta": delta,
            "partial": assistant_message_to_py_value(partial),
        }),
        E::TextEnd {
            content_index,
            content,
            partial,
        } => serde_json::json!({
            "type": "text_end",
            "content_index": content_index,
            "content": content,
            "partial": assistant_message_to_py_value(partial),
        }),
        E::ThinkingStart {
            content_index,
            partial,
        } => serde_json::json!({
            "type": "thinking_start",
            "content_index": content_index,
            "partial": assistant_message_to_py_value(partial),
        }),
        E::ThinkingDelta {
            content_index,
            delta,
            partial,
        } => serde_json::json!({
            "type": "thinking_delta",
            "content_index": content_index,
            "delta": delta,
            "partial": assistant_message_to_py_value(partial),
        }),
        E::ThinkingEnd {
            content_index,
            content,
            partial,
        } => serde_json::json!({
            "type": "thinking_end",
            "content_index": content_index,
            "content": content,
            "partial": assistant_message_to_py_value(partial),
        }),
        E::ToolCallStart {
            content_index,
            partial,
        } => serde_json::json!({
            "type": "tool_call_start",
            "content_index": content_index,
            "partial": assistant_message_to_py_value(partial),
        }),
        E::ToolCallDelta {
            content_index,
            delta,
            partial,
        } => serde_json::json!({
            "type": "tool_call_delta",
            "content_index": content_index,
            "delta": delta,
            "partial": assistant_message_to_py_value(partial),
        }),
        E::ToolCallEnd {
            content_index,
            tool_call,
            partial,
        } => serde_json::json!({
            "type": "tool_call_end",
            "content_index": content_index,
            "tool_call": tool_call_to_py_value(tool_call),
            "partial": assistant_message_to_py_value(partial),
        }),
        E::Done { reason, message } => {
            let r = match reason {
                a::StopReasonSuccess::Stop => "stop",
                a::StopReasonSuccess::Length => "length",
                a::StopReasonSuccess::ToolUse => "tool_calls",
            };
            serde_json::json!({
                "type": "done",
                "reason": r,
                "partial": assistant_message_to_py_value(message),
                "message": assistant_message_to_py_value(message),
            })
        }
        E::Error { reason, error } => {
            let r = match reason {
                a::StopReasonError::Error => "error",
                a::StopReasonError::Aborted => "aborted",
            };
            serde_json::json!({
                "type": "error",
                "reason": r,
                "partial": assistant_message_to_py_value(error),
                "error": assistant_message_to_py_value(error),
            })
        }
    }
}

// ------------------------------
// Public Python API
// ------------------------------

type BuildResult = (
    a::Model<a::OpenAICompletions>,
    a::Context,
    alchemy_llm::OpenAICompletionsOptions,
);

fn build_openai_completions_request(
    model: &Bound<'_, PyAny>,
    context: &Bound<'_, PyAny>,
    options: Option<&Bound<'_, PyAny>>,
) -> Result<BuildResult, PyErr> {
    let model_cfg: PyModelConfig = depythonize(model).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("invalid model: {e}"))
    })?;

    let ctx: PyContext = depythonize(context).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("invalid context: {e}"))
    })?;

    let opts: PyOptions = match options {
        Some(o) => depythonize(o).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("invalid options: {e}"))
        })?,
        None => PyOptions::default(),
    };

    let provider = py_provider_to_alchemy(model_cfg.provider.clone());

    let tools: Option<Vec<a::Tool>> = ctx.tools.map(|ts| {
        ts.into_iter()
            .map(|t| a::Tool {
                name: t.name,
                description: t.description,
                parameters: t.parameters,
            })
            .collect()
    });

    let mut messages: Vec<a::Message> = Vec::with_capacity(ctx.messages.len());
    for m in ctx.messages {
        messages.push(message_to_alchemy(m, &provider, &model_cfg.id).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(e)
        })?);
    }

    let system_prompt = if ctx.system_prompt.trim().is_empty() {
        None
    } else {
        Some(ctx.system_prompt)
    };

    let alchemy_ctx = a::Context {
        system_prompt,
        messages,
        tools,
    };

    let alchemy_model: a::Model<a::OpenAICompletions> = a::Model {
        id: model_cfg.id.clone(),
        name: model_cfg.name.unwrap_or_else(|| model_cfg.id.clone()),
        api: a::OpenAICompletions,
        provider: provider.clone(),
        base_url: model_cfg.base_url,
        reasoning: model_cfg.reasoning.unwrap_or(false),
        input: vec![a::InputType::Text],
        cost: a::ModelCost {
            input: 0.0,
            output: 0.0,
            cache_read: 0.0,
            cache_write: 0.0,
        },
        context_window: model_cfg.context_window.unwrap_or(128_000),
        max_tokens: model_cfg.max_tokens.unwrap_or(4096),
        headers: model_cfg.headers,
        compat: None,
    };

    let alchemy_opts = alchemy_llm::OpenAICompletionsOptions {
        api_key: opts.api_key,
        temperature: opts.temperature,
        max_tokens: opts.max_tokens,
        tool_choice: None,
        reasoning_effort: None,
        headers: None,
    };

    Ok((alchemy_model, alchemy_ctx, alchemy_opts))
}

/// Collect an OpenAI-compatible streaming response using alchemy-llm.
///
/// This is a *blocking* function (it runs an internal Tokio runtime). Call it via
/// `asyncio.to_thread(...)` from async Python code.
#[pyfunction]
fn collect_openai_completions(
    py: Python<'_>,
    model: &Bound<'_, PyAny>,
    context: &Bound<'_, PyAny>,
    options: Option<&Bound<'_, PyAny>>,
) -> PyResult<Py<PyAny>> {
    let (alchemy_model, alchemy_ctx, alchemy_opts) =
        build_openai_completions_request(model, context, options)?;

    let res: Result<(Vec<Value>, Value), String> = py.allow_threads(move || {
        RUNTIME.block_on(async move {
            let mut stream = match alchemy_llm::stream(&alchemy_model, &alchemy_ctx, Some(alchemy_opts)) {
                Ok(s) => s,
                Err(e) => return Err(e.to_string()),
            };

            let mut out_events: Vec<Value> = Vec::new();
            let mut terminal: Option<a::AssistantMessage> = None;

            while let Some(ev) = stream.next().await {
                match &ev {
                    a::AssistantMessageEvent::Done { message, .. } => terminal = Some(message.clone()),
                    a::AssistantMessageEvent::Error { error, .. } => terminal = Some(error.clone()),
                    _ => {}
                }
                out_events.push(event_to_py_value(&ev));
            }

            let terminal = terminal.ok_or_else(|| "stream ended without terminal event".to_string())?;
            Ok((out_events, assistant_message_to_py_value(&terminal)))
        })
    });

    let (events, final_message) = match res {
        Ok((v, fm)) => (v, fm),
        Err(e) => {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "alchemy-llm failed: {e}"
            )))
        }
    };

    let result = serde_json::json!({
        "events": events,
        "final_message": final_message,
    });

    pythonize(py, &result)
        .map(|o| o.unbind())
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("failed to convert result: {e}")))
}

#[pyclass]
struct OpenAICompletionsStream {
    rx: std::sync::Mutex<std::sync::mpsc::Receiver<Value>>,
    final_rx: std::sync::Mutex<Option<std::sync::mpsc::Receiver<Value>>>,
    final_message: Option<Value>,
    done: bool,
}

#[pymethods]
impl OpenAICompletionsStream {
    /// Blocking: returns the next event dict, or None when the stream is finished.
    fn next_event(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        if self.done {
            return Ok(None);
        }

        let rx = &self.rx;
        let next: Option<Value> = py.allow_threads(|| rx.lock().ok().and_then(|r| r.recv().ok()));
        match next {
            Some(v) => {
                let obj = pythonize(py, &v)
                    .map(|o| o.unbind())
                    .map_err(|e| {
                        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                            "failed to convert event: {e}"
                        ))
                    })?;
                Ok(Some(obj))
            }
            None => {
                self.done = true;
                Ok(None)
            }
        }
    }

    /// Blocking: returns the final assistant message dict.
    fn result(&mut self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if let Some(v) = &self.final_message {
            return pythonize(py, v)
                .map(|o| o.unbind())
                .map_err(|e| {
                    PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                        "failed to convert final message: {e}"
                    ))
                });
        }

        let rx_opt = self
            .final_rx
            .lock()
            .ok()
            .and_then(|mut guard| guard.take());

        let Some(rx) = rx_opt else {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "final result already consumed",
            ));
        };

        let v: Value = py.allow_threads(move || {
            rx.recv().unwrap_or_else(|_| {
                serde_json::json!({
                    "role": "assistant",
                    "content": [{"type": "text", "text": ""}],
                    "stop_reason": "error",
                    "error_message": "stream ended without final message",
                })
            })
        });

        self.final_message = Some(v.clone());

        pythonize(py, &v)
            .map(|o| o.unbind())
            .map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                    "failed to convert final message: {e}"
                ))
            })
    }
}

/// Start an OpenAI-compatible streaming completion and return a handle.
///
/// Consume events via `handle.next_event()` (blocking) from Python.
#[pyfunction]
fn openai_completions_stream(
    model: &Bound<'_, PyAny>,
    context: &Bound<'_, PyAny>,
    options: Option<&Bound<'_, PyAny>>,
) -> PyResult<OpenAICompletionsStream> {
    let (alchemy_model, alchemy_ctx, alchemy_opts) =
        build_openai_completions_request(model, context, options)?;

    // alchemy-llm providers call `tokio::spawn`, which requires a runtime context.
    let _rt_guard = RUNTIME.enter();

    let mut stream = alchemy_llm::stream(&alchemy_model, &alchemy_ctx, Some(alchemy_opts)).map_err(
        |e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("alchemy-llm failed: {e}")),
    )?;

    let (tx, rx) = std::sync::mpsc::channel::<Value>();
    let (final_tx, final_rx) = std::sync::mpsc::channel::<Value>();

    RUNTIME.spawn(async move {
        let mut terminal: Option<a::AssistantMessage> = None;

        while let Some(ev) = stream.next().await {
            match &ev {
                a::AssistantMessageEvent::Done { message, .. } => terminal = Some(message.clone()),
                a::AssistantMessageEvent::Error { error, .. } => terminal = Some(error.clone()),
                _ => {}
            }

            // Send event to Python
            if tx.send(event_to_py_value(&ev)).is_err() {
                // Python side dropped; stop producing.
                return;
            }

            if matches!(
                ev,
                a::AssistantMessageEvent::Done { .. } | a::AssistantMessageEvent::Error { .. }
            ) {
                break;
            }
        }

        let final_msg = terminal
            .as_ref()
            .map(assistant_message_to_py_value)
            .unwrap_or_else(|| {
                serde_json::json!({
                    "role": "assistant",
                    "content": [{"type": "text", "text": ""}],
                    "stop_reason": "error",
                    "error_message": "stream ended without terminal event",
                })
            });

        let _ = final_tx.send(final_msg);
        // Dropping tx closes the event channel
    });

    Ok(OpenAICompletionsStream {
        rx: std::sync::Mutex::new(rx),
        final_rx: std::sync::Mutex::new(Some(final_rx)),
        final_message: None,
        done: false,
    })
}

#[pymodule]
fn alchemy_llm_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(collect_openai_completions, m)?)?;
    m.add_function(wrap_pyfunction!(openai_completions_stream, m)?)?;
    m.add_class::<OpenAICompletionsStream>()?;
    Ok(())
}
