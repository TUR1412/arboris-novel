<!-- AIMETA P=写作台侧边栏_章节目录|R=章节列表_导航|NR=不含内容编辑|E=component:WDSidebar|X=ui|A=侧边栏|D=vue|S=dom|RD=./README.ai -->
<template>
  <div>
    <!-- 侧边栏遮罩 (移动端) -->
    <div
      v-if="sidebarOpen"
      @click="$emit('closeSidebar')"
      class="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 lg:hidden"
    ></div>

    <!-- 左侧：蓝图和章节列表 -->
    <div
      :class="[
        'md-card md-card-elevated transition-all duration-300 h-full',
        'lg:relative lg:translate-x-0 lg:w-80 lg:flex-shrink-0',
        sidebarOpen
          ? 'fixed left-4 top-20 bottom-4 w-80 z-50 translate-x-0'
          : 'lg:w-80 lg:flex-shrink-0 -translate-x-full absolute lg:relative'
      ]"
      style="border-radius: var(--md-radius-xl);"
    >
      <div class="h-full flex flex-col">
        <!-- 蓝图预览卡片 -->
        <div class="md-card-header flex-shrink-0">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-full flex items-center justify-center" style="background-color: var(--md-primary-container);">
              <svg class="w-5 h-5" style="color: var(--md-on-primary-container);" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
            </div>
            <div>
              <h2 class="md-title-medium font-semibold">故事蓝图</h2>
              <p class="md-body-small md-on-surface-variant">{{ project.blueprint?.style || '未设定风格' }}</p>
            </div>
          </div>

          <div class="space-y-3">
            <div class="md-card md-card-filled p-3" style="border-radius: var(--md-radius-md);">
              <h3 class="md-label-large font-semibold" style="color: var(--md-on-primary-container);">故事概要</h3>
              <Tooltip :text="project.blueprint?.one_sentence_summary">
                <p class="md-body-small line-clamp-3" style="color: var(--md-on-surface-variant);">{{ project.blueprint?.one_sentence_summary || '暂无概要' }}</p>
              </Tooltip>
            </div>
            <div class="grid grid-cols-2 gap-2 text-xs">
              <div class="md-card md-card-outlined p-2 text-center" style="border-radius: var(--md-radius-md);">
                <div class="md-title-small font-semibold" style="color: var(--md-primary);">{{ characterCount }}</div>
                <div class="md-label-small md-on-surface-variant">角色</div>
              </div>
              <div class="md-card md-card-outlined p-2 text-center" style="border-radius: var(--md-radius-md);">
                <div class="md-title-small font-semibold" style="color: var(--md-secondary);">{{ relationshipCount }}</div>
                <div class="md-label-small md-on-surface-variant">关系</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 章节列表 -->
        <div ref="listContainer" class="flex-1 overflow-y-auto wd-sidebar-scroll">
          <div class="p-6 pb-4 space-y-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <h3 class="md-title-medium font-semibold">章节大纲</h3>
                <p class="md-body-small md-on-surface-variant">{{ sidebarHintText }}</p>
              </div>
              <div class="flex items-center gap-2">
                <button
                  v-if="totalChapters > 0"
                  @click.stop="scrollChapterList('top')"
                  class="md-icon-btn md-ripple"
                  title="回到顶部"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7" />
                  </svg>
                </button>
                <button
                  v-if="totalChapters > 0"
                  @click.stop="scrollChapterList('bottom')"
                  class="md-icon-btn md-ripple"
                  title="跳到底部"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                <span class="md-chip md-chip-filter selected">
                  {{ totalChapters }} 章
                </span>
              </div>
            </div>

            <div class="md-card md-card-filled p-3 wd-sidebar-tools" style="border-radius: var(--md-radius-lg);">
              <div class="flex items-center gap-2">
                <label class="wd-sidebar-search">
                  <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35m1.85-5.15a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    v-model="searchQuery"
                    type="text"
                    class="wd-sidebar-search__input"
                    placeholder="按章节号、标题或摘要查找"
                  >
                </label>
                <button
                  v-if="searchQuery"
                  class="md-icon-btn md-ripple"
                  title="清空搜索"
                  @click="clearSearch"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div class="mt-3 flex flex-wrap items-center gap-2">
                <button
                  v-for="filter in chapterFilters"
                  :key="filter.key"
                  @click="statusFilter = filter.key"
                  :class="[
                    'md-chip md-chip-filter md-ripple',
                    statusFilter === filter.key ? 'selected' : ''
                  ]"
                >
                  {{ filter.label }}
                </button>
                <button
                  v-if="hasIncompleteChapters"
                  @click.stop="scrollToFirstIncompleteChapter"
                  class="md-btn md-btn-text md-ripple"
                >
                  定位到未完成
                </button>
                <button
                  v-if="useGroupedView"
                  @click="expandAllGroups"
                  class="md-btn md-btn-text md-ripple"
                >
                  展开全部
                </button>
                <button
                  v-if="useGroupedView"
                  @click="collapseAllGroups"
                  class="md-btn md-btn-text md-ripple"
                >
                  聚焦关键分组
                </button>
              </div>
            </div>
          </div>

          <div class="px-6 pb-6">
            <div v-if="filteredOutline.length" class="space-y-4">
              <section
                v-for="group in chapterGroups"
                :key="group.key"
                class="md-card md-card-outlined p-3"
                style="border-radius: var(--md-radius-lg);"
              >
                <button
                  v-if="useGroupedView"
                  class="wd-group-toggle"
                  @click="toggleGroup(group.key)"
                >
                  <div>
                    <p class="md-label-large font-semibold">{{ group.label }}</p>
                    <p class="md-body-small md-on-surface-variant">
                      {{ group.completedCount }}/{{ group.total }} 已完成，{{ group.pendingCount }} 章待推进
                    </p>
                  </div>
                  <svg
                    class="w-4 h-4 transition-transform duration-200"
                    :class="isGroupExpanded(group.key) ? 'rotate-180' : ''"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    stroke-width="2"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                <div
                  v-show="!useGroupedView || isGroupExpanded(group.key)"
                  :class="['space-y-3', useGroupedView ? 'pt-3' : '']"
                >
                  <div
                    v-for="(chapter, index) in group.chapters"
                    :key="chapter.chapter_number"
                    :ref="el => setChapterRef(chapter.chapter_number, el)"
                    @click="$emit('selectChapter', chapter.chapter_number)"
                    :class="[
                      'group cursor-pointer p-4 m3-chapter-card',
                      shouldAnimateCards ? 'm3-stagger' : '',
                      selectedForDeletion.includes(chapter.chapter_number)
                        ? 'm3-chapter-danger'
                        : selectedChapterNumber === chapter.chapter_number
                        ? 'm3-chapter-selected md-elevation-1'
                        : 'hover:md-elevation-1'
                    ]"
                    :style="getCardAnimationStyle(index)"
                  >
                    <div class="flex items-start gap-3">
                      <div class="flex-shrink-0 pt-1">
                        <input
                          type="checkbox"
                          :disabled="isChapterCompleted(chapter.chapter_number)"
                          :checked="selectedForDeletion.includes(chapter.chapter_number)"
                          @click.stop="toggleSelection(chapter.chapter_number)"
                          class="h-4 w-4 rounded border-[var(--md-outline)] text-[var(--md-primary)] focus:ring-[var(--md-primary)] disabled:opacity-50 accent-[var(--md-primary)]"
                        />
                      </div>
                      <div
                        :class="[
                          'w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold flex-shrink-0',
                          isChapterCompleted(chapter.chapter_number)
                            ? 'bg-[var(--md-success)] text-[var(--md-on-success)]'
                            : isChapterGenerating(chapter.chapter_number) || isChapterEvaluating(chapter.chapter_number) || isChapterSelecting(chapter.chapter_number)
                            ? 'bg-[var(--md-primary)] text-[var(--md-on-primary)] animate-pulse'
                            : isChapterFailed(chapter.chapter_number)
                            ? 'bg-[var(--md-error)] text-[var(--md-on-error)]'
                            : selectedChapterNumber === chapter.chapter_number
                            ? 'bg-[var(--md-primary)] text-[var(--md-on-primary)]'
                            : 'bg-[var(--md-surface-container-highest)] text-[var(--md-on-surface-variant)]'
                        ]"
                      >
                        <svg v-if="isChapterCompleted(chapter.chapter_number)" class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
                        </svg>
                        <svg v-else-if="isChapterGenerating(chapter.chapter_number) || isChapterSelecting(chapter.chapter_number)" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                          <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                        </svg>
                        <svg v-else-if="isChapterEvaluating(chapter.chapter_number)" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M10 2a6 6 0 00-6 6v3.586l-1.707 1.707A1 1 0 003 15v1a1 1 0 001 1h12a1 1 0 001-1v-1a1 1 0 00-.293-.707L16 11.586V8a6 6 0 00-6-6zM8.05 17a2 2 0 103.9 0H8.05z"></path>
                        </svg>
                        <svg v-else-if="isChapterFailed(chapter.chapter_number)" class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                        </svg>
                        <span v-else>{{ chapter.chapter_number }}</span>
                      </div>
                      <div class="flex-1 min-w-0">
                        <Tooltip :text="chapter.title">
                          <h4 class="md-body-large font-semibold mb-1 line-clamp-1">{{ chapter.title }}</h4>
                        </Tooltip>
                        <Tooltip :text="chapter.summary">
                          <p class="md-body-small md-on-surface-variant line-clamp-2 leading-relaxed">{{ chapter.summary }}</p>
                        </Tooltip>

                        <div class="mt-2 flex items-center gap-2 flex-wrap">
                          <span
                            v-if="isChapterCompleted(chapter.chapter_number)"
                            class="md-chip"
                            style="background-color: var(--md-success-container); color: var(--md-on-success-container);"
                          >
                            已完成
                          </span>
                          <span
                            v-else-if="isChapterGenerating(chapter.chapter_number)"
                            class="md-chip animate-pulse"
                            style="background-color: var(--md-primary-container); color: var(--md-on-primary-container);"
                          >
                            生成中...
                          </span>
                          <span
                            v-else-if="isChapterSelecting(chapter.chapter_number)"
                            class="md-chip animate-pulse"
                            style="background-color: var(--md-primary-container); color: var(--md-on-primary-container);"
                          >
                            选择中...
                          </span>
                          <span
                            v-else-if="isChapterEvaluating(chapter.chapter_number)"
                            class="md-chip animate-pulse"
                            style="background-color: var(--md-secondary-container); color: var(--md-on-secondary-container);"
                          >
                            评审中...
                          </span>
                          <span
                            v-else-if="isChapterFailed(chapter.chapter_number)"
                            class="md-chip"
                            style="background-color: var(--md-error-container); color: var(--md-on-error-container);"
                          >
                            生成失败
                          </span>
                          <span
                            v-else-if="hasChapterInProgress(chapter.chapter_number)"
                            class="md-chip"
                            style="background-color: var(--md-warning-container); color: var(--md-on-warning-container);"
                          >
                            待选择版本
                          </span>
                          <span v-else class="md-chip md-chip-assist">未开始</span>
                        </div>
                      </div>

                      <div class="flex items-center opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                        <button
                          v-if="!isChapterCompleted(chapter.chapter_number)"
                          @click.stop="$emit('editChapter', chapter)"
                          class="md-icon-btn md-ripple"
                          title="编辑大纲"
                        >
                          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z"></path>
                            <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd"></path>
                          </svg>
                        </button>
                        <button
                          v-if="canGenerateChapter(chapter.chapter_number) || isChapterFailed(chapter.chapter_number) || hasChapterInProgress(chapter.chapter_number)"
                          @click.stop="confirmGenerateChapter(chapter.chapter_number)"
                          :disabled="generatingChapter === chapter.chapter_number || isChapterGenerating(chapter.chapter_number)"
                          class="md-icon-btn md-ripple disabled:opacity-50"
                          style="color: var(--md-primary);"
                          :title="isChapterCompleted(chapter.chapter_number) ? '重新生成' : isChapterFailed(chapter.chapter_number) ? '重试' : hasChapterInProgress(chapter.chapter_number) ? '重新生成版本' : '开始创作'"
                        >
                          <svg v-if="generatingChapter === chapter.chapter_number || isChapterGenerating(chapter.chapter_number)" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                          </svg>
                          <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            </div>
            <div v-else class="text-center py-8 md-body-medium md-on-surface-variant">
              <svg class="w-12 h-12 mx-auto mb-3 opacity-50" fill="currentColor" viewBox="0 0 20 20">
                <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4zM18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9z"></path>
              </svg>
              <p>{{ searchQuery || statusFilter !== 'all' ? '当前筛选条件下没有匹配章节' : '暂无章节大纲' }}</p>
            </div>
            <div v-if="selectedForDeletion.length > 0" class="mt-4">
              <button
                @click="handleDeleteSelected"
                class="md-btn md-btn-filled md-ripple w-full flex items-center justify-center gap-2"
                style="background-color: var(--md-error); color: var(--md-on-error);"
              >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd"></path>
                </svg>
                <span>删除选中的 {{ selectedForDeletion.length }} 章</span>
              </button>
            </div>
            <div class="mt-4">
              <button
                @click="$emit('generateOutline')"
                :disabled="props.isGeneratingOutline"
                class="md-btn md-btn-tonal md-ripple w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg v-if="props.isGeneratingOutline" class="w-5 h-5 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                </svg>
                <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
                </svg>
                <span>{{ props.isGeneratingOutline ? '生成中...' : '生成后续大纲' }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, watch } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import type { NovelProject, ChapterOutline as ChapterOutlineItem } from '@/api/novel'
