<!-- AIMETA P=章节大纲区_大纲展示|R=大纲列表|NR=不含编辑功能|E=component:ChapterOutlineSection|X=ui|A=大纲组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">章节大纲</h2>
        <p class="text-sm text-slate-500">故事结构与章节节奏一目了然</p>
      </div>
      <div v-if="editable" class="flex items-center gap-2">
        <button
          type="button"
          class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg"
          @click="$emit('add')"
        >
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
          </svg>
          新增章节
        </button>
        <button
          type="button"
          class="flex items-center gap-1 px-3 py-2 text-sm text-gray-500 hover:text-indigo-600 transition-colors"
          @click="emitEdit('chapter_outline', '章节大纲', outline)"
        >
          <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
            <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
          </svg>
          编辑大纲
        </button>
      </div>
    </div>

    <div v-if="outline.length" class="outline-toolbar">
      <div class="outline-toolbar__group">
        <label class="outline-toolbar__label" for="outline-jump">快速跳转</label>
        <select
          id="outline-jump"
          v-model="selectedJumpTarget"
          class="outline-toolbar__select"
          @change="jumpToChapter"
        >
          <option value="">选择章节</option>
          <option
            v-for="chapter in outline"
            :key="chapter.chapter_number"
            :value="String(chapter.chapter_number)"
          >
            第{{ chapter.chapter_number }}章 · {{ chapter.title || `章节 ${chapter.chapter_number}` }}
          </option>
        </select>
      </div>
      <div class="outline-toolbar__actions">
        <button type="button" class="outline-toolbar__button" @click="scrollToTop">
          回到顶部
        </button>
        <button type="button" class="outline-toolbar__button" @click="scrollToBottom">
          跳到底部
        </button>
      </div>
    </div>

    <ol ref="outlineListRef" class="relative border-l border-slate-200 ml-3 space-y-8">
      <li
        v-for="chapter in outline"
        :key="chapter.chapter_number"
        :ref="(el) => setChapterRef(chapter.chapter_number, el)"
        class="ml-6"
      >
        <span class="absolute -left-3 mt-1 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500 text-white text-xs font-semibold">
          {{ chapter.chapter_number }}
        </span>
        <div class="bg-white/95 rounded-2xl border border-slate-200 shadow-sm p-5">
          <div class="flex items-center justify-between gap-4">
            <h3 class="text-lg font-semibold text-slate-900">{{ chapter.title || `第${chapter.chapter_number}章` }}</h3>
            <span class="text-xs text-slate-400">#{{ chapter.chapter_number }}</span>
          </div>
          <p class="mt-3 text-sm text-slate-600 leading-6 whitespace-pre-line">{{ chapter.summary || '暂无摘要' }}</p>
        </div>
      </li>
      <li v-if="!outline.length" class="ml-6 text-slate-400 text-sm">暂无章节大纲</li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import { defineEmits, defineProps, nextTick, ref } from 'vue'
import type { ComponentPublicInstance } from 'vue'

interface OutlineItem {
  chapter_number: number
  title: string
  summary: string
}

const props = defineProps<{
  outline: OutlineItem[]
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
  (e: 'add'): void
}>()

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}

const outlineListRef = ref<HTMLOListElement | null>(null)
const selectedJumpTarget = ref('')
const chapterRefs = ref<Record<number, HTMLElement | null>>({})

const setChapterRef = (chapterNumber: number, el: Element | ComponentPublicInstance | null) => {
  if (!el) {
    delete chapterRefs.value[chapterNumber]
    return
  }

  const element = el instanceof Element ? el : (el.$el instanceof Element ? el.$el : null)
  if (element) {
    chapterRefs.value[chapterNumber] = element as HTMLElement
  }
}

const jumpToChapter = async () => {
  const chapterNumber = Number(selectedJumpTarget.value)
  if (!chapterNumber) return
  await nextTick()
  chapterRefs.value[chapterNumber]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const scrollToTop = () => {
  outlineListRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const scrollToBottom = async () => {
  await nextTick()
  const lastChapter = props.outline[props.outline.length - 1]
  if (!lastChapter) return
  chapterRefs.value[lastChapter.chapter_number]?.scrollIntoView({ behavior: 'smooth', block: 'end' })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChapterOutlineSection'
})
</script>

<style scoped>
.outline-toolbar {
  position: sticky;
  top: 12px;
  z-index: 5;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(12px);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
}

.outline-toolbar__group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.outline-toolbar__label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #475569;
}

.outline-toolbar__select {
  min-width: min(320px, 60vw);
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  background: #fff;
  color: #0f172a;
  font-size: 0.875rem;
}

.outline-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.outline-toolbar__button {
  padding: 9px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #fff;
  color: #2563eb;
  font-size: 0.875rem;
  font-weight: 600;
  transition: all 0.2s ease;
}

.outline-toolbar__button:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

@media (max-width: 767px) {
  .outline-toolbar {
    top: 8px;
    align-items: stretch;
  }

  .outline-toolbar__group,
  .outline-toolbar__actions {
    width: 100%;
  }

  .outline-toolbar__select,
  .outline-toolbar__button {
    width: 100%;
  }
}
</style>
