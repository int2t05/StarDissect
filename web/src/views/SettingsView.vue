<!-- 系统设置:凭据/AI/限额配置,密钥回显仅尾号(REQ-CFG-001/002,US-10) -->
<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const form = ref({})
const lastSync = ref(null)
const saved = ref(false)

async function load() {
  form.value = await api('/api/settings')
  lastSync.value = await api('/api/sync')
}

async function save() {
  const body = { ...form.value }
  for (const k of ['github_token', 'ai_api_key']) {
    if ((body[k] || '').startsWith('…')) body[k] = ''  // 掩码回显=不修改,置空交后端保留原值
  }
  await api('/api/settings', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  saved.value = true
  setTimeout(() => (saved.value = false), 2000)
  await load()
}

async function syncNow() {
  await api('/api/sync', { method: 'POST' })
  setTimeout(load, 3000)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <h1>系统设置</h1>
    <form class="form" @submit.prevent="save">
      <label>GitHub Token(仅存服务端)<input v-model="form.github_token" type="password" :placeholder="form.github_token || 'ghp_…'" /></label>
      <label>AI 模型<input v-model="form.ai_model" placeholder="anthropic:claude-haiku-4-5-20251001 或 openai:gpt-4o-mini" /></label>
      <label>AI API Key(仅存服务端)<input v-model="form.ai_api_key" type="password" :placeholder="form.ai_api_key || 'sk-…'" /></label>
      <label>单任务轮次上限<input v-model="form.turn_limit" type="number" min="1" /></label>
      <label>单任务时限(秒)<input v-model="form.time_limit_sec" type="number" min="60" /></label>
      <p class="hint" v-if="lastSync && !lastSync.never">
        最近同步:{{ lastSync.finished_at || lastSync.started_at }} · 新增 {{ lastSync.added }} / 取消 {{ lastSync.removed }} / 跳过 {{ lastSync.skipped }}<span v-if="lastSync.failed"> / 失败 {{ lastSync.failed }}</span>
      </p>
      <div class="row">
        <button type="submit">{{ saved ? '已保存 ✓' : '保存' }}</button>
        <button type="button" @click="syncNow">立即同步 star</button>
        <a href="/rss.xml" target="_blank">RSS 地址</a>
      </div>
      <p class="hint">外网暴露请务必使用反向代理加鉴权保护(DEC-04/OPN-08)。</p>
    </form>
  </div>
</template>

<style scoped>
.form { display: flex; flex-direction: column; gap: 12px; max-width: var(--sd-width); }
label { display: flex; flex-direction: column; gap: 4px; color: var(--sd-text-2); font-size: 0.9em; }
input { padding: 8px 10px; }
.row { display: flex; gap: 12px; align-items: center; }
.hint { color: var(--sd-text-3); font-size: 0.85em; }
</style>
