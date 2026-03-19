import json

from miloco_server.agent.runtime_contract import (
    AssistantStepFinalizedPayload,
    AssistantToolCallPayload,
    DialogExceptionPayload,
    DialogFinishPayload,
    EVENT_ASSISTANT_STEP_FINALIZED,
    EVENT_DIALOG_EXCEPTION,
    EVENT_DIALOG_FINISH,
    EVENT_TOAST_STREAM,
    EVENT_TOOL_CALL_FINISHED,
    EVENT_TOOL_CALL_STARTED,
    PlanningModelConfigPayload,
    RuntimeEvent,
    RuntimeRequestPayload,
    ToastStreamPayload,
    ToolCallFinishedPayload,
    ToolCallStartedPayload,
)


def test_runtime_request_payload_serializes_expected_shape():
    payload = RuntimeRequestPayload(
        request_id="req-1",
        session_id="session-1",
        query="hello",
        max_steps=4,
        language="UserLanguage.ENGLISH",
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {"name": "client___tool"}}],
        planning_model_config=PlanningModelConfigPayload(
            base_url="http://127.0.0.1:8000",
            api_key="token",
            model_name="demo-model",
        ),
    )

    assert json.loads(payload.to_json()) == {
        "request_id": "req-1",
        "session_id": "session-1",
        "query": "hello",
        "max_steps": 4,
        "language": "UserLanguage.ENGLISH",
        "messages": [{"role": "user", "content": "hello"}],
        "tools": [{"type": "function", "function": {"name": "client___tool"}}],
        "planning_model_config": {
            "base_url": "http://127.0.0.1:8000",
            "api_key": "token",
            "model_name": "demo-model",
        },
    }


def test_runtime_event_parses_payload_only_envelope():
    event = RuntimeEvent.from_json(
        json.dumps(
            {
                "type": EVENT_TOAST_STREAM,
                "payload": {"stream": "hello"},
            }
        )
    )

    assert event.event_type == EVENT_TOAST_STREAM
    assert event.payload == {"stream": "hello"}


def test_runtime_event_constants_remain_stable():
    assert {
        EVENT_TOAST_STREAM,
        EVENT_TOOL_CALL_STARTED,
        EVENT_TOOL_CALL_FINISHED,
        EVENT_ASSISTANT_STEP_FINALIZED,
        EVENT_DIALOG_EXCEPTION,
        EVENT_DIALOG_FINISH,
    } == {
        "toast_stream",
        "tool_call_started",
        "tool_call_finished",
        "assistant_step_finalized",
        "dialog_exception",
        "dialog_finish",
    }


def test_runtime_event_payload_helpers_parse_expected_shapes():
    assert ToastStreamPayload.from_payload({"stream": "hello"}).stream == "hello"
    assert AssistantStepFinalizedPayload.from_payload(
        {
            "content": "done",
            "tool_calls": [
                {
                    "id": "call_0",
                    "function_name": "client___tool",
                    "arguments": "{\"city\":\"Paris\"}",
                }
            ],
        }
    ) == AssistantStepFinalizedPayload(
        content="done",
        tool_calls=[
            AssistantToolCallPayload(
                id="call_0",
                function_name="client___tool",
                arguments="{\"city\":\"Paris\"}",
            )
        ],
    )


def test_runtime_tool_event_payloads_parse_expected_shapes():
    tool_started = ToolCallStartedPayload.from_payload(
        {
            "tool_call_id": "call_0",
            "function_name": "client___tool",
            "arguments": "{\"city\":\"Paris\"}",
        }
    )
    assert tool_started.parsed_tool_call.client_id == "client"
    assert tool_started.parsed_tool_call.tool_name == "tool"
    assert tool_started.parsed_tool_call.parameters == {"city": "Paris"}

    tool_finished = ToolCallFinishedPayload.from_payload(
        {
            "tool_call_id": "call_0",
            "function_name": "client___tool",
            "success": True,
            "response": {"ok": True},
            "parameters": {"city": "Paris"},
        }
    )
    assert tool_finished.parsed_tool_call.client_id == "client"
    assert tool_finished.parameters == {"city": "Paris"}
    assert tool_finished.response == {"ok": True}


def test_runtime_dialog_payloads_parse_expected_shapes():
    assert DialogExceptionPayload.from_payload({"message": "boom"}).message == "boom"
    assert DialogFinishPayload.from_payload(
        {"success": False, "error_message": "boom"}
    ) == DialogFinishPayload(success=False, error_message="boom")
