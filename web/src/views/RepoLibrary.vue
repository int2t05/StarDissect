<!-- 仓库库:列表筛选、仓库详情抽屉(分类/锁定/标签/排除/重新分析/版本/知识点,US-02/03/08) -->
<script setup>
import { onMounted, ref } from 'vue'
import { NButton, NCard, NDrawer, NDrawerContent, NEmpty, NInput, NTag } from 'naive-ui'
import { api, fmtTime } from '../api'

const repos = ref([])
const q = ref('')
const filter = ref('active')
const detail = ref(null)
const showDetail = ref(false)

const filterOptions = [
  { label: '在库', value: 'active' },
  { label: '全部', value: 'all' },
  { label: '已取消收藏', value: 'unstarred' },
]

async function load() {
  repos.value = await api(`/api/repos?filter=${filter.value}&q=${encodeURIComponent(q.value)}`)
}

async function open(id) {
  detail.value = await api(`/api/repos/${id}`)
  showDetail.value = true
}

async function toggleLock() {
  const c = detail.value.classification
  await api(`/api/repos/${detail.value.repo.id}/lock`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ locked: !c.locked }) })
  await open(detail.value.repo.id)
}

async function addTag(e) {
  const name = e.target.value.trim()
  e.target.value = ''
  if (!name) return
  await api(`/api/repos/${detail.value.repo.id}/tags`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
  await open(detail.value.repo.id)
  await load()
}

async function delTag(name) {
  await api(`/api/repos/${detail.value.repo.id}/tags/${encodeURIComponent(name)}`, { method: 'DELETE' })
  await open(detail.value.repo.id)
}

async function toggleExclude() {
  await api(`/api/repos/${detail.value.repo.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ excluded: !detail.value.repo.excluded }) })
  await open(detail.value.repo.id)
  await load()
}

async function analyze() {
  await api(`/api/repos/${detail.value.repo.id}/analyze`, { method: 'POST' })
  await open(detail.value.repo.id)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="bar">
      <h1>仓库库</h1>
      <div class="bar-tools">
        <n-select v-model:value="filter" :options="filterOptions" size="small" style="width: 130px" @update:value="load" />
        <n-input v-model:value="q" size="small" placeholder="名称/描述/标签" style="width: 200px" @keydown.enter="load" />
        <n-button size="small" secondary @click="load">筛选</n-button>
      </div>
    </header>

    <div class="grid">
      <n-card v-for="r in repos" :key="r.id" size="small" hoverable class="card" @click="open(r.id)">
        <div class="card-head">
          <b>{{ r.full_name }}</b>
          <span class="chips">
            <n-tag v-if="r.type" size="tiny" :bordered="false">{{ r.type }} · {{ r.confidence }}</n-tag>
            <n-tag v-if="r.locked" size="tiny" type="warning" :bordered="false">已锁定</n-tag>
            <n-tag v-if="r.excluded" size="tiny" :bordered="false">已排除</n-tag>
          </span>
        </div>
        <p class="desc">{{ r.description }}</p>
      </n-card>
    </div>
    <n-empty v-if="!repos.length" description="库为空。先在「系统设置」配置凭据并同步 star。" class="hint" />

    <n-drawer v-model:show="showDetail" :width="540" placement="right">
      <n-drawer-content v-if="detail" :title="detail.repo.full_name" closable>
        <div class="detail">
          <p class="desc">{{ detail.repo.description }}</p>
          <div v-if="detail.classification" class="cls">
            <n-tag size="small" :bordered="false">{{ detail.classification.type }} · 置信 {{ detail.classification.confidence }}</n-tag>
            <n-button size="tiny" quaternary @click="toggleLock">{{ detail.classification.locked ? '解锁分类' : '锁定分类' }}</n-button>
            <p class="desc">{{ detail.classification.reason }}</p>
          </div>
          <p v-else class="hint">尚未分类</p>
          <div v-if="detail.history.length" class="sec">
            <h3>修正记录</h3>
            <p v-for="h in detail.history" :key="h.created_at" class="desc">{{ h.old_type }} → {{ h.new_type }}:{{ h.reason }}</p>
          </div>
          <div class="sec">
            <h3>标签</h3>
            <div class="tags">
              <n-tag v-for="t in detail.auto_tags" :key="'a' + t" size="small" type="info" :bordered="false">{{ t }}</n-tag>
              <span v-if="!detail.auto_tags.length" class="desc">尚无自动标签(分析时由 AI 生成)</span>
            </div>
            <h3 class="sub">人工标签</h3>
            <div class="tags">
              <n-tag v-for="t in detail.tags" :key="t" size="small" closable @close="delTag(t)">{{ t }}</n-tag>
            </div>
            <n-input size="small" placeholder="+ 标签,回车添加" @keydown.enter="addTag" />
          </div>
          <div class="actions">
            <n-button size="small" type="primary" secondary @click="analyze">{{ detail.versions.length ? '重新分析' : '开始分析' }}</n-button>
            <n-button size="small" quaternary @click="toggleExclude">{{ detail.repo.excluded ? '取消排除' : '排除(不再自动分析)' }}</n-button>
          </div>
          <div v-if="detail.versions.length" class="sec">
            <h3>报告版本</h3>
            <p v-for="v in detail.versions" :key="v.id" class="ver">
              <RouterLink :to="`/repos/${detail.repo.id}/report/${v.id}`" @click="showDetail = false">v{{ v.version_no }} · {{ fmtTime(v.created_at) }}</RouterLink>
              <a :href="`/api/reports/${v.id}/export`">导出</a>
            </p>
          </div>
          <div v-if="detail.knowledge_points.length" class="sec">
            <h3>知识点</h3>
            <p v-for="k in detail.knowledge_points" :key="k.id" class="desc">
              {{ k.statement }} <n-tag v-if="k.human_edited" size="tiny" type="info" :bordered="false">人工修订</n-tag>
            </p>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.card { cursor: pointer; }
.card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.desc { color: var(--sd-text-2); margin: 6px 0 0; font-size: 0.9em; }
.detail { display: flex; flex-direction: column; gap: 16px; }
.sec h3 { font-size: 0.95em; color: var(--sd-text-2); border-top: 1px solid var(--sd-border); padding-top: 14px; }
.tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
h3.sub { padding-top: 10px; margin-top: 2px; border-top: 0; font-size: 0.88em; }
.actions { display: flex; gap: 8px; }
.ver { display: flex; gap: 12px; }
</style>
