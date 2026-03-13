<!-- AIMETA P=设置页_用户设置|R=用户设置表单|NR=不含管理员设置|E=route:/settings#component:SettingsView|X=ui|A=设置表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="min-h-screen p-4 relative">
    <div class="absolute top-4 left-4">
      <router-link
        to="/"
        class="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-2"
      >
        &larr; 返回
      </router-link>
    </div>
    <div class="flex flex-col md:flex-row max-w-6xl mx-auto mt-16">
      <!-- Sidebar -->
      <div class="w-full md:w-64 bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg p-4 mb-4 md:mb-0 md:mr-8">
        <h2 class="text-xl font-bold text-gray-800 mb-4">设置</h2>
        <nav>
          <ul>
            <li>
              <button
                type="button"
                @click="activeTab = 'llm'"
                :class="tabClass('llm')"
              >
                LLM 配置
              </button>
            </li>
            <li class="mt-2">
              <button
                type="button"
                @click="activeTab = 'embedding'"
                :class="tabClass('embedding')"
              >
                RAG 向量配置
              </button>
            </li>
          </ul>
        </nav>
      </div>

      <!-- Main Content -->
      <div class="flex-1">
        <LLMSettings v-if="activeTab === 'llm'" />
        <EmbeddingSettings v-else />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import EmbeddingSettings from '@/components/EmbeddingSettings.vue';
import LLMSettings from '@/components/LLMSettings.vue';

const activeTab = ref<'llm' | 'embedding'>('llm');

const tabClass = (tab: 'llm' | 'embedding') => {
  const baseClass = 'w-full text-left px-4 py-2 rounded-lg transition-colors';
  return activeTab.value === tab
    ? `${baseClass} bg-indigo-100 text-indigo-700`
    : `${baseClass} text-gray-700 hover:bg-gray-100`;
};
</script>
