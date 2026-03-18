# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""Bridge objects used by the Rust runtime."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
)

from miloco_server.mcp.tool_executor import TOOL_NAME_CONNECT_CHARS
from miloco_server.schema.chat_schema import Template
from miloco_server.schema.mcp_schema import CallToolResult

logger = logging.getLogger(__name__)

EVENT_TOAST_STREAM = "toast_stream"
EVENT_TOOL_CALL_STARTED = "tool_call_started"
EVENT_TOOL_CALL_FINISHED = "tool_call_finished"
EVENT_ASSISTANT_STEP_FINALIZED = "assistant_step_finalized"
EVENT_DIALOG_EXCEPTION = "dialog_exception"
EVENT_DIALOG_FINISH = "dialog_finish"


@dataclass
class RuntimeExecutionResult:
    """Final outcome reported by the Rust runtime."""

    success: bool = False
    error_message: Optional[str] = None


def split_tool_name(function_name: str) -> tuple[str, str]:
    """Split MCP function names of the form client___tool."""
    if TOOL_NAME_CONNECT_CHARS in function_name:
        return tuple(function_name.split(TOOL_NAME_CONNECT_CHARS, 1))
    return "unknown", function_name


def parse_tool_arguments(parameters_str: Optional[str]) -> dict[str, Any]:
    """Mirror ToolExecutor.parse_tool_call JSON parsing without needing a tool call object."""
    if not parameters_str:
        return {}

    parameters: Any = parameters_str
    parse_count = 0
    while isinstance(parameters, str) and parse_count < 5:
        try:
            parameters = json.loads(parameters)
            parse_count += 1
        except json.JSONDecodeError:
            break

    if isinstance(parameters, str):
        return {}
    if isinstance(parameters, dict):
        return parameters
    return {}


class AgentRuntimeBridge:
    """Python callbacks exposed to the Rust runtime."""

    def __init__(self, agent):
        self._agent = agent
        self.result = RuntimeExecutionResult()

    def emit_event(self, event_json: str) -> None:
        """Handle payload-only events emitted by the Rust runtime."""
        event = json.loads(event_json)
        event_type = event["type"]
        payload = event.get("payload", {})

        if event_type == EVENT_TOAST_STREAM:
            self._agent._send_instruction(Template.ToastStream(stream=payload["stream"]))
            return

        if event_type == EVENT_ASSISTANT_STEP_FINALIZED:
            tool_calls = [
                ChatCompletionMessageToolCall(
                    id=tool_call["id"],
                    type="function",
                    function={
                        "name": tool_call["function_name"],
                        "arguments": tool_call["arguments"],
                    },
                )
                for tool_call in payload.get("tool_calls", [])
            ]
            self._agent._chat_history_messages.add_assistant_message(
                payload.get("content", ""),
                tool_calls,
            )
            return

        if event_type == EVENT_TOOL_CALL_STARTED:
            client_id, tool_name = split_tool_name(payload["function_name"])
            service_name = self._agent._tool_executor.get_server_name(client_id)
            self._agent._send_instruction(
                Template.CallTool(
                    id=payload["tool_call_id"],
                    service_name=service_name,
                    tool_name=tool_name,
                    tool_params=payload.get("arguments"),
                )
            )
            return

        if event_type == EVENT_TOOL_CALL_FINISHED:
            self._handle_tool_finished(payload)
            return

        if event_type == EVENT_DIALOG_EXCEPTION:
            self.result.error_message = payload.get("message")
            return

        if event_type == EVENT_DIALOG_FINISH:
            self.result.success = bool(payload.get("success", False))
            if not self.result.success and payload.get("error_message") and not self.result.error_message:
                self.result.error_message = payload["error_message"]
            return

        logger.warning(
            "[%s] Unknown Rust runtime event type: %s",
            self._agent._request_id,
            event_type,
        )

    async def invoke_tool(self, tool_call_json: str) -> str:
        """Execute a tool call via the existing Python ToolExecutor."""
        payload = json.loads(tool_call_json)
        function_name = payload["function_name"]
        tool_call_id = payload["tool_call_id"]
        arguments = payload.get("arguments")
        client_id, tool_name = split_tool_name(function_name)
        service_name = self._agent._tool_executor.get_server_name(client_id)
        parameters = parse_tool_arguments(arguments)

        self._agent._send_instruction(
            Template.CallTool(
                id=tool_call_id,
                service_name=service_name,
                tool_name=tool_name,
                tool_params=arguments,
            )
        )

        try:
            result = await self._agent._tool_executor.execute_tool_by_params(
                client_id=client_id,
                tool_name=tool_name,
                parameters=parameters,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(
                "[%s] Rust runtime tool call failed for %s: %s",
                self._agent._request_id,
                function_name,
                exc,
            )
            result = CallToolResult(success=False, error_message=str(exc), response=None)

        response_json = json.dumps(result.response, ensure_ascii=False) if result.response is not None else None
        self._agent._send_instruction(
            Template.CallToolResult(
                id=tool_call_id,
                success=result.success,
                tool_response=response_json,
                error_message=result.error_message,
            )
        )

        tool_call_content = response_json if result.success else result.error_message
        self._agent._chat_history_messages.add_tool_call_res_content(
            tool_call_id,
            tool_name,
            tool_call_content or "",
        )
        self._agent._post_process_tool_call(
            client_id,
            service_name,
            tool_name,
            parameters,
            result,
        )

        return json.dumps(
            {
                "tool_call_id": tool_call_id,
                "client_id": client_id,
                "tool_name": tool_name,
                "service_name": service_name,
                "success": result.success,
                "tool_response": response_json,
                "error_message": result.error_message,
            },
            ensure_ascii=False,
        )

    def _handle_tool_finished(self, payload: dict[str, Any]) -> None:
        """Support future Rust-side tool execution events without changing the bridge API."""
        client_id, tool_name = split_tool_name(payload["function_name"])
        service_name = self._agent._tool_executor.get_server_name(client_id)
        result = CallToolResult(
            success=payload.get("success", False),
            error_message=payload.get("error_message"),
            response=payload.get("response"),
        )
        response_json = json.dumps(result.response, ensure_ascii=False) if result.response is not None else None
        self._agent._send_instruction(
            Template.CallToolResult(
                id=payload["tool_call_id"],
                success=result.success,
                tool_response=response_json,
                error_message=result.error_message,
            )
        )
        tool_call_content = response_json if result.success else result.error_message
        self._agent._chat_history_messages.add_tool_call_res_content(
            payload["tool_call_id"],
            tool_name,
            tool_call_content or "",
        )
        self._agent._post_process_tool_call(
            client_id,
            service_name,
            tool_name,
            payload.get("parameters") or {},
            result,
        )
