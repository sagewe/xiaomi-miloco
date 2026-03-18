import json
from contextlib import asynccontextmanager

import pytest
from aiohttp import web

from miloco_server.agent.runtime_bridge import AgentRuntimeBridge
from miloco_server.agent.rust_runtime_adapter import (
    RUNTIME_BACKEND_AUTO,
    RUNTIME_BACKEND_RUST,
    RustRuntimeAdapter,
)
from miloco_server.schema.mcp_schema import CallToolResult


class Bridge:
    def __init__(self, tool_response=None):
        self.events = []
        self.invocations = []
        self.tool_response = tool_response or {
            "tool_call_id": "call_0",
            "client_id": "client",
            "tool_name": "tool",
            "service_name": "Mock Service",
            "success": True,
            "tool_response": json.dumps({"ok": True}),
            "error_message": None,
        }

    def emit_event(self, event_json: str):
        self.events.append(json.loads(event_json))

    async def invoke_tool(self, tool_call_json: str) -> str:
        payload = json.loads(tool_call_json)
        self.invocations.append(payload)
        response = dict(self.tool_response)
        response["tool_call_id"] = payload["tool_call_id"]
        return json.dumps(response)


@asynccontextmanager
async def serve_sse(chunks_by_request, *, status=200, response_text="upstream failure"):
    app = web.Application()
    state = {"requests": []}

    async def handle(request):
        payload = await request.json()
        state["requests"].append(payload)
        if status != 200:
            return web.Response(status=status, text=response_text)
        chunk_index = len(state["requests"]) - 1
        chunks = chunks_by_request[chunk_index]

        response = web.StreamResponse(
            status=200,
            headers={"Content-Type": "text/event-stream"},
        )
        await response.prepare(request)
        for chunk in chunks:
            await response.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
        await response.write(b"data: [DONE]\n\n")
        await response.write_eof()
        return response

    app.router.add_post("/chat/completions", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}", state
    finally:
        await runner.cleanup()


def build_request(base_url, tools=None, *, max_steps=4, planning_model_config=None):
    return json.dumps(
        {
            "request_id": "req-1",
            "session_id": "session-1",
            "query": "hello",
            "max_steps": max_steps,
            "language": "UserLanguage.ENGLISH",
            "messages": [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "hello"},
            ],
            "tools": tools or [],
            "planning_model_config": planning_model_config or {
                "base_url": base_url,
                "api_key": "token",
                "model_name": "demo-model",
            },
        },
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_runtime_streams_content_without_tools():
    miloco_agent_runtime = pytest.importorskip("miloco_agent_runtime")

    chunks = [
        [
            {"choices": [{"delta": {"content": "Hello "}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "world"}, "finish_reason": "stop"}]},
        ]
    ]

    async with serve_sse(chunks) as (base_url, state):
        bridge = Bridge()
        runtime = miloco_agent_runtime.AgentRuntime()
        await runtime.run_nlp_request(build_request(base_url), bridge)

    assert state["requests"][0]["model"] == "demo-model"
    assert [event["type"] for event in bridge.events] == [
        "toast_stream",
        "toast_stream",
        "assistant_step_finalized",
        "dialog_finish",
    ]
    assert bridge.events[-1]["payload"]["success"] is True
    assert bridge.events[2]["payload"]["content"] == "Hello world"


@pytest.mark.asyncio
async def test_runtime_invokes_python_tools_and_continues_loop():
    miloco_agent_runtime = pytest.importorskip("miloco_agent_runtime")

    tool_name = "client___tool"
    tool_schema = [
        {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": "Mock tool",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
            },
        }
    ]
    chunks = [
        [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_0",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": "{\"city\":\"",
                                    },
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": "Paris\"}"},
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        ],
        [
            {"choices": [{"delta": {"content": "Tool finished"}, "finish_reason": "stop"}]},
        ],
    ]

    async with serve_sse(chunks) as (base_url, state):
        bridge = Bridge()
        runtime = miloco_agent_runtime.AgentRuntime()
        await runtime.run_dynamic_execute(build_request(base_url, tool_schema), bridge)

    assert len(state["requests"]) == 2
    assert len(bridge.invocations) == 1
    assert bridge.invocations[0]["function_name"] == tool_name
    assert bridge.events[-1]["payload"]["success"] is True
    assert bridge.events[-2]["payload"]["content"] == "Tool finished"
    second_request_messages = state["requests"][1]["messages"]
    assert any(message.get("role") == "tool" for message in second_request_messages)


