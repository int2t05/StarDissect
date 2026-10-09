<!-- 报告阅读页:服务端渲染 HTML 直出(REQ-READ-001)、目录定位(REQ-READ-002)、
     进度高水位上报(REQ-READ-003)、格式调节(REQ-READ-001/UX-30..33)、证据块样式(UX-43..47) -->
<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useReaderSettings } from '../composables/useReaderSettings'

const route = useRoute()
const { settings } = useReaderSettings()
const report = ref(null)
const sections = ref([])
const state = ref({ read: false, favorited: false })
const violations = ref(-1) // -1=未显示;排版校验违规数(REQ-RPT-003)
let scrollTimer = null
let io = null
const activeSeq = ref(-1)

const toc = computed(() => sections.value)

onMounted(async () => {
  report.value = await (await fetch(`/api/reports/${route.params.vid}`)).json()
  sections.value = JSON.parse(report.value.sections || '[]')
  report.value.repo_name = (await (await fetch(`/api/repos/${report.value.repo_id}`)).json()).repo.full_name
  const meta = JSON.parse(report.value.meta || '{}')
  violations.value = meta.typography_check?.status === 'checked' ? meta.typography_check.violations.length : -1
  const saved = await (await fetch(`/api/reports/${route.params.vid}/progress`)).json()
  await nextTick()
  const target = document.querySelector(`[data-seq="${saved.anchor_seq ?? 0}"]`)
  if (target) target.scrollIntoView({ block: 'start' })
  renderMermaid()
  // scrollspy:最后一个越过视口顶的标题(UX-59 语义);滚动在 window(审查 T-04)
  io = new IntersectionObserver(
    (ents) => {
      for (const e of ents) if (e.isIntersecting) activeSeq.value = Number(e.target.dataset.seq)
    },
    { rootMargin: '0px 0px -90% 0px' },
  )
  document.querySelectorAll('.article [data-seq]').forEach((el) => io.observe(el))
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('keydown', onKey)
})

// 源码事实点击:跳转锚定 commit 的 GitHub blob(REQ-READ-005)
function openSource(ev) {
  const ref = ev.currentTarget.dataset.ref // path:line 或 path:start-end
  if (!ref || !ref.includes(':')) return
  const [path, lines] = ref.split(':')
  const anchor = lines ? `#L${lines.split('-')[0]}` : ''
  window.open(`https://github.com/${report.value.repo_name}/blob/${report.value.commit_anchor}/${path}${anchor}`, '_blank', 'noopener')
}

// mermaid 渲染 + 文字后备(RPT-005/UX-48):渲染失败展开源码,不空块
async function renderMermaid() {
  const blocks = [...document.querySelectorAll('.article .mermaid')]
  if (!blocks.length) return
  for (const b of blocks) {
    const src = b.textContent
    const fig = document.createElement('figure')
    const holder = document.createElement('div')
    const fallback = document.createElement('details')
    fallback.innerHTML = `<summary>图表源码</summary><pre>${src.replace(/</g, '&lt;')}</pre>`
    b.replaceWith(fig)
    fig.append(holder, fallback)
    try {
      const mermaid = (await import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs')).default
      mermaid.initialize({ startOnLoad: false, theme: 'dark' })
      const { svg } = await mermaid.render(`m${Math.random().toString(36).slice(2)}`, src)
      holder.innerHTML = svg
    } catch {
      fallback.open = true
    }
  }
}

async function toggleState(field) {
  await fetch(`/api/reports/${route.params.vid}/state`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ [field]: !state.value[field] }),
  })
  state.value[field] = !state.value[field]
}

// 阅读键 m/f(REQ-READ-004/006);j/k 在阅读页按章节移动
function onKey(e) {
  if (e.isComposing) return
  if (e.key === 'm') toggleState('read')
  else if (e.key === 'f') toggleState('favorited')
  else if (e.key === 'j') jump(Math.min(activeSeq.value + 1, sections.value.length - 1))
  else if (e.key === 'k') jump(Math.max(activeSeq.value - 1, 0))
}

onUnmounted(() => {
  io?.disconnect()
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('keydown', onKey)
})

function onScroll() {
  clearTimeout(scrollTimer)
  scrollTimer = setTimeout(async () => {
    const anchors = [...document.querySelectorAll('.article [data-seq]')]
    let seq = 0
    for (const el of anchors) {
      if (el.getBoundingClientRect().top <= 80) seq = Number(el.dataset.seq)
    }
    const doc = document.documentElement
    const top = Math.round((doc.scrollTop / Math.max(1, doc.scrollHeight - doc.clientHeight)) * 100)
    await fetch(`/api/reports/${route.params.vid}/progress`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ anchor_seq: seq, top_percent: top, bottom_percent: top }),
    })
  }, 800) // 节流上报(UX-28)
}

function resetProgress() {
  fetch(`/api/reports/${route.params.vid}/progress`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ anchor_seq: 0, top_percent: 0, bottom_percent: 0, reset: true }),
  }).then(() => window.scrollTo(0, 0))
}

