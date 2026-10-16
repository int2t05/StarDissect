<!-- 仓库库:列表筛选、领域类别筛选与管理、仓库详情抽屉(分类/锁定/标签/类别/排除/归档/更新检测/重新分析/版本/知识点,US-02/03/08) -->
<script setup>
import { computed, onMounted, ref } from 'vue'
import { NAutoComplete, NButton, NCard, NDrawer, NDrawerContent, NEmpty, NInput, NModal, NPopconfirm, NTag } from 'naive-ui'
import { api, fmtTime } from '../api'

const repos = ref([])
const q = ref('')
const filter = ref('active')
const detail = ref(null)
const showDetail = ref(false)
const categories = ref([])
const cat = ref(0)
const showManage = ref(false)
const manageInput = ref('')
const catInput = ref('')

const filterOptions = [
  { label: '在库', value: 'active' },
  { label: '全部', value: 'all' },
  { label: '已取消收藏', value: 'unstarred' },
  { label: '已归档', value: 'archived' },
]

// 归类输入补全:只提示未归入的已有类别;新名回车即建(REQ-CLS-006)
const catOptions = computed(() => {
  const assigned = new Set((detail.value?.categories || []).map(c => c.name))
  return categories.value.filter(c => !assigned.has(c.name)).map(c => ({ label: c.name, value: c.name }))
})

async function loadCategories() {
  categories.value = await api('/api/categories')
}

async function load() {
  repos.value = await api(`/api/repos?filter=${filter.value}&q=${encodeURIComponent(q.value)}&category=${cat.value}`)
}

