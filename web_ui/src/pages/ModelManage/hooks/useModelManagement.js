/**
 * Copyright (C) 2025 Xiaomi Corporation
 * This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.
 */

import { useState, useEffect } from 'react';
import { message } from 'antd';
import { useTranslation } from 'react-i18next';
import { getAllModels, deleteModel, createModel, updateModel } from '@/api';

/**
 * useModelManagement - Model management hooks
 * 模型管理钩子
 */
export const useModelManagement = () => {
  const { t } = useTranslation();
  const [models, setModels] = useState([]);
  const [selectedModelId, setSelectedModelId] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState(null);
  const [llmOptions, setLLMOptions] = useState([]);
  const [llmLoading, setLLMLoading] = useState(false);
  const [loading, setLoading] = useState(true);

  const refreshModels = async () => {
    setLoading(true);
    await fetchModels();
    setLoading(false);
  };

  // fetch models
  const fetchModels = async () => {
    try {
      const res = await getAllModels();
      if (res && res.code === 0) {
        const models = res?.data?.models || [];
        const id = res?.data?.current_model_id;
        const modelsFromApi = models.map((item) => ({
          id: item.id,
          name: item.model_name,
          apiKey: item.api_key,
          baseUrl: item.base_url,
        }));
        setModels(modelsFromApi);
        setSelectedModelId(id);
      } else {
        message.error(res?.message || t('modelModal.fetchModelCheckListFailed'));
      }
    } catch (error) {
      console.error('fetchModels failed:', error);
    }
  };

  // open modal (add/edit)
  const openModal = (model = null) => {
    setEditingModel(model);
    setModalOpen(true);
  };

  // close modal
  const closeModal = () => {
    setModalOpen(false);
    setEditingModel(null);
  };

  // submit form
  const handleSubmit = async (form, values) => {
    try {
      if (editingModel) {
        // edit model - single select logic
        const res = await updateModel(editingModel.id, {
          model_name: values.name,
          base_url: values.baseUrl,
          api_key: values.apiKey,
        });
        if (res && res.code === 0) {
          await refreshModels();
          message.success(t('common.editSuccess'));
          closeModal();
        } else {
          message.error(res?.message || t('common.editFail'));
        }
      } else {
        // add model - multi select logic
        const modelNames = Array.isArray(values.name) ? values.name : [values.name];
        const res = await createModel({
          model_names: modelNames,
          base_url: values.baseUrl,
          api_key: values.apiKey,
        });

        if (res && res.code === 0) {
          await refreshModels();
          message.success(t('common.addSuccess'));
          closeModal();
        } else {
          message.error(res?.message || t('common.addFail'));
        }
      }
    } catch {
      message.error(editingModel ? t('common.editFail') : t('common.addFail'));
    }
  };

  // delete model
  const handleDelete = async (id) => {
    try {
        const res = await deleteModel(id);
        if (res && res.code === 0) {
          message.success(t('common.deleteSuccess'));
          await refreshModels();
        } else {
          message.error(res?.message || t('common.deleteFail'));
        }
      } catch {
        message.error(t('common.deleteFail'));
      }
  };

  useEffect(() => {
    refreshModels();
  }, []);

  return {
    models,
    selectedModelId,
    modalOpen,
    editingModel,
    llmOptions,
    llmLoading,
    loading,
    setLLMLoading,
    setLLMOptions,
    fetchModels,
    openModal,
    closeModal,
    handleSubmit,
    handleDelete,
  };
};