import Tooltip from '@/components/Tooltip.vue'

interface Props {
  project: NovelProject
  sidebarOpen: boolean
  selectedChapterNumber: number | null
  generatingChapter: number | null
  evaluatingChapter: number | null
  isGeneratingOutline: boolean
}

type OutlineFilter = 'all' | 'pending' | 'completed'

interface ChapterGroup {
  key: string
  label: string
  total: number
  completedCount: number
  pendingCount: number
  chapters: ChapterOutlineItem[]
}

const props = defineProps<Props>()

const emit = defineEmits(['closeSidebar', 'selectChapter', 'generateChapter', 'editChapter', 'deleteChapter', 'generateOutline'])

const selectedForDeletion = ref<number[]>([])
const listContainer = ref<HTMLElement | null>(null)
const chapterRefs = ref<Record<number, HTMLElement | null>>({})
const searchQuery = ref('')
const statusFilter = ref<OutlineFilter>('all')
const expandedGroupKeys = ref<string[]>([])

const chapterFilters: Array<{ key: OutlineFilter; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待写' },
  { key: 'completed', label: '已完成' }
]

const characterCount = computed(() => {
  return props.project?.blueprint?.characters?.length || 0
})

const relationshipCount = computed(() => {
  return props.project?.blueprint?.relationships?.length || 0
})

