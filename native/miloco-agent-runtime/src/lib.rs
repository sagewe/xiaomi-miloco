use futures_util::StreamExt;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyModule;
use reqwest::Client;
use reqwest_eventsource::{Event, EventSource};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeMap;

#[allow(dead_code)]
#[derive(Debug, Clone, Deserialize)]
struct RuntimeRequest {
    request_id: String,
    session_id: String,
    query: String,
    max_steps: usize,
    language: String,
    messages: Vec<Value>,
    tools: Vec<Value>,
    planning_model_config: PlanningModelConfig,
}

#[derive(Debug, Clone, Deserialize)]
struct PlanningModelConfig {
    base_url: Option<String>,
    api_key: Option<String>,
    model_name: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct StreamChunk {
    choices: Vec<StreamChoice>,
}

#[derive(Debug, Clone, Deserialize)]
struct StreamChoice {
    delta: StreamDelta,
    finish_reason: Option<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
struct StreamDelta {
    content: Option<String>,
    tool_calls: Option<Vec<DeltaToolCall>>,
}

#[derive(Debug, Clone, Default, Deserialize)]
struct DeltaToolCall {
    index: Option<usize>,
    id: Option<String>,
    function: Option<DeltaToolFunction>,
}

#[derive(Debug, Clone, Default, Deserialize)]
struct DeltaToolFunction {
    name: Option<String>,
    arguments: Option<String>,
}

#[derive(Debug, Clone, Default)]
struct AggregatedToolCall {
    id: Option<String>,
    function_name: Option<String>,
    arguments: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
struct FinalizedToolCall {
    id: String,
    function_name: String,
    arguments: String,
}

#[derive(Debug, Clone, Serialize)]
struct RuntimeEvent<'a, T>
where
    T: Serialize,
{
    #[serde(rename = "type")]
    event_type: &'a str,
    payload: T,
}

#[derive(Debug, Clone, Serialize)]
struct ToastStreamPayload<'a> {
    stream: &'a str,
}

#[derive(Debug, Clone, Serialize)]
struct AssistantStepFinalizedPayload {
    content: String,
    tool_calls: Vec<FinalizedToolCall>,
}

#[derive(Debug, Clone, Serialize)]
struct DialogExceptionPayload<'a> {
    message: &'a str,
}

#[derive(Debug, Clone, Serialize)]
struct DialogFinishPayload<'a> {
    success: bool,
    error_message: Option<&'a str>,
}

#[derive(Debug, Clone, Serialize)]
struct ToolCallPayload<'a> {
    tool_call_id: &'a str,
    function_name: &'a str,
    arguments: &'a str,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Deserialize)]
struct ToolInvocationResult {
    tool_call_id: String,
    client_id: String,
    tool_name: String,
    service_name: String,
    success: bool,
    tool_response: Option<String>,
    error_message: Option<String>,
}

#[pyclass]
struct AgentRuntime;

#[pymethods]
impl AgentRuntime {
    #[new]
    fn new() -> Self {
        Self
    }

    fn run_nlp_request<'py>(
        &self,
        py: Python<'py>,
        request_json: String,
        bridge: Py<PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            run_runtime(request_json, bridge).await;
            Ok(())
        })
    }

    fn run_dynamic_execute<'py>(
        &self,
        py: Python<'py>,
        request_json: String,
        bridge: Py<PyAny>,
    ) -> PyResult<Bound<'py, PyAny>> {
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            run_runtime(request_json, bridge).await;
            Ok(())
        })
    }
}

async fn run_runtime(request_json: String, bridge: Py<PyAny>) {
    let result = async {
        let request: RuntimeRequest = serde_json::from_str(&request_json).map_err(runtime_error)?;
        validate_request(&request)?;
        execute_request(request, &bridge).await
    }
    .await;

    match result {
        Ok(()) => {
            let _ = emit_event(
                &bridge,
                RuntimeEvent {
                    event_type: "dialog_finish",
                    payload: DialogFinishPayload {
                        success: true,
                        error_message: None,
                    },
                },
            );
        }
        Err(err) => {
            let error_text = err.to_string();
            let _ = emit_event(
                &bridge,
                RuntimeEvent {
                    event_type: "dialog_exception",
                    payload: DialogExceptionPayload {
                        message: error_text.as_str(),
                    },
                },
            );
            let _ = emit_event(
                &bridge,
                RuntimeEvent {
                    event_type: "dialog_finish",
                    payload: DialogFinishPayload {
                        success: false,
                        error_message: Some(error_text.as_str()),
                    },
                },
            );
        }
    }
}

