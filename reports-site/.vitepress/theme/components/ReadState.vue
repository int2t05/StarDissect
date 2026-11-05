<script setup lang="ts">
// 已读/收藏（REQ-READ-006）：PATCH /api/reports/{vid}/state，服务端落库
import { onMounted, ref, watch } from 'vue'
import { useData } from 'vitepress'

const vid = useData().frontmatter.value.vid as number | undefined
const state = ref({ read: false, favorited: false })

onMounted(load)
watch(() => useData().frontmatter.value.vid, load)

async function load(): Promise<void> {
  if (!vid) return
  try {
    const r = await fetch(`/api/reports/${vid}`)
    if (!r.ok) return
    const report = await r.json()
    state.value = { read: !!report.read, favorited: !!report.favorited }
  } catch {
    // 管理面 API 不可达（纯静态浏览）：按钮仍可见，点了报错即可
  }
}

async function toggle(field: 'read' | 'favorited'): Promise<void> {
  if (!vid) return
  try {
    await fetch(`/api/reports/${vid}/state`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [field]: !state.value[field] }),
    })
    state.value[field] = !state.value[field]
  } catch {
    // 上报失败保持原状：状态归服务端管
  }
}
</script>

<template>
  <span v-if="vid" class="sd-state">
    <button type="button" :class="{ on: state.read }" @click="toggle('read')">
      {{ state.read ? '✓ 已读 (m)' : '标为已读 (m)' }}
    </button>
    <button type="button" :class="{ on: state.favorited }" @click="toggle('favorited')">
      {{ state.favorited ? '★ 已收藏 (f)' : '☆ 收藏 (f)' }}
    </button>
  </span>
</template>

<style scoped>
.sd-state { display: inline-flex; gap: 8px; }
.sd-state button {
  font: inherit; font-size: 12px; cursor: pointer; color: var(--vp-c-text-2);
  background: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider); border-radius: 6px; padding: 2px 10px;
}
.sd-state button:hover { color: var(--vp-c-brand-1); border-color: var(--vp-c-brand-1); }
.sd-state button.on { color: var(--vp-c-brand-1); border-color: var(--vp-c-brand-1); background: var(--vp-c-brand-soft); }
</style>
