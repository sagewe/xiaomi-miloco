# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""Rule creation tool module for creating and managing automation rules."""

import asyncio
import logging
from typing import Callable, List, Optional

from miloco_server.schema.mcp_schema import MCPClientStatus, choose_mcp_list

from miloco_server.utils.llm_utils.action_converter import ActionDescriptionConverter, ConverterResult
from miloco_server.utils.llm_utils.device_chooser import DeviceChooser

from miloco_server.schema.chat_schema import Confirmation, Dialog, Event, InstructionPayload, Internal
from miloco_server.schema.miot_schema import CameraInfo
from miloco_server.schema.trigger_schema import Action, Notify, TriggerRule, TriggerRuleDetail, ExecuteInfo, ExecuteType, ExecuteInfoDetail
from pydantic.dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RuleCreateMessage:
    name: str
    condition: str
    action_descriptions: List[str]
    location: Optional[str]
    notify: Optional[str]


class RuleCreateTool:
    """Tool for creating and managing automation rules."""

    def __init__(
        self,
        request_id: str,
        send_instruction_fn: Callable,
        camera_ids: Optional[List[str]] = None,
        mcp_ids: Optional[List[str]] = None,
    ):
        from miloco_server.service.manager import get_manager  # pylint: disable=import-outside-toplevel
        self._manager = get_manager()
        self._request_id = request_id
        self._default_preset_action_manager = self._manager.default_preset_action_manager
        self._send_instruction_fn = send_instruction_fn
        self._future: Optional[asyncio.Future] = None
        self._camera_ids = camera_ids
        self._mcp_ids = mcp_ids
        logger.info("[%s] RuleCreateTool initialized", self._request_id)

    async def run(self, message: RuleCreateMessage) -> dict:
        """Run rule creation and wait for user confirmation."""
        self._future = asyncio.Future()
        asyncio.create_task(
            self._run_create_rule(
                message.name,
                message.condition,
                message.action_descriptions,
                message.location,
                message.notify,
            )
        )
        try:
            return await asyncio.wait_for(self._future, timeout=600)
        except asyncio.TimeoutError:
            return {"error": "RuleCreateTool: timed out waiting for user confirmation"}

    def _handle_confirmation_event(self, event: Event):
        """Handle confirmation event from the user (registered as next_event_handler)."""
        try:
            if event.judge_type("Confirmation", "SaveRuleConfirmResult"):
                save_rule_confirm_result = Confirmation.SaveRuleConfirmResult.model_validate_json(event.payload)
                self._handle_save_rule_confirm_result(save_rule_confirm_result)
            else:
                raise ValueError(f"Invalid event: {event.header.namespace}.{event.header.name}")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("[%s] Error occurred while handling confirmation event: %s", self._request_id, str(e))
            if self._future and not self._future.done():
                self._future.set_result({"error": str(e)})

    async def _run_create_rule(
            self,
            name: str,
            condition: str,
            action_descriptions: list[str],
            location: Optional[str] = None,
            notify: Optional[str] = None) -> None:
        """Run the rule creation flow."""
        logger.info(
            "[%s] Starting to process rule create: name: %s, condition: %s, action_description: %s, location: %s, notify: %s",  # pylint: disable=line-too-long
            self._request_id,
            name,
            condition,
            action_descriptions,
            location,
            notify)
        if not notify:
            notify = name

        try:
            chosen_camera_infos, all_camera_infos = await self._choose_camera(location)
            if not chosen_camera_infos:
                chosen_camera_infos = all_camera_infos

            miot_scene_actions = await self._default_preset_action_manager.get_miot_scene_actions()
            ha_automation_actions = await self._default_preset_action_manager.get_ha_automation_actions()

            no_matched_action_descriptions, matched_actions = (
                await self._action_descriptions_to_preset_actions(
                    action_descriptions, miot_scene_actions, ha_automation_actions))

            execute_info = ExecuteInfo(
                ai_recommend_execute_type=ExecuteType.DYNAMIC,
                ai_recommend_action_descriptions=no_matched_action_descriptions,
                automation_actions=matched_actions,
                notify=Notify(content=notify)
            )

            choosed_mcp_list = await self._choose_mcp_list()
            trigger_rule_detail = TriggerRuleDetail(
                name=name,
                cameras=chosen_camera_infos,
                condition=condition,
                execute_info=ExecuteInfoDetail.from_execute_info(
                    execute_info, choosed_mcp_list),
                enabled=True
            )

            save_rule_confirm = Confirmation.SaveRuleConfirm(
                rule=trigger_rule_detail,
                camera_options=all_camera_infos,
                action_options=(
                    list(miot_scene_actions.values()) +
                    list(ha_automation_actions.values()))
            )

            # Register self as next event handler so confirmation comes back here
            dispatcher_message = Internal.Dispatcher(next_event_handler=self._handle_confirmation_event)
            self._send_instruction(dispatcher_message)
            self._send_instruction(save_rule_confirm)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("[%s] Error occurred during agent execution: %s", self._request_id, str(e), exc_info=True)
            self._send_instruction(Dialog.Exception(message=f"Error occurred during execution: {str(e)}"))
            if self._future and not self._future.done():
                self._future.set_result({"error": str(e)})

    async def _choose_mcp_list(self) -> list[MCPClientStatus]:
        """Get MCP list"""
        all_mcp_status = await self._manager.mcp_service.get_all_mcp_clients_status()
        return choose_mcp_list(self._mcp_ids, all_mcp_status.clients)

    async def _action_descriptions_to_preset_actions(
            self, action_descriptions: List[str],
            miot_scene_actions: dict[str, Action],
            ha_automation_actions: dict[str, Action]):
        """Convert action descriptions to actions"""

        miot_scene_converter = ActionDescriptionConverter(
            self._request_id, action_descriptions, miot_scene_actions)
        ha_automation_converter = ActionDescriptionConverter(
            self._request_id, action_descriptions, ha_automation_actions)
        task = []
        task.append(miot_scene_converter.run())
        task.append(ha_automation_converter.run())
        results = await asyncio.gather(*task)

        miot_scene_results: list[ConverterResult] = results[0]
        ha_automation_results: list[ConverterResult] = results[1]

        no_matched_action_descriptions = []
        matched_actions = []
        if (len(miot_scene_results) == len(action_descriptions) and
                len(ha_automation_results) == len(action_descriptions)):
            for action_description, miot_scene_result, ha_automation_result in zip(
                    action_descriptions, miot_scene_results, ha_automation_results):
                if not miot_scene_result.is_inside and not ha_automation_result.is_inside:
                    no_matched_action_descriptions.append(action_description)
                    continue

                if miot_scene_result.is_inside:
                    matched_actions.append(miot_scene_result.action)
                if ha_automation_result.is_inside:
                    matched_actions.append(ha_automation_result.action)
        else:
            logger.warning(
                "[%s] Action descriptions to preset actions failed: %s, %s",
                self._request_id, miot_scene_results, ha_automation_results)
            for miot_scene_result in miot_scene_results:
                if not miot_scene_result.is_inside:
                    no_matched_action_descriptions.append(miot_scene_result.action_description)
                else:
                    matched_actions.append(miot_scene_result.action)

            for ha_automation_result in ha_automation_results:
                if not ha_automation_result.is_inside:
                    no_matched_action_descriptions.append(ha_automation_result.action_description)
                else:
                    matched_actions.append(ha_automation_result.action)

        return no_matched_action_descriptions, matched_actions

    async def _choose_camera(self, location: Optional[str] = None) -> tuple[List[CameraInfo], List[CameraInfo]]:
        """Choose camera"""
        device_chooser = DeviceChooser(
            request_id=self._request_id,
            location=location,
            choose_camera_device_ids=self._camera_ids)
        return await device_chooser.run()

    def _handle_save_rule_confirm_result(self, save_rule_confirm_result: Confirmation.SaveRuleConfirmResult):
        """Handle save rule confirmation result"""
        logger.info("[%s] Received save rule confirm result: %s", self._request_id, save_rule_confirm_result)

        if save_rule_confirm_result.confirmed and save_rule_confirm_result.rule is not None:
            asyncio.create_task(self._create_rule_and_respond(save_rule_confirm_result.rule))
        else:
            if self._future and not self._future.done():
                self._future.set_result({"content": "User refused to save this rule"})

    async def _create_rule_and_respond(self, rule: TriggerRule):
        """Asynchronously create rule and respond with result"""
        try:
            rule_id = await self._manager.trigger_rule_service.create_trigger_rule(rule)
            if rule_id:
                if self._future and not self._future.done():
                    self._future.set_result(
                        {"content": self._simplify_rule_introduction(rule)})
            else:
                if self._future and not self._future.done():
                    self._future.set_result({"error": "Failed to create trigger rule"})
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("[%s] Error creating trigger rule: %s", self._request_id, str(e))
            if self._future and not self._future.done():
                self._future.set_result({"error": str(e)})

    def _simplify_rule_introduction(self, rule: TriggerRule) -> str:
        """Simplify rule introduction"""
        action_introductions = []
        if rule.execute_info.ai_recommend_action_descriptions:
            action_introductions.append(rule.execute_info.ai_recommend_action_descriptions)
        if rule.execute_info.automation_actions:
            action_introductions.append([action.introduction for action in rule.execute_info.automation_actions])
        if rule.execute_info.notify:
            action_introductions.append(f"notify: {rule.execute_info.notify.content}")

        return (
            f"User modified rule created successfully, finally rule name: {rule.name}, "
            f"condition: {rule.condition}, action_introductions: {action_introductions}"
        )

    def _send_instruction(self, instruction_payload: InstructionPayload):
        self._send_instruction_fn(instruction_payload)