const lastChapterNumber = computed(() => {
  if (!props.project?.blueprint?.chapter_outline || props.project.blueprint.chapter_outline.length === 0) {
    return null
  }
  return Math.max(...props.project.blueprint.chapter_outline.map(ch => ch.chapter_number))
})

const totalChapters = computed(() => {
  return props.project?.blueprint?.chapter_outline?.length || 0
})

const hasIncompleteChapters = computed(() => {
  if (!props.project?.blueprint?.chapter_outline) return false
  return props.project.blueprint.chapter_outline.some(ch => !isChapterCompleted(ch.chapter_number))
})

const filteredOutline = computed<ChapterOutlineItem[]>(() => {
  const outlines = [...(props.project?.blueprint?.chapter_outline || [])].sort(
    (a, b) => a.chapter_number - b.chapter_number
  )
  const query = searchQuery.value.trim().toLowerCase()

  return outlines.filter((chapter) => {
    const matchesStatus =
      statusFilter.value === 'all' ||
      (statusFilter.value === 'completed' && isChapterCompleted(chapter.chapter_number)) ||
      (statusFilter.value === 'pending' && !isChapterCompleted(chapter.chapter_number))

    if (!matchesStatus) {
      return false
    }

    if (!query) {
      return true
    }

    return (
      String(chapter.chapter_number).includes(query) ||
      chapter.title.toLowerCase().includes(query) ||
      chapter.summary.toLowerCase().includes(query)
    )
  })
})

