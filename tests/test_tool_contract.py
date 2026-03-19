import json

import pytest
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
)

from miloco_server.agent.runtime_bridge import AgentRuntimeBridge
from miloco_server.mcp.tool_contract import (
    ParsedToolCall,
    parse_tool_arguments,
    parse_tool_invocation,
    ToolInvocationRequest,
    ToolInvocationResultPayload,
)
from miloco_server.mcp.tool_executor import ToolExecutor
from miloco_server.schema.mcp_schema import CallToolResult


def build_tool_call(function_name: str, arguments: str) -> ChatCompletionMessageToolCall:
    return ChatCompletionMessageToolCall(
        id="call_0",
        type="function",
        function={"name": function_name, "arguments": arguments},
    )


def test_parse_tool_arguments_decodes_nested_json_strings():
    nested_arguments = json.dumps(json.dumps({"city": "Paris"}))

    assert parse_tool_arguments(nested_arguments) == {"city": "Paris"}


@pytest.mark.parametrize("arguments", ["not json", json.dumps("still not an object"), json.dumps([1, 2, 3])])
def test_parse_tool_arguments_returns_empty_dict_for_invalid_values(arguments):
    assert parse_tool_arguments(arguments) == {}


def test_parse_tool_invocation_defaults_missing_client_prefix_to_unknown():
    parsed = parse_tool_invocation("tool", json.dumps({"city": "Paris"}))

    assert parsed == ParsedToolCall(
        client_id="unknown",
        tool_name="tool",
        parameters={"city": "Paris"},
    )


def test_tool_invocation_request_parses_payload_json():
    request = ToolInvocationRequest.from_json(
        json.dumps(
            {
                "tool_call_id": "call_0",
                "function_name": "client___tool",
                "arguments": json.dumps({"city": "Paris"}),
            }
        )
    )

    assert request.tool_call_id == "call_0"
    assert request.parsed_tool_call == ParsedToolCall(
        client_id="client",
        tool_name="tool",
        parameters={"city": "Paris"},
    )


def test_tool_invocation_result_payload_serializes_expected_shape():
    payload = ToolInvocationResultPayload(
        tool_call_id="call_0",
        client_id="client",
        tool_name="tool",
        service_name="Mock Service",
        success=True,
        tool_response=json.dumps({"ok": True}),
        error_message=None,
    )

    assert json.loads(payload.to_json()) == {
        "tool_call_id": "call_0",
        "client_id": "client",
        "tool_name": "tool",
        "service_name": "Mock Service",
        "success": True,
        "tool_response": json.dumps({"ok": True}),
        "error_message": None,
    }


@pytest.mark.asyncio
async def test_runtime_bridge_and_tool_executor_parse_the_same_nested_payload():
    captured = {}
    nested_arguments = json.dumps(json.dumps({"city": "Paris"}))

    class FakeToolExecutor:
        def get_server_name(self, client_id):
            return "Mock Service"

        async def execute_tool_by_params(self, client_id, tool_name, parameters):
            captured["bridge"] = (client_id, tool_name, parameters)
            return CallToolResult(success=True, error_message=None, response={"ok": True})

    class FakeHistory:
        def add_tool_call_res_content(self, *_args):
            return None

    class FakeAgent:
        def __init__(self):
            self._request_id = "req-1"
            self._tool_executor = FakeToolExecutor()
            self._chat_history_messages = FakeHistory()

        def _send_instruction(self, _payload):
            return None

        def _post_process_tool_call(self, *_args):
            return None

    bridge = AgentRuntimeBridge(FakeAgent())
    await bridge.invoke_tool(
        json.dumps(
            {
                "tool_call_id": "call_0",
                "function_name": "client___tool",
                "arguments": nested_arguments,
            }
        )
    )

    executor = ToolExecutor(None)
    parsed = executor.parse_tool_call(build_tool_call("client___tool", nested_arguments))

    assert captured["bridge"] == parsed
