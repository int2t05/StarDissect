<!-- 阅读中心:类别拼图(大号标签块,UX-64)→ 点入类别看报告卡片(已读/收藏/归档);全局搜索(UX-38..42);条目聚合 /api/entries(REQ-READ-006) -->
<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NEmpty, NInput, NSelect, NTag } from 'naive-ui'
import { api, fmtTime } from '../api'

const router = useRouter()
const categories = ref([])
const overview = ref(null)
const homeLoading = ref(true)
const homeError = ref(false)
const cat = ref(null) // null=拼图;0=全部;-1=未分类;>0=领域类别 id(REQ-CLS-006)
const entries = ref([])
const filter = ref('all')
const searchOpen = ref(false)
const q = ref('')
const hits = ref([])
const searchEmpty = ref(false)
const searchActive = ref(-1)
const searchInput = ref(null)
const searchPop = ref(null)
let debounceTimer = null

const filterOptions = [
  { label: '全部', value: 'all' },
  { label: '未读', value: 'unread' },
  { label: '收藏', value: 'favorited' },
  { label: '已归档', value: 'archived' },
]

// 阅读入口只呈现有可读报告的类别,按报告数排序。
const sortedCats = computed(() =>
  categories.value.filter(c => c.reports > 0)
    .sort((a, b) => b.reports - a.reports || a.name.localeCompare(b.name, 'zh')))

const catName = computed(() =>
  cat.value === 0 ? '全部' : cat.value === -1 ? '未分类'
    : categories.value.find(c => c.id === cat.value)?.name ?? '')

// 检索结果按「报告>章节」两级分组(REQ-SRCH-001)
const groupedHits = () => {
  const map = new Map()
  for (const h of hits.value) {
    const key = `${h.full_name}·v${h.version_no ?? ''}`
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(h)
  }
  return [...map.entries()]
}

async function loadMosaic() {
  [categories.value, overview.value] = await Promise.all([
    api('/api/categories'), api('/api/reading/overview'),
  ])
}

async function loadHome() {
  try {
    await Promise.all([loadMosaic(), loadArchive()])
    homeError.value = false
  } catch {
    homeError.value = true
  } finally {
    homeLoading.value = false
  }
}

// 时间归档(UX-65):拼图下方按月分组;默认仅展开最近一月,点月份头折叠/展开
const archive = ref([])
const collapsed = ref([])
let collapseInit = false

const monthGroups = computed(() => {
  const map = new Map()
  for (const e of archive.value) {
    const m = (e.created_at || '').slice(0, 7)
    if (!map.has(m)) map.set(m, [])
    map.get(m).push(e)
  }
  return [...map.entries()].sort((a, b) => b[0].localeCompare(a[0]))
})

async function loadArchive() {
  archive.value = await api('/api/entries?state=all')
  if (!collapseInit) { // 折叠态只初始化一次,避免每次返回重置用户的展开
    collapseInit = true
    collapsed.value = [...new Set(archive.value.map(e => (e.created_at || '').slice(0, 7)))].slice(1)
  }
}

function toggleMonth(m) {
  collapsed.value = collapsed.value.includes(m)
    ? collapsed.value.filter(x => x !== m)
    : [...collapsed.value, m]
}

async function loadEntries() {
  if (cat.value === null) return
  entries.value = await api(`/api/entries?state=${filter.value}&category=${cat.value}`)
  if (active.value >= entries.value.length) active.value = entries.value.length - 1
}

function enter(id) {
  cat.value = id
}

async function back() {
  cat.value = null
  await loadHome() // 归档/分类可能在类别内变化,回拼图前刷新计数
}

watch([cat, filter], loadEntries) // 筛选服务端执行(REQ-READ-006)

// 卡片键盘 j/k 移动、o/Enter 打开、m/f 切换(REQ-READ-004)
const active = ref(-1)
function onListKey(e) {
  if (e.isComposing || searchOpen.value || cat.value === null) return
  const list = entries.value
  if (e.key === 'j') { active.value = Math.min(active.value + 1, list.length - 1); scrollActiveEntry() }
  else if (e.key === 'k') { active.value = Math.max(active.value - 1, 0); scrollActiveEntry() }
  else if ((e.key === 'o' || e.key === 'Enter') && list[active.value]) location.assign(reportUrl(list[active.value]))
  else if ((e.key === 'm' || e.key === 'f') && list[active.value]) toggleEntryState(list[active.value], e.key === 'm' ? 'read' : 'favorited')
}
function scrollActiveEntry() {
  nextTick(() => document.querySelectorAll('.entries li')[active.value]?.scrollIntoView({ block: 'nearest' }))
}
async function toggleEntryState(entry, field) {
  await api(`/api/reports/${entry.id}/state`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ [field]: !entry[field] }) })
  entry[field] = !entry[field]
}