function jump(seq) {
  document.querySelector(`[data-seq="${seq}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<template>
  <div v-if="report" class="reader">
    <header class="bar">
      <div>
        <h1>{{ report.repo_name }} · v{{ report.version_no }}</h1>
        <span class="meta">commit {{ report.commit_anchor.slice(0, 8) }} · {{ report.created_at }}</span>
        <span v-if="violations > 0" class="meta warn">排版提示 {{ violations }} 处</span>
      </div>
      <div class="tools">
        <button @click="toggleState('read')">{{ state.read ? '已读' : '未读' }} <kbd>m</kbd></button>
        <button @click="toggleState('favorited')">{{ state.favorited ? '★' : '☆' }} <kbd>f</kbd></button>
        <select v-model.number="settings.fontSize" @change="0">
          <option v-for="s in [12, 13, 14, 15.5, 17, 19, 21, 22]" :key="s" :value="s">{{ s }}px</option>
        </select>
        <select v-model="settings.width">
          <option value="narrow">窄</option>
          <option value="standard">标准</option>
          <option value="wide">宽</option>
        </select>
        <select v-model="settings.lineHeight">
          <option value="1.6">疏 1.6</option>
          <option value="1.8">1.8</option>
          <option value="2.0">密 2.0</option>
        </select>
        <select v-model="settings.theme">
          <option value="light">浅</option>
          <option value="dark">深</option>
          <option value="auto">跟随系统</option>
        </select>
        <button @click="resetProgress">重置进度</button>
        <a :href="`/api/reports/${route.params.vid}/export`">导出 MD</a>
      </div>
    </header>

    <div class="cols">
      <article class="article" v-html="report.html" @click="(e) => e.target.closest('.ev-source') && openSource({ currentTarget: e.target.closest('.ev-source') })"></article>
      <aside v-if="toc.length" class="toc">
        <button
          v-for="s in toc"
          :key="s.seq"
          :class="{ active: activeSeq === s.seq, sub: s.level === 3 }"
          @click="jump(s.seq)"
        >
          {{ s.title }}
        </button>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: center; max-width: var(--sd-width); margin: 0 auto 16px; }
.bar h1 { font-size: 18px; margin: 0; }
.meta { color: var(--sd-text-3); font-size: 0.85em; font-family: var(--sd-font-mono); }
.meta.warn { color: var(--sd-ev-infer); margin-left: 12px; }
.article :deep(.ev-source) { cursor: pointer; }
kbd { font-size: 10px; color: var(--sd-text-3); }
.tools { display: flex; gap: 8px; flex-wrap: wrap; }
.cols { display: flex; gap: 24px; justify-content: center; }
.article { max-width: var(--sd-width); }
.toc { width: 210px; flex: none; position: sticky; top: 16px; align-self: flex-start; display: flex; flex-direction: column; border-left: 2px solid var(--sd-border); }
.toc button { text-align: left; border: 0; background: none; color: var(--sd-text-2); padding: 4px 10px; font-size: 0.85em; }
.toc button.sub { padding-left: 24px; }
.toc button.active { color: var(--sd-accent); border-left: 2px solid var(--sd-accent); margin-left: -2px; }
@media (max-width: 1023px) { .toc { display: none; } } /* UX-23 平板折叠 */
@media (max-width: 767px) { .cols { display: block; } }
</style>

<style>
/* 服务端渲染正文内证据块(UX-43..47):虚线只属于分析推断 */
.article { overflow-wrap: break-word; }
.article h2, .article h3 { border-top: 1px solid var(--sd-border); padding-top: 20px; margin-top: 32px; }
.article pre { background: #0c0c10; color: var(--sd-text); font-family: var(--sd-font-mono); padding: 12px; border-radius: 4px; overflow-x: auto; }
.article code { font-family: var(--sd-font-mono); }
.article table { border-collapse: collapse; display: block; overflow-x: auto; max-width: 100%; }
.article th, .article td { border: 1px solid var(--sd-border); padding: 4px 10px; }
.article blockquote { border-left: 3px solid var(--sd-accent); margin: 0; padding: 2px 16px; }
.article .ev { border: 1px solid var(--sd-border); border-radius: 6px; padding: 8px 14px; margin: 12px 0; background: var(--sd-surface); }
.article .ev .ev-label { font-size: 0.78em; letter-spacing: 0.08em; color: var(--sd-text-3); display: block; }
.article .ev .ev-ref { font-family: var(--sd-font-mono); font-size: 0.9em; }
.article .ev-source { border-left: 3px solid var(--sd-ev-source); }
.article .ev-author { border-left: 3px solid var(--sd-ev-author); }
.article .ev-infer { border-left: 3px dashed var(--sd-ev-infer); }
.article .ev-external { border-left: 3px solid var(--sd-ev-external); }
.article .ev-unknown { border-left: 3px solid var(--sd-ev-unknown); }
.article .ev a { word-break: break-all; }
.article .ev .ev-date { color: var(--sd-text-3); font-size: 0.8em; margin-left: 8px; }
</style>
