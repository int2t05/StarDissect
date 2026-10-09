<!-- 阅读中心:报告条目列表 + 全局搜索(UX-38..42);条目聚合 /api/entries(REQ-READ-006) -->
<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NEmpty, NInput, NSelect, NTag } from 'naive-ui'
import { api, fmtTime } from '../api'

const router = useRouter()
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
]

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

async function load() {
  entries.value = await api(`/api/entries?state=${filter.value}`) // 聚合端点,消除逐仓库 N+1
  if (active.value >= entries.value.length) active.value = entries.value.length - 1
}

watch(filter, load) // 筛选服务端执行(REQ-READ-006)

// 列表键盘 j/k 移动、o/Enter 打开、m/f 切换(REQ-READ-004)
const active = ref(-1)
function onListKey(e) {
  if (e.isComposing || searchOpen.value) return
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

onMounted(() => { load(); window.addEventListener('keydown', onListKey) })
onUnmounted(() => window.removeEventListener('keydown', onListKey))
</script>

<template>
  <div class="page">
    <header class="bar">
      <h1>阅读中心</h1>
      <div class="bar-tools">
        <n-select v-model:value="filter" :options="filterOptions" size="small" style="width: 110px" />
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

    <ul class="entries">
      <li v-for="(e, i) in entries" :key="e.id" :class="{ active: i === active }">
        <RouterLink :to="`/repos/${e.repo_id}/report/${e.id}`">
          <span class="name">{{ e.full_name }} <span v-if="e.favorited">★</span><span v-if="!e.read" class="dot">●</span></span>
          <span class="meta"><n-tag size="tiny" :bordered="false">v{{ e.version_no }}</n-tag> {{ fmtTime(e.created_at) }}</span>
        </RouterLink>
      </li>
    </ul>
    <n-empty v-if="!entries.length" description="还没有报告。到「仓库库」触发分析,或先在「系统设置」配置凭据。" class="hint" />
  </div>
</template>

<style scoped>
.entries { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; }
.entries li { border-bottom: 1px solid var(--sd-border); content-visibility: auto; contain-intrinsic-size: auto 64px; } /* UX-15 */
.entries li.active { background: var(--sd-accent-soft); }
.entries a { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 14px 12px; color: var(--sd-text); border-radius: 6px; }
.entries a:hover { background: var(--sd-accent-soft); }
.entries .dot { color: var(--sd-accent); font-size: 0.65em; margin-left: 8px; vertical-align: 2px; }
.meta { color: var(--sd-text-3); font-size: 0.85em; display: flex; align-items: center; gap: 8px; }
.search-pop {
  position: fixed; top: 68px; left: 50%; transform: translateX(-50%);
  width: min(680px, 92vw); background: var(--sd-elevated);
  border: 1px solid var(--sd-border-strong); border-radius: 8px; padding: 10px; z-index: 25;
  box-shadow: 0 12px 40px #0006;
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