function setCat(id) {
  cat.value = cat.value === id ? 0 : id  // 再点已选类别=回到全部
  load()
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

async function addCat() {
  const name = catInput.value.trim()
  if (!name || !detail.value) return
  catInput.value = ''
  await api(`/api/repos/${detail.value.repo.id}/categories`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
  await open(detail.value.repo.id)
  await loadCategories()
  await load()
}

async function delRepoCat(id) {
  await api(`/api/repos/${detail.value.repo.id}/categories/${id}`, { method: 'DELETE' })
  await open(detail.value.repo.id)
  await loadCategories()
  await load()
}

async function createCat() {
  const name = manageInput.value.trim()
  if (!name) return
  manageInput.value = ''
  await api('/api/categories', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
  await loadCategories()
}

async function renameCat(c) {
  const name = c.name.trim()
  if (!name) return
  await api(`/api/categories/${c.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
  await loadCategories()
  await load()
}

async function delCat(c) {
  await api(`/api/categories/${c.id}`, { method: 'DELETE' })
  await loadCategories()
  await load()
  if (detail.value) await open(detail.value.repo.id)
}

async function toggleExclude() {
  await api(`/api/repos/${detail.value.repo.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ excluded: !detail.value.repo.excluded }) })
  await open(detail.value.repo.id)
  await load()
}

async function toggleArchive() {
  // 仓库归档/恢复:归档后默认隐藏且拒绝新分析,可随时恢复
  await api(`/api/repos/${detail.value.repo.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ archived: !detail.value.repo.archived }) })
  await open(detail.value.repo.id)
  await load()
}

async function checkUpdates() {
  // 手动检查更新:返回报告锚点落后远端 HEAD 的 commits 数(仅提示,不自动入队)
  await api(`/api/repos/${detail.value.repo.id}/updates/check`, { method: 'POST' })
  await open(detail.value.repo.id)
}

async function toggleVersionArchive(v) {
  // 报告级归档/恢复,独立于仓库归档
  await api(`/api/reports/${v.id}/state`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ archived: !v.archived }) })
  await open(detail.value.repo.id)
}

async function delVersion(v) {
  // 硬删除(仅限已归档版本):连带章节/知识点/检索索引,不可恢复
  await api(`/api/reports/${v.id}`, { method: 'DELETE' })
  await open(detail.value.repo.id)
}

async function analyze() {
  await api(`/api/repos/${detail.value.repo.id}/analyze`, { method: 'POST' })
  await open(detail.value.repo.id)
}

onMounted(() => { load(); loadCategories() })
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

    <div v-if="categories.length" class="catbar">
      <n-tag size="small" checkable :checked="cat === 0" @update:checked="setCat(0)">全部</n-tag>
      <n-tag v-for="c in categories" :key="c.id" size="small" checkable :checked="cat === c.id" @update:checked="setCat(c.id)">
        {{ c.name }} · {{ c.repos }}
      </n-tag>
      <n-button size="tiny" quaternary @click="showManage = true">管理</n-button>
    </div>

    <div class="grid">
      <n-card v-for="r in repos" :key="r.id" size="small" hoverable class="card" @click="open(r.id)">
        <div class="card-head">
          <b>{{ r.full_name }}</b>
          <span class="chips">
            <n-tag v-if="r.type" size="tiny" :bordered="false">{{ r.type }} · {{ r.confidence }}</n-tag>
            <n-tag v-if="r.locked" size="tiny" type="warning" :bordered="false">已锁定</n-tag>
            <n-tag v-if="r.excluded" size="tiny" :bordered="false">已排除</n-tag>
            <n-tag v-if="r.behind_count > 0" size="tiny" type="error" :bordered="false">落后 {{ r.behind_count }} commits</n-tag>
          </span>
        </div>
        <p class="desc">{{ r.description }}</p>
        <p v-if="r.categories && r.categories.length" class="chips cats">
          <n-tag v-for="c in r.categories" :key="c.id" size="tiny" type="primary" round :bordered="false">{{ c.name }}</n-tag>
        </p>
      </n-card>
    </div>
    <n-empty v-if="!repos.length" description="库为空。先在「系统设置」配置凭据并同步 star。" class="hint" />

    <n-drawer v-model:show="showDetail" :width="540" placement="right">
      <n-drawer-content v-if="detail" :title="detail.repo.full_name" closable>
        <div class="detail">
          <p class="desc">{{ detail.repo.description }}</p>
          <p v-if="detail.repo.behind_count > 0" class="desc behind">
            落后远端 {{ detail.repo.behind_count }} commits(检查于 {{ fmtTime(detail.repo.behind_checked_at) }})· 建议重新分析
          </p>
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
            <h3>类别</h3>
            <div class="tags">
              <n-tag v-for="c in detail.categories" :key="c.id" size="small" type="primary" :bordered="false" closable @close="delRepoCat(c.id)">{{ c.name }}</n-tag>
              <span v-if="!detail.categories.length" class="desc">尚无类别(大方向,一库可多类)</span>
            </div>
            <n-autocomplete
              v-model:value="catInput" size="small" :options="catOptions" :on-select="v => { catInput = v; addCat() }"
              placeholder="+ 类别,回车添加;输入新名即创建" @keydown.enter="addCat"
            />
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
            <n-button v-if="!detail.repo.archived" size="small" type="primary" secondary @click="analyze">{{ detail.versions.length ? '重新分析' : '开始分析' }}</n-button>
            <n-button size="small" secondary @click="checkUpdates">检查更新</n-button>
            <n-button size="small" quaternary @click="toggleExclude">{{ detail.repo.excluded ? '取消排除' : '排除(不再自动分析)' }}</n-button>
            <n-popconfirm v-if="!detail.repo.archived" @positive-click="toggleArchive">
              <template #trigger>
                <n-button size="small" quaternary type="error">归档</n-button>
              </template>
              归档后仓库默认隐藏并拒绝新分析,可随时恢复。确认归档?
            </n-popconfirm>
            <n-button v-else size="small" quaternary type="primary" @click="toggleArchive">恢复(取消归档)</n-button>
          </div>
          <div v-if="detail.versions.length" class="sec">
            <h3>报告</h3>
            <p v-for="v in detail.versions" :key="v.id" class="ver">
              <RouterLink :to="`/repos/${detail.repo.id}/report/${v.id}`" @click="showDetail = false">第 {{ v.version_no }} 次分析 · {{ fmtTime(v.created_at) }}</RouterLink>
              <n-tag v-if="v.archived" size="tiny" :bordered="false">已归档</n-tag>
              <a :href="`/api/reports/${v.id}/export`">导出</a>
              <a href="#" @click.prevent="toggleVersionArchive(v)">{{ v.archived ? '恢复' : '归档' }}</a>
              <n-popconfirm v-if="v.archived" @positive-click="delVersion(v)">
                <template #trigger>
                  <a href="#" @click.prevent class="danger">删除</a>
                </template>
                删除该报告及其章节/知识点/检索索引?不可恢复。
              </n-popconfirm>
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

    <n-modal v-model:show="showManage" preset="card" title="管理类别" style="width: 420px">
      <p class="desc">大方向归类,独立于七类主类型与标签;删除类别只解除关联,仓库数据不动。</p>
      <div class="mgr-list">
        <div v-for="c in categories" :key="c.id" class="mgr-row">
          <n-input v-model:value="c.name" size="small" @keydown.enter="renameCat(c)" />
          <span class="count">{{ c.repos }} 个仓库</span>
          <n-popconfirm @positive-click="delCat(c)">
            <template #trigger>
              <n-button size="tiny" quaternary type="error">删除</n-button>
            </template>
            删除「{{ c.name }}」并解除 {{ c.repos }} 个仓库的关联?
          </n-popconfirm>
        </div>
      </div>
      <n-input v-model:value="manageInput" size="small" placeholder="+ 新类别,回车创建" @keydown.enter="createCat" />
    </n-modal>
  </div>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
.grid :deep(.n-card) { border-radius: 18px; }
.card { cursor: pointer; }
.card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chips.cats { margin: 8px 0 0; }
.catbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 0 0 16px; }
.mgr-list { display: flex; flex-direction: column; gap: 8px; margin: 12px 0; }
.mgr-row { display: flex; gap: 8px; align-items: center; }
.mgr-row .n-input { flex: 1; }
.count { color: var(--sd-text-3); font-size: 12px; white-space: nowrap; }
.desc { color: var(--sd-text-2); margin: 6px 0 0; font-size: 0.9em; }
.desc.behind { color: var(--sd-error, #d03050); }
.detail { display: flex; flex-direction: column; gap: 16px; }
.sec h3 { font-size: 0.95em; color: var(--sd-text-2); border-top: 1px solid var(--sd-border); padding-top: 14px; }
.tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
h3.sub { padding-top: 10px; margin-top: 2px; border-top: 0; font-size: 0.88em; }
.actions { display: flex; gap: 8px; }
.ver { display: flex; gap: 12px; align-items: center; }
.ver .danger { color: var(--sd-error, #d03050); }
</style>
