# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""Adapter layer between ChatAgent and the optional Rust runtime."""

from __future__ import annotations

import importlib
import json
import logging
from typing import Any

from miloco_server.config import CHAT_CONFIG
from miloco_server.middleware.exceptions import ResourceNotFoundException
from miloco_server.utils.local_models import ModelPurpose

from miloco_server.agent.runtime_bridge import AgentRuntimeBridge

logger = logging.getLogger(__name__)

RUNTIME_BACKEND_PYTHON = "python"
RUNTIME_BACKEND_RUST = "rust"
RUNTIME_BACKEND_AUTO = "auto"
SUPPORTED_RUNTIME_BACKENDS = {
    RUNTIME_BACKEND_PYTHON,
    RUNTIME_BACKEND_RUST,
    RUNTIME_BACKEND_AUTO,
}


def _to_jsonable(value: Any) -> Any:
    """Convert SDK and Pydantic objects into plain JSON-compatible values."""
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


class RustRuntimeAdapter:
    """Lazy wrapper around the optional `miloco_agent_runtime` wheel."""

    def __init__(self, agent):
        self._agent = agent
        configured_backend = CHAT_CONFIG.get("agent_runtime_backend", RUNTIME_BACKEND_PYTHON)
        if configured_backend not in SUPPORTED_RUNTIME_BACKENDS:
            logger.warning(
                "Unsupported chat.agent_runtime_backend=%s, falling back to python",
                configured_backend,
            )
            configured_backend = RUNTIME_BACKEND_PYTHON
        self._configured_backend = configured_backend
        self._runtime_cls = None
        self._load_error: Exception | None = None

    @property
    def configured_backend(self) -> str:
        """Return the configured backend name."""
        return self._configured_backend

    def should_use_rust(self) -> bool:
        """Resolve backend selection with `auto` fallback semantics."""
        if self._configured_backend == RUNTIME_BACKEND_PYTHON:
            return False
        if self._load_runtime_class() is not None:
            return True
        if self._configured_backend == RUNTIME_BACKEND_AUTO:
            logger.warning(
                "[%s] Rust runtime unavailable, falling back to Python backend: %s",
                self._agent._request_id,
                self._load_error,
            )
            return False
        raise RuntimeError(
            "Rust runtime backend is configured but the native module could not be loaded"
        ) from self._load_error

    async def run(self, query: str, request_kind: str) -> tuple[bool, str | None]:
        """Execute a chat request through the native runtime."""
        runtime_cls = self._load_runtime_class()
        if runtime_cls is None:
            raise RuntimeError("Rust runtime module is not available") from self._load_error

        bridge = AgentRuntimeBridge(self._agent)
        runtime = runtime_cls()
        request_json = json.dumps(self._build_request_payload(query), ensure_ascii=False)

        if request_kind == "dynamic_execute":
            await runtime.run_dynamic_execute(request_json, bridge)
        else:
            await runtime.run_nlp_request(request_json, bridge)

        return bridge.result.success, bridge.result.error_message

    def _build_request_payload(self, query: str) -> dict[str, Any]:
        """Build the JSON contract consumed by the Rust runtime."""
        llm_proxy = self._agent._manager.get_llm_proxy_by_purpose(ModelPurpose.PLANNING)
        if llm_proxy is None:
            raise ResourceNotFoundException(
                "Planning model not exit, Please configure on the Model Settings Page"
            )

        return {
            "request_id": self._agent._request_id,
            "session_id": getattr(self._agent, "_session_id", self._agent._request_id),
            "query": query,
            "max_steps": self._agent._max_steps,
            "language": str(self._agent._language),
            "messages": _to_jsonable(self._agent._chat_history_messages.get_messages()),
            "tools": _to_jsonable(self._agent._all_mcp_tools_meta),
            "planning_model_config": {
                "base_url": getattr(llm_proxy, "base_url", None),
                "api_key": getattr(llm_proxy, "api_key", None),
                "model_name": getattr(llm_proxy, "model_name", None),
            },
        }

    def _load_runtime_class(self):
        """Import the wheel lazily to keep the Python fallback path cheap."""
        if self._runtime_cls is not None:
            return self._runtime_cls
        if self._load_error is not None:
            return None

        try:
            module = importlib.import_module("miloco_agent_runtime")
            self._runtime_cls = module.AgentRuntime
            return self._runtime_cls
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._load_error = exc
            return None
