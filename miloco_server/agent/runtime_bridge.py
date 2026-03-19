# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""Bridge objects used by the Rust runtime."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
)

from miloco_server.agent.runtime_contract import (
    AssistantStepFinalizedPayload,
    DialogExceptionPayload,
    DialogFinishPayload,
    EVENT_ASSISTANT_STEP_FINALIZED,
    EVENT_DIALOG_EXCEPTION,
    EVENT_DIALOG_FINISH,
    EVENT_TOAST_STREAM,
    EVENT_TOOL_CALL_FINISHED,
    EVENT_TOOL_CALL_STARTED,
    RuntimeEvent,
    ToastStreamPayload,
    ToolCallFinishedPayload,
    ToolCallStartedPayload,
)
from miloco_server.mcp.tool_contract import ToolInvocationRequest, ToolInvocationResultPayload
from miloco_server.schema.chat_schema import Template
from miloco_server.schema.mcp_schema import CallToolResult

logger = logging.getLogger(__name__)

@dataclass
class RuntimeExecutionResult:
    """Final outcome reported by the Rust runtime."""

    success: bool = False
    error_message: Optional[str] = None

class AgentRuntimeBridge:
    """Python callbacks exposed to the Rust runtime."""

    def __init__(self, agent):
        self._agent = agent
        self.result = RuntimeExecutionResult()

    def emit_event(self, event_json: str) -> None:
        """Handle payload-only events emitted by the Rust runtime."""
        event = RuntimeEvent.from_json(event_json)
        event_type = event.event_type
        payload = event.payload

        if event_type == EVENT_TOAST_STREAM:
            toast_payload = ToastStreamPayload.from_payload(payload)
            self._agent._send_instruction(Template.ToastStream(stream=toast_payload.stream))
            return

        if event_type == EVENT_ASSISTANT_STEP_FINALIZED:
            step_payload = AssistantStepFinalizedPayload.from_payload(payload)
            tool_calls = [
                ChatCompletionMessageToolCall(
                    id=tool_call.id,
                    type="function",
                    function={
                        "name": tool_call.function_name,
                        "arguments": tool_call.arguments,
                    },
                )
                for tool_call in step_payload.tool_calls
            ]
            self._agent._chat_history_messages.add_assistant_message(
                step_payload.content,
                tool_calls,
            )
            return

        if event_type == EVENT_TOOL_CALL_STARTED:
            tool_started_payload = ToolCallStartedPayload.from_payload(payload)
            parsed_tool_call = tool_started_payload.parsed_tool_call
            client_id = parsed_tool_call.client_id
            tool_name = parsed_tool_call.tool_name
            service_name = self._agent._tool_executor.get_server_name(client_id)
            self._agent._send_instruction(
                Template.CallTool(
                    id=tool_started_payload.tool_call_id,
                    service_name=service_name,
                    tool_name=tool_name,
                    tool_params=tool_started_payload.arguments,
                )
            )
            return

        if event_type == EVENT_TOOL_CALL_FINISHED:
            self._handle_tool_finished(ToolCallFinishedPayload.from_payload(payload))
            return

        if event_type == EVENT_DIALOG_EXCEPTION:
            self.result.error_message = DialogExceptionPayload.from_payload(payload).message
            return

        if event_type == EVENT_DIALOG_FINISH:
            dialog_finish_payload = DialogFinishPayload.from_payload(payload)
            self.result.success = dialog_finish_payload.success
            if (
                not self.result.success
                and dialog_finish_payload.error_message
                and not self.result.error_message
            ):
                self.result.error_message = dialog_finish_payload.error_message
            return

        logger.warning(
            "[%s] Unknown Rust runtime event type: %s",
            self._agent._request_id,
            event_type,
        )

    async def invoke_tool(self, tool_call_json: str) -> str:
        """Execute a tool call via the existing Python ToolExecutor."""
        request = ToolInvocationRequest.from_json(tool_call_json)
        parsed_tool_call = request.parsed_tool_call
        function_name = request.function_name
        tool_call_id = request.tool_call_id
        client_id = parsed_tool_call.client_id
        tool_name = parsed_tool_call.tool_name
        service_name = self._agent._tool_executor.get_server_name(client_id)
        parameters = parsed_tool_call.parameters

        self._agent._send_instruction(
            Template.CallTool(
                id=tool_call_id,
                service_name=service_name,
                tool_name=tool_name,
                tool_params=request.arguments,
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

        return ToolInvocationResultPayload(
            tool_call_id=tool_call_id,
            client_id=client_id,
            tool_name=tool_name,
            service_name=service_name,
            success=result.success,
            tool_response=response_json,
            error_message=result.error_message,
        ).to_json()

    def _handle_tool_finished(self, payload: ToolCallFinishedPayload) -> None:
        """Support future Rust-side tool execution events without changing the bridge API."""
        parsed_tool_call = payload.parsed_tool_call
        client_id = parsed_tool_call.client_id
        tool_name = parsed_tool_call.tool_name
        service_name = self._agent._tool_executor.get_server_name(client_id)
        result = CallToolResult(
            success=payload.success,
            error_message=payload.error_message,
            response=payload.response,
        )
        response_json = json.dumps(result.response, ensure_ascii=False) if result.response is not None else None
        self._agent._send_instruction(
            Template.CallToolResult(
                id=payload.tool_call_id,
                success=result.success,
                tool_response=response_json,
                error_message=result.error_message,
            )
        )
        tool_call_content = response_json if result.success else result.error_message
        self._agent._chat_history_messages.add_tool_call_res_content(
            payload.tool_call_id,
            tool_name,
            tool_call_content or "",
        )
        self._agent._post_process_tool_call(
            client_id,
            service_name,
            tool_name,
            payload.parameters,
            result,
        )
