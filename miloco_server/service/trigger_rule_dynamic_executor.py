# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""
Trigger rule dynamic executor module
"""
import logging
import asyncio
from typing import Optional

from fastapi import WebSocket
from miloco_server.schema.miot_schema import CameraImgSeq

from miloco_server.dao.trigger_rule_log_dao import TriggerRuleLogDAO
from miloco_server.utils.chat_companion import ChatCachedData
from miloco_server.agent.dynamic_execute_agent import ActionDescriptionDynamicExecuteAgent
from miloco_server.schema.chat_schema import Event, Instruction, InstructionPayload, Internal, Nlp, Confirmation
from miloco_server.schema.chat_history_schema import ChatHistorySession
from miloco_server.schema.trigger_log_schema import AiRecommendDynamicExecuteResult, ExecuteResult
from miloco_server.schema.trigger_schema import TriggerRule

logger = logging.getLogger(__name__)


class TriggerRuleDynamicExecutor:
    """
    TriggerRuleDynamicExecutor - runs an ActionDescriptionDynamicExecuteAgent for a trigger rule
    and collects session history for later retrieval.
    """

    def __init__(self,
                 request_id: str,
                 trigger_rule: TriggerRule,
                 trigger_rule_log_dao: TriggerRuleLogDAO,
                 camera_motion_dict: dict[str, dict[int,
                                           tuple[bool,
                                                 Optional[CameraImgSeq]]]],
                 ):
        from miloco_server.service.manager import get_manager  # pylint: disable=import-outside-toplevel
        self._manager = get_manager()
        self._chat_companion = self._manager.chat_companion
        self.request_id = request_id
        self._trigger_rule = trigger_rule
        self._trigger_rule_log_dao = trigger_rule_log_dao
        self.session_id = "no session id"
        self._session: ChatHistorySession = ChatHistorySession()
        self._web_sockets: list[WebSocket] = []
        self._done: Optional[asyncio.Event] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._camera_motion_dict = camera_motion_dict
        logger.info("[%s] TriggerRuleDynamicExecutor init", self.request_id)

    async def run(self) -> bool:
        """Start the dynamic executor and wait for completion."""
        self._loop = asyncio.get_running_loop()
        self._done = asyncio.Event()

        chat_agent = ActionDescriptionDynamicExecuteAgent(
            self.request_id,
            self._handle_instruction_payload,
            None,
            session_id=self.session_id,
        )

        mock_event_payload = Nlp.ActionDescriptionDynamicExecute(
            action_descriptions=self._trigger_rule.execute_info.ai_recommend_action_descriptions,
            mcp_list=self._trigger_rule.execute_info.mcp_list,
            camera_ids=self._trigger_rule.cameras,
        )
        mock_event = Event.build_event(mock_event_payload, self.request_id, self.session_id)

        camera_images = self._get_camera_images(self._trigger_rule.cameras)
        self._chat_companion.set_chat_data(self.request_id, ChatCachedData(
            camera_images=camera_images,
        ))

        chat_agent.handle_event(mock_event)

        try:
            await asyncio.wait_for(self._done.wait(), timeout=300)
            return True
        except asyncio.TimeoutError:
            logger.error("[%s] TriggerRuleDynamicExecutor timed out", self.request_id)
            return False
        finally:
            self._close_web_sockets()
            self._store_chat_history_session()

    async def attach_websocket(self, web_socket: WebSocket) -> None:
        """Attach a WebSocket: replay existing session, then add to live list."""
        await self._send_all_sessions(web_socket)

    def _get_camera_images(self, camera_ids: list[str]) -> list[CameraImgSeq]:
        """Get camera images"""
        camera_images: list[CameraImgSeq] = []
        for camera_id in camera_ids:
            channel_images = self._camera_motion_dict[camera_id]
            for _, (is_motion, camera_img_seq) in channel_images.items():
                if is_motion and camera_img_seq:
                    camera_images.append(camera_img_seq)
        return camera_images

    def _handle_instruction_payload(self, instruction_payload: InstructionPayload) -> None:
        """Receive instructions from the agent and forward to connected WebSockets."""
        if isinstance(instruction_payload, Internal.Dispatcher):
            return
        if isinstance(instruction_payload, Confirmation.AiGeneratedActions):
            return

        instruction = Instruction.build_instruction(instruction_payload, self.request_id, self.session_id)
        self._session.add_instruction(instruction)
        self._schedule_coroutine(self._send_instruction(instruction))

    async def _send_instruction(self, instruction: Instruction):
        """Send instruction to all connected WebSockets."""
        msg = instruction.model_dump_json()
        logger.info("send_instruction: %s", msg)
        for web_socket in self._web_sockets:
            await self._send_message(web_socket, msg)
        if instruction.judge_type("Dialog", "Finish"):
            logger.info("[%s] Dialog.Finish received, signalling done", self.request_id)
            if self._done:
                self._done.set()

    async def _send_message(self, web_socket: WebSocket, message: str):
        """Send a message to a single WebSocket."""
        try:
            await web_socket.send_text(message)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("[%s] Error sending message: %s", self.request_id, e)

    async def _send_all_sessions(self, web_socket: WebSocket):
        """
        Send all existing session items to a new WebSocket, then add it to the live list.
        Uses index tracking to ensure no messages are missed during catch-up.
        """
        try:
            sent_index = 0
            while True:
                current_count = len(self._session.data)
                while sent_index < current_count:
                    session = self._session.data[sent_index]
                    session_json = session.model_dump_json()
                    logger.info("send session to web socket: %s", session_json)
                    await self._send_message(web_socket, session_json)
                    sent_index += 1

                if len(self._session.data) == current_count:
                    break

            logger.info("append web socket after sending all sessions")
            self._web_sockets.append(web_socket)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("[%s] Error sending all sessions: %s", self.request_id, e)
            if web_socket not in self._web_sockets:
                self._web_sockets.append(web_socket)

    def _store_chat_history_session(self):
        """Store chat history session in the trigger rule log."""
        execute_result, _ = self._trigger_rule_log_dao.get_execute_result(self.request_id)
        if execute_result and execute_result.ai_recommend_dynamic_execute_result:
            execute_result.ai_recommend_dynamic_execute_result.chat_history_session = self._session
            execute_result.ai_recommend_dynamic_execute_result.is_done = True
        else:
            execute_result = ExecuteResult(
                ai_recommend_execute_type=self._trigger_rule.execute_info.ai_recommend_execute_type,
                ai_recommend_dynamic_execute_result=AiRecommendDynamicExecuteResult(
                    is_done=True,
                    ai_recommend_action_descriptions=self._trigger_rule.execute_info.ai_recommend_action_descriptions,
                    chat_history_session=self._session,
                ),
            )

        self._trigger_rule_log_dao.update_execute_result(self.request_id, execute_result)

    def _close_web_sockets(self):
        try:
            if not self._web_sockets:
                return
            for web_socket in self._web_sockets:
                if (hasattr(web_socket, "client_state")
                        and web_socket.client_state.value == 3):
                    logger.info("[%s] WebSocket already closed", self.request_id)
                    continue
                self._schedule_coroutine(web_socket.close())
        except Exception as e:  # pylint: disable=broad-except
            logger.error("[%s] Error closing WebSocket: %s", self.request_id, e)

    def _schedule_coroutine(self, coroutine):
        """Schedule work on the executor's owning event loop."""
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        if self._loop.is_closed():
            raise RuntimeError("TriggerRuleDynamicExecutor event loop is closed")
        self._loop.call_soon_threadsafe(self._loop.create_task, coroutine)