fn validate_request(request: &RuntimeRequest) -> PyResult<()> {
    if request.max_steps == 0 {
        return Err(runtime_error("max_steps must be greater than 0"));
    }
    if request
        .planning_model_config
        .base_url
        .as_deref()
        .unwrap_or("")
        .is_empty()
    {
        return Err(runtime_error("planning_model_config.base_url is required"));
    }
    if request
        .planning_model_config
        .api_key
        .as_deref()
        .unwrap_or("")
        .is_empty()
    {
        return Err(runtime_error("planning_model_config.api_key is required"));
    }
    if request
        .planning_model_config
        .model_name
        .as_deref()
        .unwrap_or("")
        .is_empty()
    {
        return Err(runtime_error(
            "planning_model_config.model_name is required",
        ));
    }
    Ok(())
}

async fn execute_request(request: RuntimeRequest, bridge: &Py<PyAny>) -> PyResult<()> {
    let client = Client::builder().build().map_err(runtime_error)?;
    let mut messages = request.messages.clone();

    for _ in 0..request.max_steps {
        let step_result = execute_step(&client, &request, &messages, bridge).await?;
        messages.push(step_result.assistant_message);

        if step_result.tool_messages.is_empty() {
            if step_result.finish_reason.as_deref() == Some("stop") {
                return Ok(());
            }
        } else {
            messages.extend(step_result.tool_messages);
        }
    }

    Err(runtime_error("Maximum operation steps reached"))
}

struct StepResult {
    finish_reason: Option<String>,
    assistant_message: Value,
    tool_messages: Vec<Value>,
}

async fn execute_step(
    client: &Client,
    request: &RuntimeRequest,
    messages: &[Value],
    bridge: &Py<PyAny>,
) -> PyResult<StepResult> {
    let request_body = json!({
        "model": request.planning_model_config.model_name,
        "messages": messages,
        "stream": true,
        "tools": request.tools,
        "temperature": 0,
    });

    let endpoint = chat_completions_endpoint(
        request
            .planning_model_config
            .base_url
            .as_deref()
            .unwrap_or_default(),
    );

    let request_builder = client
        .post(endpoint)
        .bearer_auth(
            request
                .planning_model_config
                .api_key
                .as_deref()
                .unwrap_or_default(),
        )
        .json(&request_body);

    let mut event_source = EventSource::new(request_builder).map_err(runtime_error)?;
    let mut chunk_content_cache: Vec<String> = Vec::new();
    let mut aggregated_tool_calls: BTreeMap<usize, AggregatedToolCall> = BTreeMap::new();
    let mut finish_reason: Option<String> = None;

    while let Some(event) = event_source.next().await {
        match event {
            Ok(Event::Open) => {}
            Ok(Event::Message(message)) => {
                if message.data == "[DONE]" {
                    break;
                }

                let chunk: StreamChunk =
                    serde_json::from_str(&message.data).map_err(runtime_error)?;
                let choice = chunk
                    .choices
                    .first()
                    .ok_or_else(|| runtime_error("No choices in LLM response"))?;

                if let Some(content_stream) = choice.delta.content.as_deref() {
                    if !content_stream.is_empty() {
                        chunk_content_cache.push(content_stream.to_owned());
                        emit_event(
                            bridge,
                            RuntimeEvent {
                                event_type: "toast_stream",
                                payload: ToastStreamPayload {
                                    stream: content_stream,
                                },
                            },
                        )?;
                    }
                }

                if let Some(tool_calls) = choice.delta.tool_calls.as_ref() {
                    merge_tool_calls(&mut aggregated_tool_calls, tool_calls);
                }

                if let Some(current_finish_reason) = choice.finish_reason.as_ref() {
                    if !current_finish_reason.is_empty() {
                        finish_reason = Some(current_finish_reason.clone());
                        break;
                    }
                }
            }
            Err(err) => return Err(runtime_error(err)),
        }
    }

    event_source.close();

    let finalized_content = chunk_content_cache.join("");
    let finalized_tool_calls = finalize_tool_calls(&aggregated_tool_calls);

    emit_event(
        bridge,
        RuntimeEvent {
            event_type: "assistant_step_finalized",
            payload: AssistantStepFinalizedPayload {
                content: finalized_content.clone(),
                tool_calls: finalized_tool_calls.clone(),
            },
        },
    )?;

    let assistant_message = build_assistant_message(&finalized_content, &finalized_tool_calls);
    let tool_messages = invoke_tools(bridge, finalized_tool_calls).await?;

    Ok(StepResult {
        finish_reason,
        assistant_message,
        tool_messages,
    })
}

async fn invoke_tools(
    bridge: &Py<PyAny>,
    tool_calls: Vec<FinalizedToolCall>,
) -> PyResult<Vec<Value>> {
    let mut tool_messages = Vec::new();

    for tool_call in tool_calls {
        let payload = ToolCallPayload {
            tool_call_id: tool_call.id.as_str(),
            function_name: tool_call.function_name.as_str(),
            arguments: tool_call.arguments.as_str(),
        };
        let result = invoke_tool(bridge, payload).await?;
        let tool_content = if result.success {
            result.tool_response.unwrap_or_else(|| "null".to_owned())
        } else {
            result.error_message.unwrap_or_default()
        };
        tool_messages.push(json!({
            "role": "tool",
            "tool_call_id": result.tool_call_id,
            "name": result.tool_name,
            "content": tool_content,
        }));
    }

    Ok(tool_messages)
}

