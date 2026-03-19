# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""Shared Python-side contract for Rust runtime requests and events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from miloco_server.mcp.tool_contract import ParsedToolCall, parse_tool_invocation

EVENT_TOAST_STREAM = "toast_stream"
EVENT_TOOL_CALL_STARTED = "tool_call_started"
EVENT_TOOL_CALL_FINISHED = "tool_call_finished"
EVENT_ASSISTANT_STEP_FINALIZED = "assistant_step_finalized"
EVENT_DIALOG_EXCEPTION = "dialog_exception"
EVENT_DIALOG_FINISH = "dialog_finish"


def to_jsonable(value: Any) -> Any:
    """Convert SDK and Pydantic objects into plain JSON-compatible values."""
    if hasattr(value, "model_dump"):
        return to_jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


@dataclass(frozen=True)
class PlanningModelConfigPayload:
    """Planning model configuration passed to the Rust runtime."""

    base_url: str | None
    api_key: str | None
    model_name: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "model_name": self.model_name,
        }


@dataclass(frozen=True)
class RuntimeRequestPayload:
    """Request payload consumed by the Rust runtime."""

    request_id: str
    session_id: str
    query: str
    max_steps: int
    language: str
    messages: list[Any]
    tools: list[Any]
    planning_model_config: PlanningModelConfigPayload

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "query": self.query,
            "max_steps": self.max_steps,
            "language": self.language,
            "messages": self.messages,
            "tools": self.tools,
            "planning_model_config": self.planning_model_config.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass(frozen=True)
class RuntimeEvent:
    """Payload-only event envelope emitted by the Rust runtime."""

    event_type: str
    payload: dict[str, Any]

    @classmethod
    def from_json(cls, event_json: str) -> "RuntimeEvent":
        event = json.loads(event_json)
        return cls(
            event_type=event["type"],
            payload=event.get("payload", {}),
        )


@dataclass(frozen=True)
class ToastStreamPayload:
    stream: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ToastStreamPayload":
        return cls(stream=payload["stream"])


@dataclass(frozen=True)
class AssistantToolCallPayload:
    id: str
    function_name: str
    arguments: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "AssistantToolCallPayload":
        return cls(
            id=payload["id"],
            function_name=payload["function_name"],
            arguments=payload["arguments"],
        )


@dataclass(frozen=True)
class AssistantStepFinalizedPayload:
    content: str
    tool_calls: list[AssistantToolCallPayload]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "AssistantStepFinalizedPayload":
        return cls(
            content=payload.get("content", ""),
            tool_calls=[
                AssistantToolCallPayload.from_payload(tool_call)
                for tool_call in payload.get("tool_calls", [])
            ],
        )


@dataclass(frozen=True)
class ToolCallStartedPayload:
    tool_call_id: str
    function_name: str
    arguments: str | None

    @property
    def parsed_tool_call(self) -> ParsedToolCall:
        return parse_tool_invocation(self.function_name, self.arguments)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ToolCallStartedPayload":
        return cls(
            tool_call_id=payload["tool_call_id"],
            function_name=payload["function_name"],
            arguments=payload.get("arguments"),
        )


@dataclass(frozen=True)
class ToolCallFinishedPayload:
    tool_call_id: str
    function_name: str
    success: bool
    error_message: str | None
    response: Any
    parameters: dict[str, Any]

    @property
    def parsed_tool_call(self) -> ParsedToolCall:
        return parse_tool_invocation(self.function_name, None)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ToolCallFinishedPayload":
        return cls(
            tool_call_id=payload["tool_call_id"],
            function_name=payload["function_name"],
            success=bool(payload.get("success", False)),
            error_message=payload.get("error_message"),
            response=payload.get("response"),
            parameters=payload.get("parameters") or {},
        )


@dataclass(frozen=True)
class DialogExceptionPayload:
    message: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "DialogExceptionPayload":
        return cls(message=payload.get("message"))


@dataclass(frozen=True)
class DialogFinishPayload:
    success: bool
    error_message: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "DialogFinishPayload":
        return cls(
            success=bool(payload.get("success", False)),
            error_message=payload.get("error_message"),
        )
