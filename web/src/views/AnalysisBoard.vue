<!-- 分析管理:队列状态、暂停/恢复、优先级、取消、重试(REQ-TASK-001..005,US-04) -->
<script setup>
import { api } from '../api'
import { onMounted, onUnmounted, ref } from 'vue'

const data = ref({ paused: false, tasks: [] })
let timer = null

async function load() {
  data.value = await api('/api/tasks')
}

async function togglePause() {
  await api('/api/queue', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paused: !data.value.paused }) })
  await load()
}

async function cancel(id) {
  await api(`/api/tasks/${id}`, { method: 'DELETE' })
  await load()
}

async function retry(id) {
  await api(`/api/tasks/${id}/retry`, { method: 'POST' })
  await load()
}

async function setPriority(id, priority) {
  await api(`/api/tasks/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ priority }) })
  await load()
}

async function syncNow() {
  await api('/api/sync', { method: 'POST' })
}

onMounted(() => { load(); timer = setInterval(load, 3000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="page">
    <h1>分析管理</h1>
    <div class="bar">
      <button @click="togglePause">{{ data.paused ? '恢复队列' : '暂停队列' }}</button>
      <button @click="syncNow">立即同步</button>
    </div>
    <table>
      <thead>
        <tr><th>仓库</th><th>类型</th><th>状态</th><th>优先级</th><th>原因</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="t in data.tasks" :key="t.id">
          <td>{{ t.full_name }}</td>
          <td>{{ t.kind === 'reanalyze' ? '重分析' : '分析' }}</td>
          <td><span :class="['st', t.status]">{{ t.status }}</span></td>
          <td>
            <template v-if="t.status === '排队'">
              <input type="number" :value="t.priority" min="0" style="width:64px" @change="setPriority(t.id, $event.target.value)" />
            </template>
            <template v-else>{{ t.priority }}</template>
          </td>
          <td class="why">{{ t.fail_reason }}</td>
          <td>
            <button v-if="t.status === '排队'" @click="cancel(t.id)">取消</button>
            <button v-if="['失败', '中断'].includes(t.status)" @click="retry(t.id)">重试</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="!data.tasks.length" class="hint">队列为空。在「仓库库」触发分析,或同步 star 自动入库。</p>
  </div>
</template>

<style scoped>
.bar { display: flex; gap: 8px; margin: 12px 0; }
table { width: 100%; max-width: var(--sd-width); border-collapse: collapse; font-size: 0.92em; }
th, td { text-align: left; padding: 8px; border-bottom: 1px solid var(--sd-border); }
.why { color: var(--sd-text-3); font-size: 0.85em; }
.st { font-weight: 600; }
.st.排队, .st.进行 { color: var(--sd-accent); }
.st.完成 { color: var(--sd-ev-source); }
.st.失败, .st.中断 { color: var(--sd-text-3); }
.hint { color: var(--sd-text-3); }
</style>