const useGroupedView = computed(() => filteredOutline.value.length > 12 && !searchQuery.value.trim())

const chapterGroups = computed<ChapterGroup[]>(() => {
  if (!filteredOutline.value.length) {
    return []
  }

  if (!useGroupedView.value) {
    const completedCount = filteredOutline.value.filter((chapter) =>
      isChapterCompleted(chapter.chapter_number)
    ).length
    return [
      {
        key: 'all',
        label: searchQuery.value.trim() ? '搜索结果' : '当前章节',
        total: filteredOutline.value.length,
        completedCount,
        pendingCount: filteredOutline.value.length - completedCount,
        chapters: filteredOutline.value
      }
    ]
  }

  const groups = new Map<string, ChapterGroup>()
  for (const chapter of filteredOutline.value) {
    const groupStart = Math.floor((chapter.chapter_number - 1) / 10) * 10 + 1
    const groupEnd = groupStart + 9
    const key = `${groupStart}-${groupEnd}`

    if (!groups.has(key)) {
      groups.set(key, {
        key,
        label: `第 ${groupStart}-${groupEnd} 章`,
        total: 0,
        completedCount: 0,
        pendingCount: 0,
        chapters: []
      })
    }

    const group = groups.get(key)!
    group.chapters.push(chapter)
    group.total += 1
    if (isChapterCompleted(chapter.chapter_number)) {
      group.completedCount += 1
    } else {
      group.pendingCount += 1
    }
  }

  return Array.from(groups.values())
})

