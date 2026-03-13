<template>
  <div ref="panelRef" class="bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg p-8">
    <h2 class="text-2xl font-bold text-gray-800 mb-4">RAG 向量模型配置</h2>
    <p class="text-sm text-gray-600 mb-6">
      优先级：本页配置 &gt; 系统配置 &gt; backend/.env。留空字段会自动回退到下一层可用配置。
    </p>

    <form @submit.prevent="handleSave" class="space-y-6">
      <div>
        <label for="embedding-provider" class="block text-sm font-medium text-gray-700">Provider</label>
        <select
          id="embedding-provider"
          v-model="config.embedding_provider"
          class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
        >
          <option value="openai">OpenAI Compatible</option>
          <option value="ollama">Ollama</option>
        </select>
      </div>

      <div>
        <label for="embedding-url" class="block text-sm font-medium text-gray-700">API URL</label>
        <div class="relative mt-1">
          <input
            type="text"
            id="embedding-url"
            v-model="config.embedding_base_url"
            class="block w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            :placeholder="urlPlaceholder"
          >
          <button
            type="button"
            @click="clearApiUrl"
            class="absolute inset-y-0 right-2 flex items-center px-2 text-gray-400 hover:text-gray-600"
            aria-label="清空 API URL"
          >
            <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
      </div>

      <div v-if="config.embedding_provider === 'openai'">
        <label for="embedding-key" class="block text-sm font-medium text-gray-700">API Key</label>
        <div class="relative mt-1">
          <input
            :type="showApiKey ? 'text' : 'password'"
            id="embedding-key"
            v-model="config.embedding_api_key"
            class="block w-full px-3 py-2 pr-24 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            :placeholder="apiKeyPlaceholder"
            @input="handleApiKeyInput"
          >
          <button
            type="button"
            @click="clearApiKey"
            class="absolute inset-y-0 right-2 flex items-center px-2 text-gray-400 hover:text-gray-600"
            aria-label="清空 API Key"
          >
            <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
          <button
            type="button"
            @click="toggleApiKeyVisibility"
            class="absolute inset-y-0 right-10 flex items-center px-2 text-gray-400 hover:text-gray-600"
            :aria-label="showApiKey ? '隐藏 API Key' : '显示 API Key'"
          >
            <svg v-if="showApiKey" class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10 5c-4.478 0-8.268 2.943-9.542 7C1.732 16.057 5.522 19 10 19s8.268-2.943 9.542-7C18.268 7.943 14.478 5 10 5zm0 10a5 5 0 110-10 5 5 0 010 10z" fill-opacity="0.2" />
              <path d="M10 7a3 3 0 100 6 3 3 0 000-6z" />
            </svg>
            <svg v-else class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zm13.707 0a4.167 4.167 0 11-8.334 0 4.167 4.167 0 018.334 0z" clip-rule="evenodd" />
              <path d="M10 8a2 2 0 100 4 2 2 0 000-4z" />
            </svg>
          </button>
        </div>
      </div>

      <div>
        <label for="embedding-model" class="block text-sm font-medium text-gray-700">Model</label>
        <div class="flex gap-2 mt-1">
          <div class="relative flex-1">
            <input
              type="text"
              id="embedding-model"
              v-model="config.embedding_model"
              @focus="showModelDropdown = true"
              @blur="hideDropdown"
              class="block w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              :placeholder="modelPlaceholder"
            >
            <button
              type="button"
              @click="clearApiModel"
              class="absolute inset-y-0 right-2 flex items-center px-2 text-gray-400 hover:text-gray-600"
              aria-label="清空模型名称"
            >
              <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
              </svg>
            </button>
            <div
              v-if="showModelDropdown && availableModels.length > 0"
              class="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto"
            >
              <div
                v-for="model in filteredModels"
                :key="model"
                @mousedown="selectModel(model)"
                class="px-3 py-2 cursor-pointer hover:bg-indigo-50 hover:text-indigo-600 text-sm"
              >
                {{ model }}
              </div>
              <div v-if="filteredModels.length === 0" class="px-3 py-2 text-sm text-gray-500">
                无匹配的模型
              </div>
            </div>
          </div>
          <button
            type="button"
            @click="loadModels"
            :disabled="isLoadingModels"
            class="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <svg v-if="isLoadingModels" class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>{{ isLoadingModels ? '加载中...' : '获取模型' }}</span>
          </button>
        </div>
      </div>

      <div>
        <label for="embedding-vector-size" class="block text-sm font-medium text-gray-700">Vector Size</label>
        <div class="relative mt-1">
          <input
            type="number"
            id="embedding-vector-size"
            v-model="vectorSizeInput"
            min="1"
            class="block w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            placeholder="留空则自动检测"
          >
          <button
            type="button"
            @click="clearVectorSize"
            class="absolute inset-y-0 right-2 flex items-center px-2 text-gray-400 hover:text-gray-600"
            aria-label="清空向量维度"
          >
            <svg class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
      </div>

      <div class="flex justify-end space-x-4 pt-4">
        <button type="button" @click="handleDelete" class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors">删除配置</button>
        <button type="submit" class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors">保存</button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  createOrUpdateEmbeddingConfig,
  deleteEmbeddingConfig,
  getAvailableEmbeddingModels,
  getEmbeddingConfig,
  type EmbeddingConfigCreate,
} from '@/api/embedding';
import { globalAlert } from '@/composables/useAlert';

const config = ref<EmbeddingConfigCreate>({
  embedding_provider: 'openai',
  embedding_base_url: '',
  embedding_api_key: '',
  embedding_model: '',
  embedding_model_vector_size: null,
});

