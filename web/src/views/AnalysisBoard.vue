<!-- 分析管理:队列状态、暂停/恢复、优先级、取消、重试(REQ-TASK-001..005,US-04) -->
<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { NButton, NPagination, NSelect, NTable, NTag } from 'naive-ui'

const pageSize = ref(15)
const page = ref(1)
import { api } from '../api'

const data = ref({ paused: false, tasks: [] })
let timer = null

const statusType = { 完成: 'success', 排队: 'default', 进行: 'info', 失败: 'error', 中断: 'warning' }

async function load() {
  data.value = await api('/api/tasks')
  // 翻页收敛:数据刷新后页码不越界
  const maxPage = Math.max(1, Math.ceil(data.value.tasks.length / pageSize.value))
  if (page.value > maxPage) page.value = maxPage
}

// 限高分页:进行/排队优先已在服务端排序,这里只做客户端分页
const paged = computed(() => data.value.tasks.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))

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
    <header class="bar">
      <h1>分析管理</h1>
      <div class="bar-tools">
        <n-button size="small" :type="data.paused ? 'primary' : 'default'" secondary @click="togglePause">{{ data.paused ? '恢复队列' : '暂停队列' }}</n-button>
        <n-button size="small" secondary @click="syncNow">立即同步</n-button>
      </div>
    </header>

    <div class="table-wrap">
      <n-table size="small" :bordered="false" :single-line="false">
      <thead>
        <tr><th>仓库</th><th>类型</th><th>状态</th><th>优先级</th><th>原因</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="t in paged" :key="t.id">
          <td>{{ t.full_name }}</td>
          <td>{{ t.kind === 'reanalyze' ? '重分析' : '分析' }}</td>
          <td><n-tag size="small" :type="statusType[t.status]" :bordered="false">{{ t.status }}</n-tag></td>
          <td>
            <n-select
              v-if="t.status === '排队'"
              :value="t.priority"
              size="tiny"
              style="width: 90px"
              :options="[0, 25, 50, 75, 100].map((v) => ({ label: String(v), value: v }))"
              @update:value="(v) => setPriority(t.id, v)"
            />
            <span v-else>{{ t.priority }}</span>
          </td>
          <td class="why">{{ t.fail_reason }}</td>
          <td>
            <n-button v-if="t.status === '排队'" size="tiny" quaternary type="error" @click="cancel(t.id)">取消</n-button>
            <n-button v-if="['失败', '中断'].includes(t.status)" size="tiny" quaternary type="primary" @click="retry(t.id)">重试</n-button>
          </td>
        </tr>
      </tbody>
      </n-table>
    </div>
    <n-pagination
      v-model:page="page"
      :page-size="pageSize"
      :item-count="data.tasks.length"
      :page-slot="7"
      show-size-picker
      :page-sizes="[15, 30, 50]"
      @update:page-size="(s) => (pageSize = s)"
    />
    <p v-if="!data.tasks.length" class="hint">队列为空。在「仓库库」触发分析,或同步 star 自动入库。</p>
  </div>
</template>

<style scoped>
.table-wrap { max-height: calc(100vh - 230px); overflow-y: auto; border: 1px solid var(--sd-border); border-radius: 6px; }
.table-wrap :deep(th) { position: sticky; top: 0; background: var(--sd-surface); z-index: 1; }
.why { color: var(--sd-text-3); font-size: 0.85em; max-width: 260px; overflow-wrap: break-word; }
</style>