async function doSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(async () => {
    searchActive.value = -1
    if (!q.value.trim()) { hits.value = []; searchEmpty.value = false; return }
    hits.value = await (await fetch(`/api/search?q=${encodeURIComponent(q.value)}`)).json()
    searchEmpty.value = hits.value.length === 0
  }, 200) // UX-38:输入 debounce 200ms;空结果态延迟出现(UX-42)
}

function onSearchKey(e) {
  if (e.isComposing) return // UX-39:组词回车不触发跳转
  const flat = hits.value
  if (e.key === 'ArrowDown') { e.preventDefault(); searchActive.value = (searchActive.value + 1) % flat.length; scrollActive() }
  else if (e.key === 'ArrowUp') { e.preventDefault(); searchActive.value = (searchActive.value - 1 + flat.length) % flat.length; scrollActive() }
  else if (e.key === 'Enter' && searchActive.value >= 0) goto(flat[searchActive.value])
}

function scrollActive() {
  nextTick(() => document.querySelectorAll('.hit')[searchActive.value]?.scrollIntoView({ block: 'nearest' }))
}

let lastFocus = null
watch(searchOpen, (open) => {
  if (open) {
    lastFocus = document.activeElement
    nextTick(() => searchInput.value?.focus())
  } else {
    lastFocus?.focus()
  }
})

// 焦点陷阱(UX-40):Tab 环绕弹层内,Esc 关闭并还原焦点
function trapFocus(e) {
  if (e.key === 'Escape') {
    searchOpen.value = false
    return
  }
  if (e.key !== 'Tab') return
  const focusables = [...searchPop.value.querySelectorAll('input, button')]
  if (!focusables.length) return
  const first = focusables[0]
  const last = focusables[focusables.length - 1]
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
}

// 报告阅读面在 /reports 静态站(ADR-0009):整页跳转,hash 路由不得拦截
function reportUrl(e) {
  return `/reports/${e.full_name.replace(/\//g, '__')}/${e.id}/`
}

function goto(hit) {
  searchOpen.value = false
  if (hit.kind === 'repo') router.push('/repos')
  else location.assign(reportUrl({ full_name: hit.full_name, id: hit.version_id }))
}

onMounted(() => { loadHome(); loadEntries(); window.addEventListener('keydown', onListKey) })
onUnmounted(() => window.removeEventListener('keydown', onListKey))
</script>

