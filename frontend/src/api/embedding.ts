import { useAuthStore } from '@/stores/auth';

const API_PREFIX = '/api';
const EMBEDDING_BASE = `${API_PREFIX}/embedding-config`;

export type EmbeddingProvider = 'openai' | 'ollama';

export interface EmbeddingConfig {
  user_id: number;
  embedding_provider: EmbeddingProvider | null;
  embedding_base_url: string | null;
  embedding_api_key: string | null;
  embedding_model: string | null;
  embedding_model_vector_size: number | null;
  has_api_key: boolean;
}

export interface EmbeddingConfigCreate {
  embedding_provider?: EmbeddingProvider;
  embedding_base_url?: string | null;
  embedding_api_key?: string | null;
  embedding_model?: string | null;
  embedding_model_vector_size?: number | null;
}

export interface EmbeddingModelListRequest {
  embedding_provider: EmbeddingProvider;
  embedding_base_url?: string;
  embedding_api_key?: string;
}

const getHeaders = () => {
  const authStore = useAuthStore();
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${authStore.token}`,
  };
};

export const getEmbeddingConfig = async (): Promise<EmbeddingConfig | null> => {
  const response = await fetch(EMBEDDING_BASE, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error('Failed to fetch embedding config');
  }
  return response.json();
};

export const createOrUpdateEmbeddingConfig = async (
  config: EmbeddingConfigCreate,
): Promise<EmbeddingConfig> => {
  const response = await fetch(EMBEDDING_BASE, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    throw new Error('Failed to save embedding config');
  }
  return response.json();
};

export const deleteEmbeddingConfig = async (): Promise<void> => {
  const response = await fetch(EMBEDDING_BASE, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to delete embedding config');
  }
};

export const getAvailableEmbeddingModels = async (
  request: EmbeddingModelListRequest,
): Promise<string[]> => {
  const response = await fetch(`${EMBEDDING_BASE}/models`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    return [];
  }
  return response.json();
};