def test_auto_backend_falls_back_when_native_module_is_missing(monkeypatch):
    class FakeAgent:
        _request_id = "req-1"

    adapter = RustRuntimeAdapter(FakeAgent())
    adapter._configured_backend = RUNTIME_BACKEND_AUTO
    adapter._load_error = ModuleNotFoundError("missing wheel")

    monkeypatch.setattr(adapter, "_load_runtime_class", lambda: None)

    assert adapter.should_use_rust() is False


def test_rust_backend_raises_when_native_module_is_missing(monkeypatch):
    class FakeAgent:
        _request_id = "req-1"

    adapter = RustRuntimeAdapter(FakeAgent())
    adapter._configured_backend = RUNTIME_BACKEND_RUST
    adapter._load_error = ModuleNotFoundError("missing wheel")

    monkeypatch.setattr(adapter, "_load_runtime_class", lambda: None)

    with pytest.raises(RuntimeError, match="Rust runtime backend is configured"):
        adapter.should_use_rust()


@pytest.mark.asyncio
async def test_agent_runtime_bridge_executes_tools_and_updates_history():
    class FakeToolExecutor:
        def get_server_name(self, client_id):
            assert client_id == "client"
            return "Mock Service"

        async def execute_tool_by_params(self, client_id, tool_name, parameters):
            assert client_id == "client"
            assert tool_name == "tool"
            assert parameters == {"city": "Paris"}
            return CallToolResult(success=True, error_message=None, response={"ok": True})

    class FakeHistory:
        def __init__(self):
            self.assistant_messages = []
            self.tool_messages = []

        def add_assistant_message(self, content, tool_calls):
            self.assistant_messages.append((content, tool_calls))

        def add_tool_call_res_content(self, tool_call_id, tool_name, content):
            self.tool_messages.append((tool_call_id, tool_name, content))

    class FakeAgent:
        def __init__(self):
            self._request_id = "req-1"
            self._tool_executor = FakeToolExecutor()
            self._chat_history_messages = FakeHistory()
            self.instructions = []
            self.post_processed = []

        def _send_instruction(self, payload):
            self.instructions.append(payload)

        def _post_process_tool_call(self, client_id, service_name, tool_name, parameters, result):
            self.post_processed.append(
                (client_id, service_name, tool_name, parameters, result.success)
            )

    agent = FakeAgent()
    bridge = AgentRuntimeBridge(agent)

    bridge.emit_event(
        json.dumps(
            {
                "type": "assistant_step_finalized",
                "payload": {
                    "content": "hello",
                    "tool_calls": [
                        {
                            "id": "call_0",
                            "function_name": "client___tool",
                            "arguments": "{\"city\":\"Paris\"}",
                        }
                    ],
                },
            }
        )
    )

    response = await bridge.invoke_tool(
        json.dumps(
            {
                "tool_call_id": "call_0",
                "function_name": "client___tool",
                "arguments": "{\"city\":\"Paris\"}",
            }
        )
    )
    bridge.emit_event(
        json.dumps(
            {
                "type": "dialog_finish",
                "payload": {"success": True},
            }
        )
    )

    result = json.loads(response)
    assert result["success"] is True
    assert bridge.result.success is True
    assert agent._chat_history_messages.assistant_messages[0][0] == "hello"
    assert agent._chat_history_messages.tool_messages[0] == (
        "call_0",
        "tool",
        json.dumps({"ok": True}),
    )
    assert agent.post_processed[0] == (
        "client",
        "Mock Service",
        "tool",
        {"city": "Paris"},
        True,
    )
    assert [payload.__class__.__name__ for payload in agent.instructions] == [
        "CallTool",
        "CallToolResult",
    ]


