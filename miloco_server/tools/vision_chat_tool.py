# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""Vision chat tool module for image understanding and processing."""

import asyncio
import logging
from typing import Callable, Optional

from pydantic.dataclasses import dataclass
from miloco_server.schema.miot_schema import CameraImgSeq

from miloco_server.config import CHAT_CONFIG
from miloco_server.schema.chat_schema import Dialog, InstructionPayload, Template
from miloco_server.utils.llm_utils.device_chooser import DeviceChooser
from miloco_server.utils.llm_utils.vision_understander import VisionUnderstander

logger = logging.getLogger(__name__)


@dataclass
class VisionUnderstandStart:
    pass


class VisionChatTool:
    """Tool for handling vision chat and image understanding tasks."""

    def __init__(
        self,
        request_id: str,
        query: str,
        send_instruction_fn: Callable,
        location_info: Optional[str],
        user_choosed_camera_dids: list[str],
        camera_images: Optional[list[CameraImgSeq]],
    ):
        from miloco_server.service.manager import get_manager  # pylint: disable=import-outside-toplevel
        self._manager = get_manager()

        self._request_id = request_id
        self._query = query
        self._location_info = location_info
        self._user_choosed_camera_dids = user_choosed_camera_dids
        self._send_instruction_fn = send_instruction_fn
        self._language = self._manager.auth_service.get_user_language().language
        self._vision_use_img_count = CHAT_CONFIG["vision_use_img_count"]
        self._camera_images: Optional[list[CameraImgSeq]] = camera_images
        logger.info("[%s] VisionChatTool initialized", self._request_id)

    async def run(self) -> dict:
        """Run vision understanding and return the result."""
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        asyncio.create_task(self._handle_vision_understand_start(future))
        try:
            return await asyncio.wait_for(future, timeout=600)
        except asyncio.TimeoutError:
            return {"error": "VisionChatTool: timed out waiting for vision understanding"}

    async def _handle_vision_understand_start(self, future: asyncio.Future) -> None:
        """Run vision understanding logic."""
        logger.info(
            "[%s] Starting to process user query: %s", self._request_id, self._query
        )

        try:
            if self._camera_images:
                camera_img_seqs = self._camera_images
            else:
                device_chooser = DeviceChooser(
                    request_id=self._request_id,
                    location=self._location_info,
                    choose_camera_device_ids=self._user_choosed_camera_dids)
                camera_list, all_cameras = await device_chooser.run()

                if len(camera_list) == 0:
                    camera_list = all_cameras

                camera_dids = [camera.did for camera in camera_list]
                camera_img_seqs = await self._manager.miot_service.get_miot_cameras_img(
                    camera_dids, self._vision_use_img_count)

                logger.info("[%s] Got %d camera image sequences, camera_infos: %s, img_counts: %s",
                        self._request_id,
                        len(camera_img_seqs),
                        [camera_img_seq.camera_info for camera_img_seq in camera_img_seqs],
                        [len(camera_img_seq.img_list) for camera_img_seq in camera_img_seqs])

                camera_img_seqs = [
                    camera_img_seq for camera_img_seq in camera_img_seqs
                    if camera_img_seq.camera_info.online and len(camera_img_seq.img_list) > 0
                ]

            if len(camera_img_seqs) == 0:
                future.set_result({"error": "No camera images found, please check cameras are working"})
                return

            camera_img_path_seqs = await asyncio.gather(*[
                camera_img_seq.store_to_path()
                for camera_img_seq in camera_img_seqs
            ])

            self._send_instruction(
                Template.CameraImages(
                    image_path_seq_list=camera_img_path_seqs))
            vision_understander = VisionUnderstander(
                request_id=self._request_id,
                query=self._query,
                camera_img_seqs=camera_img_seqs,
                language=self._language)

            content = await vision_understander.run()
            if content is not None:
                future.set_result({"content": content})
            else:
                future.set_result({"error": "Failed to understand vision"})

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "[%s] Error occurred during agent execution: %s", self._request_id, str(e),
                exc_info=True)
            self._send_instruction(
                Dialog.Exception(message=f"Failed to understand vision: {str(e)}"))
            future.set_result({"error": f"Failed to understand vision: {str(e)}"})

    def _send_instruction(self, instruction_payload: InstructionPayload):
        """Send instruction upstream."""
        self._send_instruction_fn(instruction_payload)
