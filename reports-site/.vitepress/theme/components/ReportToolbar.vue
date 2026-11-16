<script setup lang="ts">
// 报告阅读工具：放在左侧栏,仅报告页显示。
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
  <div v-if="isReport" class="reader-toolbar">
    <section class="reader-block" aria-label="报告信息">
      <p class="reader-label">报告信息</p>
      <div class="reader-meta">
        <b>{{ frontmatter.repo }}</b>
        <span v-for="part in meta" :key="part">{{ part }}</span>
      </div>
    </section>
    <section class="reader-block" aria-label="阅读状态">
      <p class="reader-label">阅读状态</p>
      <ReadState />
    </section>
    <section class="reader-block" aria-label="阅读排版">
      <p class="reader-label">阅读排版</p>
      <ReaderSettings />
    </section>
    <section class="reader-block" aria-label="阅读进度">
      <p class="reader-label">阅读进度</p>
      <ProgressTracker />
    </section>
  </div>
</template>
