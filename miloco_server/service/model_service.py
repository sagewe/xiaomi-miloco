# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""
Model management service module
"""

import asyncio
import json
import logging
from typing import Optional

from miloco_server.dao.kv_dao import KVDao, SystemConfigKeys
from miloco_server.dao.third_party_model_dao import ThirdPartyModelDAO
from miloco_server.utils.local_models import ModelPurpose
from miloco_server.proxy.llm_proxy import LLMProxy, OpenAIProxy
from miloco_server.schema.model_schema import (
    ThirdPartyModelCreate, ThirdPartyModelInfo, LLMModelInfo, ModelsList
)
from miloco_server.middleware.exceptions import (
    ResourceNotFoundException,
    BusinessException,
    ConflictException
)

logger = logging.getLogger(__name__)


class ModelService:
    """Model management service class"""

    def __init__(self, kv_dao: KVDao, third_party_model_dao: ThirdPartyModelDAO):
        self._kv_dao = kv_dao
        self._third_party_model_dao = third_party_model_dao
        self._model_id_by_purpose = {}
        self._llm_proxy_by_purpose = {}

        try:
            asyncio.create_task(self._refresh_llm_proxy())
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("refresh llm proxy failed: %s", e)

    async def _refresh_llm_proxy(self):
        """Refresh LLM proxy cache"""

        self._model_id_by_purpose = {}
        self._llm_proxy_by_purpose = {}
        model_purpose_str = self._kv_dao.get(SystemConfigKeys.CURRENT_MODEL_ID_KEY)
        if not model_purpose_str:
            return self._llm_proxy_by_purpose

        model_id_by_purpose = {}
        try:
            model_id_by_purpose = json.loads(model_purpose_str)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to parse current model ID: %s, using None", e)
            return self._llm_proxy_by_purpose

        llm_proxy_by_purpose: dict[ModelPurpose, LLMModelInfo] = {}
        pop_keys = []
        for purpose_type, model_id in model_id_by_purpose.items():
            try:
                purpose = ModelPurpose(purpose_type)
            except Exception:  # pylint: disable=broad-exception-caught
                pop_keys.append(purpose_type)
                continue

            model = self._third_party_model_dao.get_by_id(model_id)
            if model:
                llm_proxy_by_purpose[purpose] = model
            else:
                pop_keys.append(purpose_type)
                logger.error("Selected model does not exist: %s, using None", model_id)

        for key in pop_keys:
            model_id_by_purpose.pop(key)

        if pop_keys:
            success = self._kv_dao.set(
                SystemConfigKeys.CURRENT_MODEL_ID_KEY,
                json.dumps(model_id_by_purpose, ensure_ascii=False))
            if not success:
                logger.error("Failed to set current model ID: %s", model_id_by_purpose)
                raise BusinessException("Failed to set current model")

        self._model_id_by_purpose = model_id_by_purpose
        self._llm_proxy_by_purpose = {
            purpose:
            OpenAIProxy(base_url=model_info.base_url,
                        api_key=model_info.api_key,
                        model_name=model_info.model_name)
            for purpose, model_info in llm_proxy_by_purpose.items()
        }

    def get_llm_proxy(self) -> dict[ModelPurpose, LLMProxy]:
        return self._llm_proxy_by_purpose

    async def set_current_model(self, model_id: Optional[str], purpose: ModelPurpose):
        """
        Set currently used model

        Args:
            model_id: Model ID (optional, None to clear the model for this purpose)
            purpose: Model purpose
        """
        logger.info("Setting current model: model_id=%s", model_id)

        model = None
        if model_id:
            model = self._third_party_model_dao.get_by_id(model_id)

        model_id_by_purpose = self._model_id_by_purpose.copy()
        if model:
            model_id_by_purpose[purpose.value] = model_id
        else:
            model_id_by_purpose.pop(purpose.value, None)

        success = self._kv_dao.set(
            SystemConfigKeys.CURRENT_MODEL_ID_KEY,
            json.dumps(model_id_by_purpose, ensure_ascii=False))

        if not success:
            logger.error("Failed to set current model ID: %s", model_id_by_purpose)
            raise BusinessException("Failed to set current model")

        await self._refresh_llm_proxy()
        logger.info("Current model set successfully: %s", model_id)

    async def create_third_party_model(
            self, model: ThirdPartyModelCreate) -> list[str]:

        model_infos = model.convert_to_model_infos()
        model_ids = [
            self._third_party_model_dao.create(model_info)
            for model_info in model_infos
        ]

        if not model_ids:
            logger.error("Third-party model creation failed")
            raise BusinessException("Third-party model creation failed")

        logger.info("Third-party model created successfully: %s", model_ids)
        return model_ids

    async def get_third_party_model(self, model_id: str) -> LLMModelInfo:
        logger.info("Getting third-party model details: id=%s", model_id)

        model = self._third_party_model_dao.get_by_id(model_id)

        if not model:
            logger.warning("Third-party model does not exist: id=%s", model_id)
            raise ResourceNotFoundException("Third-party model does not exist")

        return model

    async def get_all_models(self) -> ModelsList:
        logger.info("Getting all models")

        models = self._third_party_model_dao.get_all()
        models_response = [
            LLMModelInfo.from_third_party(model) for model in models
        ]
        await self._refresh_llm_proxy()
        return ModelsList(models=models_response,
                          current_model=self._model_id_by_purpose)

    async def update_third_party_model(self, model: ThirdPartyModelInfo):
        existing_model = self._third_party_model_dao.get_by_id(model.id)
        if not existing_model:
            raise ResourceNotFoundException(f"Third-party model does not exist: {model.id}")

        success = self._third_party_model_dao.update(model)

        if not success:
            logger.error("Third-party model update failed: %s", model.id)
            raise BusinessException("Third-party model update failed")

        logger.info("Third-party model updated successfully: %s", model.id)

    def delete_third_party_model(self, model_id: str):
        logger.info("Deleting third-party model: id=%s", model_id)

        if model_id in self._model_id_by_purpose.values():
            raise ConflictException("Current model is in use, cannot delete")

        if not self._third_party_model_dao.exists(model_id):
            raise ResourceNotFoundException("Third-party model does not exist")

        success = self._third_party_model_dao.delete(model_id)

        if not success:
            logger.error("Third-party model deletion failed: id=%s", model_id)
            raise BusinessException("Third-party model deletion failed")

        logger.info("Third-party model deleted successfully: %s", model_id)

    async def get_vendor_models(self, base_url: str, api_key: str) -> dict:
        """
        Get all models from vendor

        Args:
            base_url: Vendor API base URL
            api_key: Vendor API key
        """
        logger.info("Getting vendor models: base_url=%s", base_url)

        try:
            from miloco_server.proxy.llm_proxy import get_models_from_openai_compatible_api  # pylint: disable=import-outside-toplevel
            result = await get_models_from_openai_compatible_api(base_url, api_key)
            logger.info("Successfully retrieved vendor models: count=%d", result.get("count", 0))
            return result
        except Exception as e:
            logger.error("Failed to get vendor models: %s", str(e))
            raise BusinessException(f"Failed to get vendor models: {str(e)}") from e
