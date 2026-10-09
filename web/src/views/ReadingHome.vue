<!-- 阅读中心:报告条目列表(miniflux 式),含全局搜索入口(UX-38..42)与未读筛选 -->
<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const entries = ref([])
const filter = ref('all')
const searchOpen = ref(false)
const q = ref('')
const hits = ref([])
const searchEmpty = ref(false)
const searchActive = ref(-1)
let debounceTimer = null

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
  const repos = await (await fetch('/api/repos?filter=all')).json()
  const list = []
  for (const r of repos.filter((x) => x.versions > 0)) {
    const versions = await (await fetch(`/api/repos/${r.id}/reports`)).json()
    for (const v of versions) list.push({ ...v, repo: r })
  }
  entries.value = list.sort((a, b) => b.id - a.id)
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

function goto(hit) {
  searchOpen.value = false
  if (hit.kind === 'repo') router.push('/repos')
  else router.push(`/repos/${hit.repo_id}/report/${hit.version_id}`)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="bar">
      <h1>阅读中心</h1>
      <button data-search-open @click="searchOpen = !searchOpen">搜索 <kbd>/</kbd></button>
    </header>

    <div v-if="searchOpen" class="search-pop">
      <input v-model="q" placeholder="搜索报告、知识点、仓库…" @input="doSearch" @keydown="onSearchKey" />
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
            <span class="kind">{{ { report: '报告', knowledge: '知识点', repo: '仓库' }[h.kind] }}</span>
            <span class="title">{{ h.title || h.full_name }}</span>
            <span class="snip" v-html="h.snippet"></span><!-- 服务端已 nh3 转义,仅 <mark> 白名单(UX-41) -->
          </button>
        </div>
      </template>
      <div v-else-if="searchEmpty" class="empty">无结果</div>
    </div>

    <ul class="entries">
      <li v-for="e in entries" :key="e.id">
        <RouterLink :to="`/repos/${e.repo.id}/report/${e.id}`">
          <span class="name">{{ e.repo.full_name }}</span>
          <span class="meta">v{{ e.version_no }} · {{ e.created_at }}</span>
        </RouterLink>
      </li>
    </ul>
    <p v-if="!entries.length" class="hint">还没有报告。到「仓库库」触发分析,或先在「系统设置」配置凭据。</p>
  </div>
</template>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: center; }
.entries { list-style: none; padding: 0; max-width: var(--sd-width); }
.entries li { border-bottom: 1px solid var(--sd-border); content-visibility: auto; contain-intrinsic-size: auto 60px; } /* UX-15 */
.entries a { display: flex; justify-content: space-between; padding: 12px 8px; color: var(--sd-text); }
.entries a:hover { background: var(--sd-accent-soft); }
.meta { color: var(--sd-text-3); font-size: 0.85em; }
.search-pop { position: fixed; top: 60px; left: 50%; transform: translateX(-50%); width: min(640px, 92vw); background: var(--sd-elevated); border: 1px solid var(--sd-border-strong); border-radius: 6px; padding: 8px; z-index: 10; }
.search-pop input { width: 100%; }
.group { margin-top: 4px; }
.group-name { color: var(--sd-text-3); font-size: 0.78em; padding: 6px 8px 2px; }
.hit { display: block; width: 100%; text-align: left; border: 0; border-top: 1px solid var(--sd-border); background: none; padding: 8px; }
.hit:hover, .hit.active { background: var(--sd-accent-soft); }
.kind { color: var(--sd-text-3); font-size: 0.8em; margin-right: 8px; }
.snip { display: block; color: var(--sd-text-2); font-size: 0.85em; }
.snip :deep(mark) { background: var(--sd-accent-soft); color: var(--sd-accent); }
.empty { color: var(--sd-text-3); padding: 12px; }
.hint { color: var(--sd-text-3); }
</style>