<template>
  <div class="page">
    <header class="bar">
      <h1>阅读中心</h1>
      <div class="bar-tools">
        <n-button size="small" secondary data-search-open @click="searchOpen = !searchOpen">搜索 <kbd>/</kbd></n-button>
      </div>
    </header>

    <div v-if="searchOpen" ref="searchPop" class="search-pop" @keydown="trapFocus">
      <n-input ref="searchInput" v-model:value="q" placeholder="搜索报告、知识点、仓库…" @input="doSearch" @keydown="onSearchKey" />
      <template v-if="hits.length">
        <div v-for="[group, items] in groupedHits()" :key="group" class="group">
          <div class="group-name">{{ group }}</div>
          <button
            v-for="h in items"
            :key="h.kind + (h.version_id ?? h.repo_id) + h.title"
            class="hit"
            :class="{ active: hits[searchActive] === h }"
            @click="goto(h)"
          >
            <span class="kind"><n-tag size="tiny" :bordered="false">{{ { report: '报告', knowledge: '知识点', repo: '仓库' }[h.kind] }}</n-tag></span>
            <span class="title">{{ h.title || h.full_name }}</span>
            <span class="snip" v-html="h.snippet"></span><!-- 服务端已 nh3 转义,仅 <mark> 白名单(UX-41) -->
          </button>
        </div>
      </template>
      <div v-else-if="searchEmpty" class="empty"><n-empty description="无结果" size="small" /></div>
    </div>

    <!-- 类别是主阅读入口;时间列表收进折叠面板,避免重复占满首页。 -->
    <template v-if="cat === null">
      <section class="category-section" aria-labelledby="category-heading">
        <header class="section-head">
          <h2 id="category-heading">按类别浏览</h2>
          <span class="section-hint">选择类别查看报告</span>
        </header>
        <div v-if="homeLoading" class="category-loading" role="status">
          <span v-for="i in 6" :key="i" class="category-skeleton" aria-hidden="true"></span>
          <span class="hint">正在读取报告分类</span>
        </div>
        <div v-else-if="homeError" class="load-error" role="alert">
          <span>阅读数据加载失败，请重试。</span>
          <n-button size="small" secondary @click="loadHome">重试</n-button>
        </div>
        <div v-else class="cloud">
        <button class="tile" @click="enter(0)">
          <span class="name">全部</span>
          <span class="meta">{{ overview?.total.reports ?? 0 }} 篇报告 · {{ overview?.total.unread ?? 0 }} 篇未读</span>
        </button>
        <button v-for="c in sortedCats" :key="c.id" class="tile" @click="enter(c.id)">
          <span class="name">{{ c.name }}</span>
          <span class="meta">{{ c.reports }} 篇报告 · {{ c.unread }} 篇未读</span>
        </button>
        <button v-if="overview?.uncategorized.reports" class="tile" @click="enter(-1)">
          <span class="name">未分类</span>
          <span class="meta">{{ overview.uncategorized.reports }} 篇报告 · {{ overview.uncategorized.unread }} 篇未读</span>
        </button>
        </div>
      </section>
      <n-empty
        v-if="!homeLoading && !homeError && overview && !overview.total.reports"
        description="还没有报告。到「仓库库」触发分析,或先在「系统设置」配置凭据。" class="hint"
      />

      <details v-if="!homeLoading && !homeError && monthGroups.length" class="archive">
        <summary class="archive-summary">
          <span>按时间浏览</span>
          <span class="arch-hint">共 {{ archive.length }} 篇</span>
        </summary>
        <div v-for="[m, items] in monthGroups" :key="m" class="month">
          <button class="month-head" :aria-expanded="!collapsed.includes(m)" @click="toggleMonth(m)">
            <span class="m">{{ m }}</span>
            <span class="c">{{ items.length }} 篇</span>
            <span class="arrow">{{ collapsed.includes(m) ? '▸' : '▾' }}</span>
          </button>
          <ul v-if="!collapsed.includes(m)" class="month-list">
            <li v-for="e in items" :key="e.id">
              <a :href="reportUrl(e)">
                <span class="name">{{ e.full_name }} <span v-if="e.favorited">★</span><span v-if="!e.read" class="dot">●</span></span>
                <span class="meta">{{ fmtTime(e.created_at) }}</span>
              </a>
            </li>
          </ul>
        </div>
      </details>
    </template>

    <!-- 类别内:报告卡片,可切未读/收藏态 -->
    <template v-else>
      <div class="cat-head">
        <n-button size="small" quaternary @click="back">← 全部类别</n-button>
        <b class="cat-title">{{ catName }}</b>
        <n-select v-model:value="filter" :options="filterOptions" size="small" style="width: 100px" />
      </div>
      <ul class="entries">
        <li v-for="(e, i) in entries" :key="e.id" :class="{ active: i === active }">
          <a :href="reportUrl(e)">
            <span class="name">{{ e.full_name }} <span v-if="e.favorited">★</span><span v-if="!e.read" class="dot">●</span></span>
            <span class="meta">
              <n-tag v-if="e.archived" size="tiny" :bordered="false">已归档</n-tag>
              {{ fmtTime(e.created_at) }}
              <a href="#" @click.prevent.stop="toggleEntryState(e, 'archived')">{{ e.archived ? '恢复' : '归档' }}</a>
            </span>
          </a>
        </li>
      </ul>
      <n-empty v-if="!entries.length" description="该类别暂无可看的报告。" class="hint" />
    </template>
  </div>
</template>