const sidebarHintText = computed(() => {
  if (searchQuery.value.trim()) {
    return `当前匹配到 ${filteredOutline.value.length} 个章节，已展开便于定位`
  }
  if (useGroupedView.value) {
    return '按 10 章自动折叠浏览，减少长距离滚动和误滑空白'
  }
  if (statusFilter.value === 'pending') {
    return '当前只显示待写章节'
  }
  if (statusFilter.value === 'completed') {
    return '当前只显示已完成章节'
  }
  return '可搜索、筛选、折叠章节区间，减少反复滑动'
})

const shouldAnimateCards = computed(() => filteredOutline.value.length <= 16)

const getCardAnimationStyle = (index: number) => {
  if (!shouldAnimateCards.value) {
    return undefined
  }
  return { animationDelay: `${Math.min(index, 4) * 35}ms` }
}

const getGroupKeyForChapter = (chapterNumber: number | null) => {
  if (!chapterNumber) {
    return null
  }
  return (
    chapterGroups.value.find((group) =>
      group.chapters.some((chapter) => chapter.chapter_number === chapterNumber)
    )?.key || null
  )
}

const getFirstPendingGroupKey = () => {
  return chapterGroups.value.find((group) => group.pendingCount > 0)?.key || null
}

const syncExpandedGroups = () => {
  const validKeys = chapterGroups.value.map((group) => group.key)
  if (!validKeys.length) {
    expandedGroupKeys.value = []
    return
  }

  if (!useGroupedView.value || searchQuery.value.trim()) {
    expandedGroupKeys.value = validKeys
    return
  }

  const next = expandedGroupKeys.value.filter((key) => validKeys.includes(key))
  const defaults = [validKeys[0], getGroupKeyForChapter(props.selectedChapterNumber), getFirstPendingGroupKey()]

  for (const key of defaults) {
    if (key && !next.includes(key)) {
      next.push(key)
    }
  }
  expandedGroupKeys.value = next
}

watch(
  [chapterGroups, () => props.selectedChapterNumber, searchQuery, statusFilter],
  () => {
    syncExpandedGroups()
  },
  { immediate: true }
)

const scrollChapterList = (direction: 'top' | 'bottom') => {
  const container = listContainer.value
  if (!container) return
  container.scrollTo({
    top: direction === 'top' ? 0 : container.scrollHeight,
    behavior: 'smooth'
  })
}

const clearSearch = () => {
  searchQuery.value = ''
}

const isGroupExpanded = (key: string) => {
  return !useGroupedView.value || expandedGroupKeys.value.includes(key)
}

const toggleGroup = (key: string) => {
  if (!useGroupedView.value) {
    return
  }
  if (expandedGroupKeys.value.includes(key)) {
    expandedGroupKeys.value = expandedGroupKeys.value.filter((item) => item !== key)
  } else {
    expandedGroupKeys.value = [...expandedGroupKeys.value, key]
  }
}

const expandAllGroups = () => {
  expandedGroupKeys.value = chapterGroups.value.map((group) => group.key)
}

const collapseAllGroups = () => {
  expandedGroupKeys.value = []
  syncExpandedGroups()
}