async fn invoke_tool(
    bridge: &Py<PyAny>,
    payload: ToolCallPayload<'_>,
) -> PyResult<ToolInvocationResult> {
    let payload_json = serde_json::to_string(&payload).map_err(runtime_error)?;
    let py_future = Python::attach(|py| {
        let awaitable = bridge.call_method1(py, "invoke_tool", (payload_json,))?;
        pyo3_async_runtimes::tokio::into_future(awaitable.into_bound(py))
    })?;

    let response_object = py_future.await?;
    let response_json: String = Python::attach(|py| response_object.extract(py))?;
    serde_json::from_str(&response_json).map_err(runtime_error)
}

fn emit_event<T>(bridge: &Py<PyAny>, event: RuntimeEvent<'_, T>) -> PyResult<()>
where
    T: Serialize,
{
    let event_json = serde_json::to_string(&event).map_err(runtime_error)?;
    Python::attach(|py| {
        bridge.call_method1(py, "emit_event", (event_json,))?;
        Ok(())
    })
}

fn build_assistant_message(content: &str, tool_calls: &[FinalizedToolCall]) -> Value {
    if tool_calls.is_empty() {
        json!({
            "role": "assistant",
            "content": content,
        })
    } else {
        json!({
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls.iter().map(|tool_call| {
                json!({
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function_name,
                        "arguments": tool_call.arguments,
                    },
                })
            }).collect::<Vec<_>>(),
        })
    }
}

fn merge_tool_calls(
    aggregated_calls: &mut BTreeMap<usize, AggregatedToolCall>,
    chunk_tool_calls: &[DeltaToolCall],
) {
    for delta_tool_call in chunk_tool_calls {
        let call_index = delta_tool_call.index.unwrap_or(0);
        let current = aggregated_calls.entry(call_index).or_default();

        if let Some(delta_id) = delta_tool_call.id.as_ref() {
            current.id = Some(delta_id.clone());
        }

        if let Some(delta_function) = delta_tool_call.function.as_ref() {
            if let Some(delta_name) = delta_function.name.as_ref() {
                current.function_name = Some(delta_name.clone());
            }
            if let Some(delta_arguments) = delta_function.arguments.as_ref() {
                current.arguments.push_str(delta_arguments);
            }
        }
    }
}

fn finalize_tool_calls(
    aggregated_calls: &BTreeMap<usize, AggregatedToolCall>,
) -> Vec<FinalizedToolCall> {
    aggregated_calls
        .iter()
        .map(|(call_index, call)| FinalizedToolCall {
            id: call
                .id
                .clone()
                .unwrap_or_else(|| format!("call_{}", call_index)),
            function_name: call.function_name.clone().unwrap_or_default(),
            arguments: call.arguments.clone(),
        })
        .collect()
}

fn chat_completions_endpoint(base_url: &str) -> String {
    format!("{}/chat/completions", base_url.trim_end_matches('/'))
}

fn runtime_error<E>(error: E) -> PyErr
where
    E: std::fmt::Display,
{
    PyRuntimeError::new_err(error.to_string())
}

#[pymodule]
fn miloco_agent_runtime(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<AgentRuntime>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use pretty_assertions::assert_eq;

    #[test]
    fn merges_tool_call_deltas_in_order() {
        let mut aggregated = BTreeMap::new();
        merge_tool_calls(
            &mut aggregated,
            &[DeltaToolCall {
                index: Some(0),
                id: Some("call_0".to_owned()),
                function: Some(DeltaToolFunction {
                    name: Some("client___tool".to_owned()),
                    arguments: Some("{\"foo\":".to_owned()),
                }),
            }],
        );
        merge_tool_calls(
            &mut aggregated,
            &[DeltaToolCall {
                index: Some(0),
                id: None,
                function: Some(DeltaToolFunction {
                    name: None,
                    arguments: Some("\"bar\"}".to_owned()),
                }),
            }],
        );

        assert_eq!(
            finalize_tool_calls(&aggregated),
            vec![FinalizedToolCall {
                id: "call_0".to_owned(),
                function_name: "client___tool".to_owned(),
                arguments: "{\"foo\":\"bar\"}".to_owned(),
            }]
        );
    }

    #[test]
    fn generates_default_call_id_when_missing() {
        let mut aggregated = BTreeMap::new();
        merge_tool_calls(
            &mut aggregated,
            &[DeltaToolCall {
                index: Some(3),
                id: None,
                function: Some(DeltaToolFunction {
                    name: Some("client___tool".to_owned()),
                    arguments: Some("{}".to_owned()),
                }),
            }],
        );

        assert_eq!(
            finalize_tool_calls(&aggregated),
            vec![FinalizedToolCall {
                id: "call_3".to_owned(),
                function_name: "client___tool".to_owned(),
                arguments: "{}".to_owned(),
            }]
        );
    }
}
