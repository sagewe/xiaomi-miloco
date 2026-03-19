# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""Shared tool invocation contract for Python and Rust runtime integration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
)

TOOL_NAME_CONNECT_CHARS = "___"


@dataclass(frozen=True)
class ParsedToolCall:
    """Normalized tool invocation fields shared by all execution paths."""

    client_id: str
    tool_name: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolInvocationRequest:
    """Rust bridge request payload for invoking a tool through Python."""

    tool_call_id: str
    function_name: str
    arguments: Optional[str]

    @property
    def parsed_tool_call(self) -> ParsedToolCall:
        return parse_tool_invocation(self.function_name, self.arguments)

    @classmethod
    def from_json(cls, payload_json: str) -> "ToolInvocationRequest":
        payload = json.loads(payload_json)
        return cls(
            tool_call_id=payload["tool_call_id"],
            function_name=payload["function_name"],
            arguments=payload.get("arguments"),
        )


@dataclass(frozen=True)
class ToolInvocationResultPayload:
    """Rust bridge response payload returned to the native runtime."""

    tool_call_id: str
    client_id: str
    tool_name: str
    service_name: str
    success: bool
    tool_response: Optional[str]
    error_message: Optional[str]

    def to_json(self) -> str:
        return json.dumps(
            {
                "tool_call_id": self.tool_call_id,
                "client_id": self.client_id,
                "tool_name": self.tool_name,
                "service_name": self.service_name,
                "success": self.success,
                "tool_response": self.tool_response,
                "error_message": self.error_message,
            },
            ensure_ascii=False,
        )


def split_tool_name(function_name: str) -> tuple[str, str]:
    """Split MCP function names of the form client___tool."""
    if TOOL_NAME_CONNECT_CHARS in function_name:
        return tuple(function_name.split(TOOL_NAME_CONNECT_CHARS, 1))
    return "unknown", function_name


def parse_tool_arguments(parameters_str: Optional[str]) -> dict[str, Any]:
    """Parse nested JSON string arguments into a dictionary."""
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

    if isinstance(parameters, dict):
        return parameters
    return {}


def parse_tool_invocation(function_name: str, arguments: Optional[str]) -> ParsedToolCall:
    """Parse a tool invocation from primitive function name and arguments."""
    client_id, tool_name = split_tool_name(function_name)
    return ParsedToolCall(
        client_id=client_id,
        tool_name=tool_name,
        parameters=parse_tool_arguments(arguments),
    )


def parse_openai_tool_call(tool_call: ChatCompletionMessageToolCall) -> ParsedToolCall:
    """Parse an OpenAI tool call object into the shared normalized contract."""
    return parse_tool_invocation(tool_call.function.name, tool_call.function.arguments)
