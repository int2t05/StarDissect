<script setup lang="ts">
// 报告页工具条：元信息行 + 已读/收藏 + 排版调节 + 进度控制（doc-top 槽位，仅报告页显示）
import { computed } from 'vue'
import { useData } from 'vitepress'
import ProgressTracker from './ProgressTracker.vue'
import ReadState from './ReadState.vue'
import ReaderSettings from './ReaderSettings.vue'

const frontmatter = useData().frontmatter
const isReport = computed(() => !!frontmatter.value.vid)
const meta = computed(() => {
  const fm = frontmatter.value
  const parts: string[] = []
  if (fm.version) parts.push(`第 ${fm.version} 次分析`)
  if (fm.commit) parts.push(`commit ${String(fm.commit).slice(0, 8)}`)
  if (fm.generated_at) parts.push(String(fm.generated_at).slice(0, 10))
  return parts
})
</script>

<template>
  <div v-if="isReport" class="sd-toolbar">
    <div class="sd-meta">
      <b>{{ frontmatter.repo }}</b>
      <span v-for="part in meta" :key="part">{{ part }}</span>
    </div>
    <div class="sd-rows">
      <ReadState />
      <ReaderSettings />
      <ProgressTracker />
    </div>
  </div>
</template>

<style scoped>
.sd-toolbar {
  display: flex; flex-direction: column; gap: 8px;
  border: 1px solid var(--vp-c-divider); border-radius: 8px;
  background: var(--vp-c-bg-soft); padding: 10px 14px; margin: 12px 0 20px;
}
.sd-meta { display: flex; gap: 14px; flex-wrap: wrap; font-size: 13px; color: var(--vp-c-text-2); }
.sd-meta b { color: var(--vp-c-text-1); }
.sd-rows { display: flex; gap: 18px; flex-wrap: wrap; align-items: center; }
</style>
