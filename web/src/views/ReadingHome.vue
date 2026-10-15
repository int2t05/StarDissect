<!-- 阅读中心:类别拼图(大号标签块,UX-64)→ 点入类别看报告卡片(已读/收藏/归档);全局搜索(UX-38..42);条目聚合 /api/entries(REQ-READ-006) -->
<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NEmpty, NInput, NSelect, NTag } from 'naive-ui'
import { api, fmtTime } from '../api'

const router = useRouter()
const categories = ref([])
const overview = ref(null)
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

// 拼图只呈现有内容的类别;按报告数优先排序
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
  await loadMosaic() // 未读/收藏可能在类别内被切换,回拼图前刷新计数
}

watch([cat, filter], loadEntries) // 筛选服务端执行(REQ-READ-006)

// 卡片键盘 j/k 移动、o/Enter 打开、m/f 切换(REQ-READ-004)
const active = ref(-1)
function onListKey(e) {
  if (e.isComposing || searchOpen.value || cat.value === null) return
  const list = entries.value
  if (e.key === 'j') { active.value = Math.min(active.value + 1, list.length - 1); scrollActiveEntry() }
  else if (e.key === 'k') { active.value = Math.max(active.value - 1, 0); scrollActiveEntry() }
  else if ((e.key === 'o' || e.key === 'Enter') && list[active.value]) router.push(`/repos/${list[active.value].repo_id}/report/${list[active.value].id}`)
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

function goto(hit) {
  searchOpen.value = false
  if (hit.kind === 'repo') router.push('/repos')
  else router.push(`/repos/${hit.repo_id}/report/${hit.version_id}`)
}

onMounted(() => { loadMosaic(); loadEntries(); window.addEventListener('keydown', onListKey) })
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

    <!-- 类别拼图(UX-64):大号标签块,一类别一入口 -->
    <template v-if="cat === null">
      <div class="cloud">
        <button class="tile" @click="enter(0)">
          <span class="name">全部</span>
          <span class="meta">{{ overview?.total.reports ?? 0 }} 篇<span v-if="overview?.total.unread" class="unread"> · {{ overview.total.unread }} 未读</span></span>
        </button>
        <button v-for="c in sortedCats" :key="c.id" class="tile" @click="enter(c.id)">
          <span class="name">{{ c.name }}</span>
          <span class="meta">{{ c.reports }} 篇<span v-if="c.unread" class="unread"> · {{ c.unread }} 未读</span></span>
        </button>
        <button v-if="overview?.uncategorized.reports" class="tile" @click="enter(-1)">
          <span class="name">未分类</span>
          <span class="meta">{{ overview.uncategorized.reports }} 篇<span v-if="overview.uncategorized.unread" class="unread"> · {{ overview.uncategorized.unread }} 未读</span></span>
        </button>
      </div>
      <n-empty
        v-if="overview && !overview.total.reports"
        description="还没有报告。到「仓库库」触发分析,或先在「系统设置」配置凭据。" class="hint"
      />
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
          <RouterLink :to="`/repos/${e.repo_id}/report/${e.id}`">
            <span class="name">{{ e.full_name }} <span v-if="e.favorited">★</span><span v-if="!e.read" class="dot">●</span></span>
            <span class="meta">
              <n-tag size="tiny" :bordered="false">v{{ e.version_no }}</n-tag>
              <n-tag v-if="e.archived" size="tiny" :bordered="false">已归档</n-tag>
              {{ fmtTime(e.created_at) }}
              <a href="#" @click.prevent.stop="toggleEntryState(e, 'archived')">{{ e.archived ? '恢复' : '归档' }}</a>
            </span>
          </RouterLink>
        </li>
      </ul>
      <n-empty v-if="!entries.length" description="该类别暂无可看的报告。" class="hint" />
    </template>
  </div>
</template>

<style scoped>
.cloud { display: flex; flex-wrap: wrap; gap: 14px; align-items: stretch; }
.tile {
  display: flex; flex-direction: column; align-items: flex-start; gap: 4px;
  padding: 16px 28px; border: 1px solid var(--sd-border); border-radius: 9999px;
  background: var(--sd-surface); color: var(--sd-text); cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.tile:hover { background: var(--sd-accent-soft); border-color: var(--sd-accent); }
.tile .name { font-size: 21px; font-weight: 600; letter-spacing: -0.01em; } /* UX-63 display 负字距 */
.tile .meta { font-size: 13px; color: var(--sd-text-3); }
.tile .unread { color: var(--sd-accent); }
.cat-head { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.cat-title { font-size: 18px; letter-spacing: -0.01em; }
.cat-head .n-select { margin-left: auto; }
.entries { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }
.entries li { border: 1px solid var(--sd-border); border-radius: 14px; content-visibility: auto; contain-intrinsic-size: auto 84px; } /* UX-15 */
.entries li.active { background: var(--sd-accent-soft); }
.entries a { display: flex; flex-direction: column; gap: 6px; height: 100%; padding: 14px 16px; color: var(--sd-text); box-sizing: border-box; }
.entries a:hover { background: var(--sd-accent-soft); }
.entries .name { font-weight: 500; }
.entries .dot { color: var(--sd-accent); font-size: 0.65em; margin-left: 8px; vertical-align: 2px; }
.entries .meta { color: var(--sd-text-3); font-size: 0.85em; display: flex; align-items: center; gap: 8px; }
.search-pop {
  position: fixed; top: 64px; left: 50%; transform: translateX(-50%);
  width: min(680px, 92vw); background: var(--sd-elevated);
  border: 1px solid var(--sd-border); border-radius: 18px; padding: 10px; z-index: 25;
  backdrop-filter: saturate(180%) blur(20px);
}
.group { margin-top: 6px; }
.group-name { color: var(--sd-text-3); font-size: 0.78em; padding: 8px 8px 2px; }
.hit { display: block; width: 100%; text-align: left; border: 0; border-top: 1px solid var(--sd-border); background: none; padding: 10px; color: var(--sd-text); }
.hit:hover, .hit.active { background: var(--sd-accent-soft); }
.title { display: block; margin: 2px 0; }
.snip { display: block; color: var(--sd-text-2); font-size: 0.85em; }
.snip :deep(mark) { background: var(--sd-accent-soft); color: var(--sd-accent); }
.empty { padding: 12px; }
</style>
