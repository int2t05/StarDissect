<!-- 系统设置:凭据/AI/限额配置,密钥回显仅尾号(REQ-CFG-001/002,US-10) -->
<script setup>
import { onMounted, ref } from 'vue'
import { NAlert, NButton, NForm, NFormItem, NInput } from 'naive-ui'
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
  <div class="page narrow">
    <header class="bar"><h1>系统设置</h1></header>
    <n-form label-placement="top" class="form" @submit.prevent="save">
      <n-form-item label="GitHub Token(仅存服务端)">
        <n-input v-model:value="form.github_token" type="password" show-password-on="click" :placeholder="form.github_token || 'ghp_…'" />
      </n-form-item>
      <n-form-item label="AI 模型">
        <n-input v-model:value="form.ai_model" placeholder="anthropic:claude-haiku-4-5-20251001 / openai:gpt-4o-mini / 网关模型名" />
      </n-form-item>
      <n-form-item label="AI Base URL(OpenAI 兼容网关,可选)">
        <n-input v-model:value="form.ai_base_url" placeholder="https://…/v1" />
      </n-form-item>
      <n-form-item label="AI API Key(仅存服务端)">
        <n-input v-model:value="form.ai_api_key" type="password" show-password-on="click" :placeholder="form.ai_api_key || 'sk-…'" />
      </n-form-item>
      <n-form-item label="单任务轮次上限">
        <n-input v-model:value="form.turn_limit" placeholder="60" />
      </n-form-item>
      <n-form-item label="单任务时限(秒)">
        <n-input v-model:value="form.time_limit_sec" placeholder="1800" />
      </n-form-item>
      <n-alert v-if="lastSync && !lastSync.never" :type="lastSync.failed ? 'warning' : 'info'" :bordered="false">
        最近同步:{{ lastSync.finished_at || lastSync.started_at }} · 新增 {{ lastSync.added }} / 取消 {{ lastSync.removed }} / 跳过 {{ lastSync.skipped }}<span v-if="lastSync.failed"> / 失败 {{ lastSync.failed }}</span>
      </n-alert>
      <div class="row">
        <n-button attr-type="submit" type="primary" secondary>{{ saved ? '已保存 ✓' : '保存' }}</n-button>
        <n-button secondary @click="syncNow">立即同步 star</n-button>
        <a href="/rss.xml" target="_blank">RSS 地址</a>
      </div>
      <p class="hint">外网暴露请务必使用反向代理加鉴权保护(DEC-04/OPN-08)。</p>
    </n-form>
  </div>
</template>

<style scoped>
.page.narrow { max-width: 640px; }
.form { display: flex; flex-direction: column; gap: 4px; }
.row { display: flex; gap: 12px; align-items: center; }
</style>
