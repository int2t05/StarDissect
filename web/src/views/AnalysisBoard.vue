<!-- 分析管理:队列状态、暂停/恢复、优先级、取消、重试(REQ-TASK-001..005,US-04) -->
<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { NButton, NPagination, NSelect, NTable, NTag } from 'naive-ui'
import { api } from '../api'

const pageSize = ref(15)
const page = ref(1)
const data = ref({ paused: false, tasks: [] })
const loading = ref(true)
const loadError = ref(false)
let timer = null

const statusType = { 完成: 'success', 排队: 'default', 进行: 'info', 失败: 'error', 中断: 'warning' }

async function load() {
  try {
    data.value = await api('/api/tasks')
    loadError.value = false
    // 翻页收敛:数据刷新后页码不越界
    const maxPage = Math.max(1, Math.ceil(data.value.tasks.length / pageSize.value))
    if (page.value > maxPage) page.value = maxPage
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

// 限高分页:进行/排队优先已在服务端排序,这里只做客户端分页
const paged = computed(() => data.value.tasks.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))

async function togglePause() {
  await api('/api/queue', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paused: !data.value.paused }) })
  await load()
}

// 报告阅读站在 /reports 静态站(ADR-0009):手动重建,异步执行,进度看 data/logs/site-build.log
const rebuilding = ref(false)
async function rebuildSite() {
  rebuilding.value = true
  try {
    await api('/api/site/rebuild', { method: 'POST' })
  } finally {
    setTimeout(() => { rebuilding.value = false }, 3000) // 后台构建,按钮只做防连点
  }
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
        <n-button size="small" secondary :loading="rebuilding" @click="rebuildSite">重建报告站</n-button>
      </div>
    </header>

    <div v-if="loading" class="queue-loading" role="status">
      <span v-for="i in 4" :key="i" class="queue-skeleton" aria-hidden="true"></span>
      <span class="loading-label">正在加载分析队列</span>
    </div>
    <div v-else-if="loadError" class="load-error" role="alert">
      <span>分析队列加载失败，请重试。</span>
      <n-button size="small" secondary @click="load">重试</n-button>
    </div>
    <div v-else-if="data.tasks.length" class="table-wrap">
      <n-table size="small" :bordered="false" :single-line="false">
      <thead>
        <tr><th>仓库</th><th>类型</th><th>状态</th><th>优先级</th><th>原因</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="t in paged" :key="t.id">
          <td data-label="仓库">{{ t.full_name }}</td>
          <td data-label="类型">{{ t.kind === 'reanalyze' ? '重分析' : '分析' }}</td>
          <td data-label="状态"><n-tag size="small" :type="statusType[t.status]" :bordered="false">{{ t.status }}</n-tag></td>
          <td data-label="优先级">
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
          <td data-label="原因" class="why">{{ t.fail_reason }}</td>
          <td data-label="操作">
            <n-button v-if="t.status === '排队'" size="tiny" quaternary type="error" @click="cancel(t.id)">取消</n-button>
            <n-button v-if="['失败', '中断'].includes(t.status)" size="tiny" quaternary type="primary" @click="retry(t.id)">重试</n-button>
          </td>
        </tr>
      </tbody>
      </n-table>
    </div>
    <div v-if="!loading && !loadError && data.tasks.length" class="pager-wrap">
      <n-pagination
        v-model:page="page"
        :page-size="pageSize"
        :item-count="data.tasks.length"
        :page-slot="7"
        show-size-picker
        :page-sizes="[15, 30, 50]"
        @update:page-size="(s) => (pageSize = s)"
      />
    </div>
    <p v-if="!loading && !loadError && !data.tasks.length" class="queue-empty hint">队列为空。在「仓库库」触发分析，或同步 star 自动入库。</p>
  </div>
</template>

<style scoped>
.table-wrap { max-width: 100%; max-height: calc(100vh - 230px); overflow: auto; border: 1px solid var(--sd-border); border-radius: 6px; }
.queue-loading { display: flex; flex-direction: column; gap: 10px; }
.queue-skeleton { height: 42px; border: 1px solid var(--sd-border); border-radius: 6px; background: var(--sd-surface); }
.loading-label { color: var(--sd-text-3); font-size: 13px; }
.load-error { display: flex; align-items: center; gap: 12px; color: var(--sd-text-2); }
.table-wrap :deep(table) { min-width: 860px; }
.table-wrap :deep(th) { position: sticky; top: 0; background: var(--sd-surface); z-index: 1; }
.why { color: var(--sd-text-3); font-size: 0.85em; max-width: 260px; overflow-wrap: break-word; }
.pager-wrap { max-width: 100%; overflow-x: auto; align-self: flex-end; }
@media (max-width: 767px) {
  .table-wrap { max-height: none; overflow: visible; border: 0; }
  .table-wrap :deep(table) { min-width: 0; border-collapse: separate; border-spacing: 0; }
  .table-wrap :deep(thead) { display: none; }
  .table-wrap :deep(tbody) { display: flex; flex-direction: column; gap: 10px; }
  .table-wrap :deep(tr) {
    display: block;
    padding: 4px 12px;
    border: 1px solid var(--sd-border);
    border-radius: var(--sd-radius-card);
    background: var(--sd-surface);
  }
  .table-wrap :deep(td) {
    display: grid;
    grid-template-columns: 76px minmax(0, 1fr);
    align-items: start;
    gap: 10px;
    padding: 7px 0 !important;
    border: 0 !important;
    text-align: left;
    overflow-wrap: anywhere;
  }
  .table-wrap :deep(td::before) { content: attr(data-label); color: var(--sd-text-3); font-size: 0.82em; }
  .table-wrap :deep(td:empty) { display: none; }
  .why { max-width: none; }
  .queue-loading { gap: 8px; }
  .queue-skeleton { height: 36px; }
  .queue-empty { margin: 8px 0; }
  .pager-wrap { align-self: stretch; overflow: visible; }
  .pager-wrap :deep(.n-pagination) { justify-content: center; flex-wrap: wrap; gap: 6px; }
}
</style>