function toggleSelection(chapterNumber: number) {
  if (isChapterCompleted(chapterNumber)) return
  const index = selectedForDeletion.value.indexOf(chapterNumber)
  if (index > -1) {
    selectedForDeletion.value.splice(index, 1)
  } else {
    selectedForDeletion.value.push(chapterNumber)
  }
}

function handleDeleteSelected() {
  if (selectedForDeletion.value.length === 0) return

  const sortedSelection = [...selectedForDeletion.value].sort((a, b) => a - b)

  if (!lastChapterNumber.value || !sortedSelection.includes(lastChapterNumber.value)) {
    void globalAlert.showError('批量删除必须包含最后一章。', '无法删除章节')
    return
  }

  const isContinuous = sortedSelection.every((num, i) => {
    return i === 0 || num === sortedSelection[i - 1] + 1
  })
  if (!isContinuous) {
    void globalAlert.showError('只能删除连续的章节块。', '无法删除章节')
    return
  }

  emit('deleteChapter', sortedSelection)
  selectedForDeletion.value = []
}

async function confirmGenerateChapter(chapterNumber: number) {
  const confirmed = await globalAlert.showConfirm('重新生成会覆盖当前章节的生成结果，确定继续吗？', '重新生成确认')
  if (confirmed) {
    emit('generateChapter', chapterNumber)
  }
}

function setChapterRef(chapterNumber: number, el: Element | ComponentPublicInstance | null) {
  if (!el) {
    delete chapterRefs.value[chapterNumber]
    return
  }

  const element = el instanceof Element ? el : (el.$el instanceof Element ? el.$el : null)

  if (element) {
    chapterRefs.value[chapterNumber] = element as HTMLElement
  }
}

const scrollToFirstIncompleteChapter = async () => {
  if (!props.project?.blueprint?.chapter_outline) return
  const sorted = [...props.project.blueprint.chapter_outline].sort((a, b) => a.chapter_number - b.chapter_number)
  const target = sorted.find(chapter => !isChapterCompleted(chapter.chapter_number))
  if (!target) return
  await nextTick()
  const element = chapterRefs.value[target.chapter_number]
  if (!element) return
  const container = listContainer.value
  if (container) {
    element.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
  } else {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

// 章节状态检查
const isChapterCompleted = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'successful'
}

const hasChapterInProgress = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'waiting_for_confirm'
}

const isChapterGenerating = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'generating'
}

const isChapterEvaluating = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'evaluating'
}

const isChapterFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const isChapterSelecting = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'selecting'
}

const canGenerateChapter = (chapterNumber: number) => {
  if (!props.project?.blueprint?.chapter_outline) return false

  const outlines = [...props.project.blueprint.chapter_outline].sort((a, b) => a.chapter_number - b.chapter_number)
  
  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break
    
    const chapter = props.project?.chapters.find(ch => ch.chapter_number === outline.chapter_number)
    if (!chapter || chapter.generation_status !== 'successful') {
      return false
    }
  }

  const currentChapter = props.project?.chapters.find(ch => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true
  }

  return true
}
</script>

<style scoped>
.wd-sidebar-scroll {
  overscroll-behavior: contain;
  scroll-padding-top: 16px;
}

.wd-sidebar-tools {
  position: sticky;
  top: 12px;
  z-index: 4;
}

.wd-sidebar-search {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 42px;
  padding: 0 12px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-full);
  background-color: var(--md-surface);
  color: var(--md-on-surface-variant);
}

.wd-sidebar-search__input {
  width: 100%;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--md-on-surface);
  font-size: 0.92rem;
}

.wd-group-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 12px;
  text-align: left;
  color: var(--md-on-surface);
}

.m3-chapter-card {
  border-radius: var(--md-radius-lg);
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface);
  transition: all var(--md-duration-medium) var(--md-easing-standard);
}

.m3-chapter-card:hover {
  background-color: var(--md-surface-container-low);
}

.m3-chapter-selected {
  border-color: var(--md-primary);
  background-color: var(--md-primary-container);
}

.m3-chapter-danger {
  border-color: var(--md-error);
  background-color: var(--md-error-container);
}

.m3-stagger {
  animation: m3-rise 0.45s ease-out both;
}

@keyframes m3-rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
