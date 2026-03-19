import asyncio
import json
from types import SimpleNamespace

import pytest

from miloco_server.schema.chat_schema import Template
from miloco_server.service.chat_agent_dispatcher import ChatAgentDispatcher
from miloco_server.service.trigger_rule_dynamic_executor import TriggerRuleDynamicExecutor


class FakeWebSocket:
    def __init__(self):
        self.messages = []
        self.closed = False
        self.client_state = SimpleNamespace(value=1)

    async def send_text(self, message: str):
        self.messages.append(message)

    async def close(self):
        self.closed = True
        self.client_state.value = 3


class FakeChatCompanion:
    def get_chat_history(self, session_id):
        return None

    def store_chat_history(self, storage):
        return None

    def clear_chat_data(self, request_id):
        return None

    def set_chat_data(self, request_id, data):
        return None


class FakeManager:
    def __init__(self):
        self.chat_companion = FakeChatCompanion()


class FakeTriggerRuleLogDAO:
    def get_execute_result(self, request_id):
        return None, None

    def update_execute_result(self, request_id, execute_result):
        return None


class FakeExecuteInfo:
    def __init__(self):
        self.ai_recommend_action_descriptions = []
        self.ai_recommend_execute_type = "dynamic"
        self.mcp_list = []


class FakeTriggerRule:
    def __init__(self):
        self.execute_info = FakeExecuteInfo()
        self.cameras = []


@pytest.mark.asyncio
async def test_chat_agent_dispatcher_schedules_from_worker_thread(monkeypatch):
    fake_manager = FakeManager()
    monkeypatch.setattr(
        "miloco_server.service.manager.get_manager",
        lambda: fake_manager,
    )

    websocket = FakeWebSocket()
    dispatcher = ChatAgentDispatcher(websocket, "req-1", "session-1")

    await asyncio.to_thread(
        dispatcher._handle_instruction_payload,  # pylint: disable=protected-access
        Template.ToastStream(stream="hello from rust"),
    )
    await asyncio.sleep(0)

    assert len(websocket.messages) == 1
    payload = json.loads(websocket.messages[0])
    instruction_payload = json.loads(payload["payload"])
    assert payload["header"]["namespace"] == "Template"
    assert payload["header"]["name"] == "ToastStream"
    assert instruction_payload["stream"] == "hello from rust"


@pytest.mark.asyncio
async def test_trigger_rule_dynamic_executor_schedules_from_worker_thread(monkeypatch):
    fake_manager = FakeManager()
    monkeypatch.setattr(
        "miloco_server.service.manager.get_manager",
        lambda: fake_manager,
    )

    executor = TriggerRuleDynamicExecutor(
        request_id="req-2",
        trigger_rule=FakeTriggerRule(),
        trigger_rule_log_dao=FakeTriggerRuleLogDAO(),
        camera_motion_dict={},
    )
    executor._loop = asyncio.get_running_loop()  # pylint: disable=protected-access
    websocket = FakeWebSocket()
    executor._web_sockets.append(websocket)  # pylint: disable=protected-access

    await asyncio.to_thread(
        executor._handle_instruction_payload,  # pylint: disable=protected-access
        Template.ToastStream(stream="dynamic hello"),
    )
    await asyncio.sleep(0)

    assert len(websocket.messages) == 1
    payload = json.loads(websocket.messages[0])
    instruction_payload = json.loads(payload["payload"])
    assert payload["header"]["namespace"] == "Template"
    assert payload["header"]["name"] == "ToastStream"
    assert instruction_payload["stream"] == "dynamic hello"