<style scoped>
.category-section { display: flex; flex-direction: column; gap: 12px; }
.section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.section-head h2 { margin: 0; font-size: 18px; font-weight: 600; }
.section-hint, .arch-hint { color: var(--sd-text-3); font-size: 13px; }
.cloud { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr)); gap: 12px; align-items: stretch; }
.category-loading { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr)); gap: 12px; }
.category-skeleton { min-height: 82px; border: 1px solid var(--sd-border); border-radius: var(--sd-radius-card); background: var(--sd-surface); }
.category-loading .hint { grid-column: 1 / -1; }
.load-error { display: flex; align-items: center; gap: 12px; color: var(--sd-text-2); }
.tile {
  display: flex; flex-direction: column; align-items: flex-start; gap: 4px;
  min-height: 82px; padding: 14px 16px; border: 1px solid var(--sd-border); border-radius: var(--sd-radius-card);
  background: var(--sd-surface); color: var(--sd-text); cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.tile:hover { background: var(--sd-accent-soft); border-color: var(--sd-accent); }
.tile .name { font-size: 18px; font-weight: 600; letter-spacing: -0.01em; }
.tile .meta { font-size: 13px; color: var(--sd-text-3); }
.archive { margin-top: 8px; border-top: 1px solid var(--sd-border); }
.archive-summary { display: flex; align-items: baseline; gap: 12px; padding: 14px 2px; color: var(--sd-text-2); cursor: pointer; }
.archive-summary:hover { color: var(--sd-accent); }
.archive-summary::marker { color: var(--sd-text-3); }
.month-head {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 12px 4px; border: 0; border-top: 1px solid var(--sd-border);
  background: none; color: var(--sd-text); cursor: pointer; text-align: left;
}
.month-head:hover { color: var(--sd-accent); }
.month-head .m { font-size: 16px; font-weight: 600; letter-spacing: -0.01em; }
.month-head .c { color: var(--sd-text-3); font-size: 13px; }
.month-head .arrow { margin-left: auto; color: var(--sd-text-3); font-size: 12px; }
.month-list { list-style: none; padding: 0; margin: 0; }
.month-list li { border-top: 1px solid var(--sd-border); }
.month-list a {
  display: flex; justify-content: space-between; align-items: center; gap: 16px;
  padding: 10px 4px; color: var(--sd-text); font-size: 0.95em;
}
.month-list a:hover { color: var(--sd-accent); }
.month-list .name { font-weight: 400; }
.month-list .dot { color: var(--sd-accent); font-size: 0.65em; margin-left: 8px; vertical-align: 2px; }
.month-list .meta { color: var(--sd-text-3); font-size: 0.82em; white-space: nowrap; }
.cat-head { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.cat-title { font-size: 18px; letter-spacing: -0.01em; }
.cat-head .n-select { margin-left: auto; }
.entries { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr)); gap: 12px; }
.entries li { border: 1px solid var(--sd-border); border-radius: var(--sd-radius-card); content-visibility: auto; contain-intrinsic-size: auto 84px; } /* UX-15 */
.entries li.active { background: var(--sd-accent-soft); }
.entries a { display: flex; flex-direction: column; gap: 6px; height: 100%; padding: 14px 16px; color: var(--sd-text); box-sizing: border-box; }
.entries a:hover { background: var(--sd-accent-soft); }
.entries .name { font-weight: 500; }
.entries .dot { color: var(--sd-accent); font-size: 0.65em; margin-left: 8px; vertical-align: 2px; }
.entries .meta { color: var(--sd-text-3); font-size: 0.85em; display: flex; align-items: center; gap: 8px; }
.search-pop {
  position: fixed; top: 64px; left: 50%; transform: translateX(-50%);
  width: min(680px, 92vw); background: var(--sd-surface);
  border: 1px solid var(--sd-border); border-radius: 8px; padding: 10px; z-index: 25;
}
.group { margin-top: 6px; }
.group-name { color: var(--sd-text-3); font-size: 0.78em; padding: 8px 8px 2px; }
.hit { display: block; width: 100%; text-align: left; border: 0; border-top: 1px solid var(--sd-border); background: none; padding: 10px; color: var(--sd-text); }
.hit:hover, .hit.active { background: var(--sd-accent-soft); }
.title { display: block; margin: 2px 0; }
.snip { display: block; color: var(--sd-text-2); font-size: 0.85em; }
.snip :deep(mark) { background: var(--sd-accent-soft); color: var(--sd-accent); }
.empty { padding: 12px; }
@media (max-width: 600px) {
  .section-head { align-items: flex-start; flex-direction: column; gap: 2px; }
  .cloud, .category-loading { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .tile { min-height: 76px; padding: 11px 12px; }
  .tile .name { font-size: 15px; line-height: 1.35; }
  .tile .meta { font-size: 12px; line-height: 1.45; }
  .category-skeleton { min-height: 76px; }
  .cat-head { flex-wrap: wrap; }
  .cat-head .n-select { margin-left: auto; }
  .month-list a { align-items: flex-start; flex-direction: column; gap: 2px; }
  .month-list .meta { white-space: normal; }
}
</style>