const panelRef = ref<HTMLElement | null>(null);
const vectorSizeInput = ref('');
const showApiKey = ref(false);
const availableModels = ref<string[]>([]);
const isLoadingModels = ref(false);
const showModelDropdown = ref(false);
const hasStoredApiKey = ref(false);
const clearStoredApiKey = ref(false);

const filteredModels = computed(() => {
  if (!config.value.embedding_model) {
    return availableModels.value;
  }
  const searchTerm = config.value.embedding_model.toLowerCase();
  return availableModels.value.filter((model) => model.toLowerCase().includes(searchTerm));
});

const urlPlaceholder = computed(() => (
  config.value.embedding_provider === 'ollama'
    ? 'http://127.0.0.1:11434'
    : 'https://api.example.com/v1'
));

const modelPlaceholder = computed(() => (
  config.value.embedding_provider === 'ollama'
    ? '例如 nomic-embed-text:latest'
    : '例如 text-embedding-3-large'
));

const apiKeyPlaceholder = computed(() => {
  if (clearStoredApiKey.value) {
    return '保存后将清除当前自定义 Key';
  }
  if (hasStoredApiKey.value) {
    return '已保存自定义 Key；留空将保持不变';
  }
  return '留空则优先复用本页 LLM 配置，其次回退系统默认';
});

onMounted(async () => {
  const existingConfig = await getEmbeddingConfig();
  if (existingConfig) {
    config.value = {
      embedding_provider: existingConfig.embedding_provider || 'openai',
      embedding_base_url: existingConfig.embedding_base_url || '',
      embedding_api_key: '',
      embedding_model: existingConfig.embedding_model || '',
      embedding_model_vector_size: existingConfig.embedding_model_vector_size,
    };
    vectorSizeInput.value = existingConfig.embedding_model_vector_size?.toString() || '';
    hasStoredApiKey.value = existingConfig.has_api_key;
  }
  if (typeof window !== 'undefined') {
    window.addEventListener('keydown', handleGlobalKeydown);
  }
});

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', handleGlobalKeydown);
  }
});

const isPanelFocused = () => {
  if (typeof document === 'undefined') return false;
  return panelRef.value?.contains(document.activeElement) ?? false;
};

const handleGlobalKeydown = (event: KeyboardEvent) => {
  if (!isPanelFocused()) return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault();
    void handleSave();
  }
};

const normalizePayload = (): EmbeddingConfigCreate => ({
  embedding_provider: config.value.embedding_provider,
  embedding_base_url: config.value.embedding_base_url || null,
  embedding_api_key: config.value.embedding_api_key?.trim()
    ? config.value.embedding_api_key.trim()
    : clearStoredApiKey.value
      ? null
      : undefined,
  embedding_model: config.value.embedding_model || null,
  embedding_model_vector_size: vectorSizeInput.value ? Number(vectorSizeInput.value) : null,
});

const handleSave = async () => {
  await createOrUpdateEmbeddingConfig(normalizePayload());
  hasStoredApiKey.value = hasStoredApiKey.value || Boolean(config.value.embedding_api_key?.trim());
  clearStoredApiKey.value = false;
  config.value.embedding_api_key = '';
  await globalAlert.showSuccess('RAG 配置已保存');
};

const handleDelete = async () => {
  const confirmed = await globalAlert.showConfirm('确定要删除您的自定义 RAG 配置吗？删除后将恢复为系统默认配置。', '删除 RAG 配置');
  if (!confirmed) return;

  await deleteEmbeddingConfig();
  config.value = {
    embedding_provider: 'openai',
    embedding_base_url: '',
    embedding_api_key: '',
    embedding_model: '',
    embedding_model_vector_size: null,
  };
  vectorSizeInput.value = '';
  availableModels.value = [];
  hasStoredApiKey.value = false;
  clearStoredApiKey.value = false;
  await globalAlert.showSuccess('RAG 配置已删除');
};

const toggleApiKeyVisibility = () => {
  showApiKey.value = !showApiKey.value;
};

const clearApiKey = () => {
  config.value.embedding_api_key = '';
  clearStoredApiKey.value = hasStoredApiKey.value;
};

const handleApiKeyInput = () => {
  if (config.value.embedding_api_key) {
    clearStoredApiKey.value = false;
  }
};

const clearApiUrl = () => {
  config.value.embedding_base_url = '';
};

const clearApiModel = () => {
  config.value.embedding_model = '';
};

const clearVectorSize = () => {
  vectorSizeInput.value = '';
  config.value.embedding_model_vector_size = null;
};

const loadModels = async () => {
  isLoadingModels.value = true;
  try {
    const models = await getAvailableEmbeddingModels({
      embedding_provider: config.value.embedding_provider || 'openai',
      embedding_api_key: config.value.embedding_api_key?.trim() || undefined,
      embedding_base_url: config.value.embedding_base_url || undefined,
    });
    availableModels.value = models;
    if (models.length > 0) {
      showModelDropdown.value = true;
    } else {
      await globalAlert.showError('未获取到可用的嵌入模型，请检查 Provider、URL 和配置是否正确。', '获取模型失败');
    }
  } catch (error) {
    console.error('Failed to load embedding models:', error);
    await globalAlert.showError('获取模型列表失败，请检查网络连接和配置。', '获取模型失败');
  } finally {
    isLoadingModels.value = false;
  }
};

const selectModel = (model: string) => {
  config.value.embedding_model = model;
  showModelDropdown.value = false;
};

const hideDropdown = () => {
  setTimeout(() => {
    showModelDropdown.value = false;
  }, 200);
};
</script>