@pytest.mark.asyncio
async def test_agent_runtime_bridge_reports_tool_errors_when_executor_raises():
    class FakeToolExecutor:
        def get_server_name(self, client_id):
            assert client_id == "client"
            return "Mock Service"

        async def execute_tool_by_params(self, client_id, tool_name, parameters):
            raise RuntimeError("tool boom")

    class FakeHistory:
        def __init__(self):
            self.tool_messages = []

        def add_tool_call_res_content(self, tool_call_id, tool_name, content):
            self.tool_messages.append((tool_call_id, tool_name, content))

    class FakeAgent:
        def __init__(self):
            self._request_id = "req-1"
            self._tool_executor = FakeToolExecutor()
            self._chat_history_messages = FakeHistory()
            self.instructions = []
            self.post_processed = []

        def _send_instruction(self, payload):
            self.instructions.append(payload)

        def _post_process_tool_call(self, client_id, service_name, tool_name, parameters, result):
            self.post_processed.append(
                (client_id, service_name, tool_name, parameters, result.success)
            )

    bridge = AgentRuntimeBridge(FakeAgent())
    response = await bridge.invoke_tool(
        json.dumps(
            {
                "tool_call_id": "call_0",
                "function_name": "client___tool",
                "arguments": "{\"city\":\"Paris\"}",
            }
        )
    )

    result = json.loads(response)
    assert result["success"] is False
    assert result["error_message"] == "tool boom"
    assert bridge._agent._chat_history_messages.tool_messages[0] == (
        "call_0",
        "tool",
        "tool boom",
    )
    assert bridge._agent.post_processed[0] == (
        "client",
        "Mock Service",
        "tool",
        {"city": "Paris"},
        False,
    )


@pytest.mark.asyncio
async def test_runtime_reports_failure_when_upstream_stream_errors():
    miloco_agent_runtime = pytest.importorskip("miloco_agent_runtime")

    async with serve_sse([], status=500, response_text="upstream failure") as (base_url, state):
        bridge = Bridge()
        runtime = miloco_agent_runtime.AgentRuntime()
        await runtime.run_nlp_request(build_request(base_url), bridge)

    assert len(state["requests"]) == 1
    assert [event["type"] for event in bridge.events] == [
        "dialog_exception",
        "dialog_finish",
    ]
    assert "500" in bridge.events[0]["payload"]["message"]
    assert bridge.events[-1]["payload"]["success"] is False


@pytest.mark.asyncio
async def test_runtime_reports_failure_when_request_contract_is_invalid():
    miloco_agent_runtime = pytest.importorskip("miloco_agent_runtime")

    bridge = Bridge()
    runtime = miloco_agent_runtime.AgentRuntime()
    await runtime.run_nlp_request(
        build_request(
            "http://127.0.0.1:9999",
            planning_model_config={
                "base_url": None,
                "api_key": "token",
                "model_name": "demo-model",
            },
        ),
        bridge,
    )

    assert [event["type"] for event in bridge.events] == [
        "dialog_exception",
        "dialog_finish",
    ]
    assert bridge.events[0]["payload"]["message"].endswith(
        "planning_model_config.base_url is required"
    )
    assert bridge.events[-1]["payload"]["success"] is False


@pytest.mark.asyncio
async def test_runtime_reports_failure_when_max_steps_are_exhausted():
    miloco_agent_runtime = pytest.importorskip("miloco_agent_runtime")

    tool_name = "client___tool"
    tool_schema = [
        {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": "Mock tool",
                "parameters": {"type": "object"},
            },
        }
    ]
    chunks = [
        [
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_0",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": "{\"city\":\"Paris\"}",
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        ],
    ]

    async with serve_sse(chunks) as (base_url, _state):
        bridge = Bridge()
        runtime = miloco_agent_runtime.AgentRuntime()
        await runtime.run_nlp_request(
            build_request(base_url, tool_schema, max_steps=1),
            bridge,
        )

    assert [event["type"] for event in bridge.events] == [
        "assistant_step_finalized",
        "dialog_exception",
        "dialog_finish",
    ]
    assert bridge.events[-1]["payload"]["success"] is False
    assert bridge.events[-1]["payload"]["error_message"].endswith(
        "Maximum operation steps reached"
    )
