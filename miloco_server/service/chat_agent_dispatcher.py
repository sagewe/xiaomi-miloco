# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""
Chat agent dispatcher module
"""

import logging
import time
from typing import Callable, Optional
import uuid
import asyncio

from fastapi import WebSocket

from miloco_server.agent.nlp_request_agent import NlpRequestAgent
from miloco_server.agent.dynamic_execute_agent import ActionDescriptionDynamicExecuteAgent
from miloco_server.schema.chat_schema import Event, Instruction, InstructionPayload, Internal
from miloco_server.schema.chat_history_schema import (
    ChatHistoryStorage, ChatHistoryMessages, ChatHistorySession
)

logger = logging.getLogger(__name__)


class ChatAgentDispatcher:
    """
    ChatAgentDispatcher - dispatches WebSocket events to the appropriate chat agent
    and forwards agent instructions back over the WebSocket connection.
    """

    def __init__(self,
                 web_socket: WebSocket,
                 request_id: str,
                 session_id: Optional[str] = None):
        self.web_socket = web_socket
        self.request_id = request_id
        self.session_id = session_id if session_id is not None else str(uuid.uuid4())

        self._chat_agent = None
        self._next_event_handler: Optional[Callable] = None
        from miloco_server.service.manager import get_manager  # pylint: disable=import-outside-toplevel
        self._manager = get_manager()
        self._chat_companion = self._manager.chat_companion
        chat_history_storage = self._chat_companion.get_chat_history(self.session_id)
        if chat_history_storage is not None:
            self._chat_history_storage = chat_history_storage
        else:
            self._chat_history_storage = ChatHistoryStorage(
                session_id=self.session_id,
                title="",
                timestamp=int(time.time() * 1000),
                session=ChatHistorySession(),
                messages=None,
            )
        self._chat_history_messages = ChatHistoryMessages.from_json(self._chat_history_storage.messages)
        logger.info(
            "ChatAgentDispatcher init, current chat history: %s", self._chat_history_storage
        )
        self._need_storage_history = False

    def handle_event(self, event: Event) -> None:
        """Handle an incoming Event from the WebSocket client."""
        try:
            self._handle_event(event)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("[%s] Error in handle_event: %s", self.request_id, e)
            self._close_web_socket()

    def _handle_instruction_payload(self, instruction_payload: InstructionPayload) -> None:
        """Receive an InstructionPayload from a chat agent and forward to the client."""
        try:
            if isinstance(instruction_payload, Internal.Dispatcher):
                self._handle_internal_dispatcher(instruction_payload)
                return

            instruction = Instruction.build_instruction(
                instruction_payload, self.request_id, self.session_id)

            self._chat_history_storage.session.add_instruction(instruction)
            asyncio.create_task(self._send_instruction(instruction))
        except Exception as e:  # pylint: disable=broad-except
            logger.error("[%s] Error in _handle_instruction_payload: %s", self.request_id, e)
            self._close_web_socket()

    def _handle_event(self, event: Event) -> None:
        """Handle Event object."""
        logger.info(
            "[%s] handle_event: %s.%s", self.request_id,
            event.header.namespace, event.header.name
        )
        if event.header.type != "event":
            raise ValueError(f"Invalid event type: {event.header.type}")

        self._chat_history_storage.session.add_event(event)

        if self._next_event_handler is not None:
            handler = self._next_event_handler
            self._next_event_handler = None
            handler(event)
            return

        if event.judge_type("Nlp", "Request"):
            logger.info("[%s] create nlp request agent", self.request_id)
            self._chat_agent = NlpRequestAgent(
                self.request_id,
                self._handle_instruction_payload,
                self._chat_history_messages,
                session_id=self.session_id,
            )
            logger.info("[%s] send event to nlp request agent", self.request_id)
            self._chat_agent.handle_event(event)

        elif event.judge_type("Nlp", "ActionDescriptionDynamicExecute"):
            logger.info("[%s] create nlp action description dynamic execute agent", self.request_id)
            self._chat_agent = ActionDescriptionDynamicExecuteAgent(
                self.request_id,
                self._handle_instruction_payload,
                self._chat_history_messages,
                session_id=self.session_id,
            )
            logger.info("[%s] send event to nlp action descriptions dynamic execute agent", self.request_id)
            self._chat_agent.handle_event(event)
        else:
            logger.warning(
                "[%s] Unsupported event: %s.%s", self.request_id,
                event.header.namespace, event.header.name
            )

    def _handle_internal_dispatcher(self, dispatcher_message: Internal.Dispatcher) -> None:
        """Handle Internal Dispatcher message."""
        logger.info("[%s] handle_internal_dispatcher: %s", self.request_id, dispatcher_message)
        self._next_event_handler = dispatcher_message.next_event_handler
        if dispatcher_message.current_query is not None and self._chat_history_storage.title == "":
            self._chat_history_storage.title = dispatcher_message.current_query
        if dispatcher_message.need_storage_history is not None:
            self._need_storage_history = dispatcher_message.need_storage_history

    async def _send_instruction(self, instruction: Instruction):
        """Send instruction over WebSocket and handle Dialog.Finish."""
        msg = instruction.model_dump_json()
        logger.info("send_instruction: %s", msg)
        await self._send_message(msg)
        if instruction.judge_type("Dialog", "Finish"):
            logger.info("[%s] Dialog.Finish received, closing dispatcher", self.request_id)
            await self.close()

    async def _send_message(self, message: str):
        """Send a raw text message over the WebSocket."""
        if self.web_socket is None:
            return
        try:
            await self.web_socket.send_text(message)
        except Exception:  # pylint: disable=broad-except
            pass

    async def close(self):
        """Clean up dispatcher: persist history and close WebSocket."""
        self._close_web_socket()
        logger.info("[%s] close, need_storage_history: %s", self.request_id, self._need_storage_history)
        if self._need_storage_history:
            self._chat_history_storage.messages = self._chat_history_messages.to_json()
            self._chat_companion.store_chat_history(self._chat_history_storage)
        self._chat_companion.clear_chat_data(self.request_id)
        logger.info("[%s] Dispatcher closed successfully", self.request_id)

    def _close_web_socket(self):
        if self.web_socket is None:
            return
        try:
            if (hasattr(self.web_socket, "client_state")
                    and self.web_socket.client_state.value == 3):
                logger.info("[%s] WebSocket already closed", self.request_id)
                self.web_socket = None
                return
            asyncio.create_task(self.web_socket.close())
        except Exception as e:  # pylint: disable=broad-except
            logger.error("[%s] Error closing WebSocket: %s", self.request_id, e)
        finally:
            self.web_socket = None
