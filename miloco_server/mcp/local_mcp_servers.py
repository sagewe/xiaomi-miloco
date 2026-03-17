# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""
Local MCP server implementation
Uses Tool.from_function() to automatically generate parameter definitions, more concise and elegant
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Annotated
from fastmcp import FastMCP
from fastmcp.tools import Tool
from miloco_server.schema.mcp_schema import LocalMcpClientId
from miloco_server.utils.chat_companion import ChatCachedData
from miloco_server.tools.rule_create_tool import RuleCreateMessage, RuleCreateTool
from miloco_server.tools.vision_chat_tool import VisionChatTool

logger = logging.getLogger(__name__)


class LocalMCPBase:
    """Base class for local MCP servers"""

    def __init__(self, name: str, instructions: str = None):
        from miloco_server.service.manager import get_manager # pylint: disable=import-outside-toplevel
        self.name = name
        self.instructions = instructions or f"Local tool server: {name}"
        self.mcp: FastMCP = None
        self._initialized = False
        self._manager = get_manager()

    async def init_async(self):
        """Asynchronously initialize MCP server"""
        if self._initialized:
            return

        self.mcp = FastMCP(
            name=self.name,
            instructions=self.instructions,
            on_duplicate="error",
            mask_error_details=True,
        )

        # Register tools
        await self._register_tools()
        self._initialized = True
        logger.info("Local MCP server %s initialization completed", self.name)

    async def _register_tools(self):
        """Register tools to MCP server"""
        raise NotImplementedError("Subclass must implement _register_tools method")

    @property
    def mcp_instance(self) -> FastMCP:
        """Get MCP instance"""
        if not self._initialized:
            raise RuntimeError("MCP server not initialized, please call init_async() first")
        return self.mcp


class LocalDefaultMcp(LocalMCPBase):
    """Local default MCP server - includes rule creation and vision understanding tools"""

    def __init__(self):
        super().__init__(
            name="本地默认工具 (Local Default Tools)",
            instructions="Provides core tools for rule creation, vision understanding, etc."
        )

    async def _register_tools(self):
        """Register all default tools"""
        rule_tool = Tool.from_function(
            fn=self.create_rule,
            name="create_rule",
            description="""
用于创建规则的工具 / Tool for creating rules, used when users want to create a rule through this tool.
典型的解决问题为"当XXX时，执行YYY" / Typical problem solving is "when XXX, execute YYY". Examples:
1. "当XXX时，执行YYY和ZZZZ" / "When XXX, execute YYY and ZZZZ".
2. "当客厅的有人移动时，执行开灯场景" / "When someone moves in the living room, execute the turn on light scene".
3. "当卧室有人摔倒时，执行通知场景" / "When someone falls in the bedroom, execute the notification scene".
4. "当有人坐在沙发上时，执行开灯和打开电视机场景" / "When someone sits on the sofa, execute the turn on light and turn on TV scene".
注意：用户可能拒绝保存规则，此时无需再次尝试保存规则。 / Note: The user may refuse to save the rule, in this case, do not try to save the rule again.
"""
        )
        self.mcp.add_tool(tool=rule_tool)

        vision_tool = Tool.from_function(
            fn=self.vision_understand,
            name="vision_understand",
            description="Tool for understanding images, used when users want to understand the home cameras displayed.")
        self.mcp.add_tool(tool=vision_tool)

    async def create_rule(
        self,
        request_id: Annotated[str, "request_id"],
        name: Annotated[str, "Description of the rule to be created, concise and natural, format: xx rule, 4-6 chars"],
        condition: Annotated[str, "Condition, such as 'when XXX'"],
        actions: Annotated[list[str], "Actions, such as 'execute YYY and ZZZ', action descriptions should be concise and natural, real user descriptions (no excessive thinking), if it is 'execute YYY and ZZZ', then pass [YYY,ZZZ]"],  # pylint: disable=line-too-long
        location: Annotated[Optional[str], "Location, such as 'living room', empty if no specific location is described"] = None,  # pylint: disable=line-too-long
        notify: Annotated[Optional[str], "Notification content, such as 'someone fell', can be empty"] = None
    ) -> dict[str, Any]:
        """Create rule"""
        chat_data: ChatCachedData | None = self._manager.chat_companion.get_chat_data(request_id)
        if chat_data is None:
            return "error: request_id not found"

        if chat_data.send_instruction is None:
            return "error: send_instruction not found"

        rule_create_tool = RuleCreateTool(
            request_id=request_id,
            send_instruction_fn=chat_data.send_instruction,
            camera_ids=chat_data.camera_ids,
            mcp_ids=chat_data.mcp_ids,
        )

        logger.info("RuleTool: create rule: %s, %s, %s, %s, %s", name, condition, actions, location, notify)
        response = await rule_create_tool.run(RuleCreateMessage(name, condition, actions, location, notify))
        logger.info("RuleTool: create rule response: %s", response)
        return response

    async def vision_understand(
        self,
        request_id: Annotated[str, "Request ID"],
        query: Annotated[str, "Query content, such as 'what is my cat doing'"],
        location: Annotated[Optional[str], "Location, such as 'living room', empty if no specific location is described"] = None  # pylint: disable=line-too-long
    ) -> dict[str, Any]:
        """Understand image"""
        chat_data: ChatCachedData | None = self._manager.chat_companion.get_chat_data(request_id)
        if chat_data is None:
            return "error: request_id not found"

        if chat_data.send_instruction is None:
            return "error: send_instruction not found"

        vision_chat_tool = VisionChatTool(
            request_id=request_id,
            query=query,
            send_instruction_fn=chat_data.send_instruction,
            location_info=location,
            user_choosed_camera_dids=chat_data.camera_ids,
            camera_images=chat_data.camera_images,
        )

        response = await vision_chat_tool.run()
        logger.info("VisionUnderstandTool: vision understand response: %s", response)
        return response


class LocalMCPServerFactory:
    """Local MCP server factory"""

    @staticmethod
    async def create_all_servers() -> Dict[str, LocalMCPBase]:
        """Create all local MCP servers"""
        servers = {}

        try:
            default_server = LocalDefaultMcp()
            await default_server.init_async()
            servers[LocalMcpClientId.LOCAL_DEFAULT] = default_server

            logger.info("Successfully created %d local MCP servers", len(servers))

        except Exception as e:
            logger.error("Failed to create local MCP servers: %s", e)
            raise

        return servers
