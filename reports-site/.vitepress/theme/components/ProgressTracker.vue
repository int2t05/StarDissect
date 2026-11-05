<script setup lang="ts">
// 阅读进度（UX-26..28 / UIUX §11 UX-58）：scrollspy 判章 + 高水位上报（PUT 契约不变）、
// 跨设备恢复、显式重置。移植自 SPA 的 useScrollSpy + useReadingProgress。
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useData } from 'vitepress'

const RETRY_KEY = 'reports-progress-retry'
const HEADER_OFFSET = 4

const frontmatter = useData().frontmatter
const vid = () => frontmatter.value.vid as number | undefined

const activeSeq = ref(-1)
const ignoreScrollOnce = ref(false)
const saved = ref<{ anchor_seq: number; top_percent: number } | null>(null)
const hasSaved = ref(false)

let spyTimer: ReturnType<typeof setTimeout> | null = null
let reportTimer: ReturnType<typeof setTimeout> | null = null
let lastSpyCall = 0
let mounted = false

// —— scrollspy（UX-59，移植 VitePress useActiveAnchor 算法）——
function throttleAndDebounce(fn: () => void): () => void {
  return () => {
    const now = Date.now()
    if (now - lastSpyCall >= 100) {
      lastSpyCall = now
      fn()
    }
    clearTimeout(spyTimer!)
    spyTimer = setTimeout(() => {
      lastSpyCall = Date.now()
      fn()
    }, 100)
  }
}

function getAbsoluteTop(el: HTMLElement): number {
  let top = 0
  let cur: HTMLElement | null = el
  while (cur) {
    if (getComputedStyle(cur).display === 'none') return 0
    top += cur.offsetTop
    cur = cur.offsetParent
  }
  return top
}

function update(): void {
  if (ignoreScrollOnce.value) {
    ignoreScrollOnce.value = false
  } else {
    const anchors = [...document.querySelectorAll<HTMLElement>('.vp-doc [data-seq]')]
    if (!anchors.length) return
    const doc = document.documentElement
    const scrollTop = window.scrollY
    if (scrollTop <= 0) {
      activeSeq.value = -1 // 页顶置空
    } else if (scrollTop >= doc.scrollHeight - doc.clientHeight - 1) {
      activeSeq.value = Number(anchors[anchors.length - 1].dataset.seq) // 页底取最后
    } else {
      let current = -1
      for (const el of anchors) {
        const margin = parseFloat(getComputedStyle(el).scrollMarginTop || '0')
        if (getAbsoluteTop(el) - margin - HEADER_OFFSET <= scrollTop) current = Number(el.dataset.seq)
        else break
      }
      activeSeq.value = current
    }
  }
  if (mounted) queueReport()
}

const onScroll = throttleAndDebounce(update)

// 当前的阅读位置：scrollspy 判定的章节 + 页面滚动百分比
function computeCurrent(): { anchor_seq: number; top: number; bottom: number } {
  const doc = document.documentElement
  const top = Math.round((doc.scrollTop / Math.max(1, doc.scrollHeight - doc.clientHeight)) * 100)
  const bottom = Math.round(((doc.scrollTop + doc.clientHeight) / Math.max(1, doc.scrollHeight)) * 100)
  return { anchor_seq: Math.max(activeSeq.value, 0), top, bottom }
}

// —— 高水位上报（PUT 契约不变；失败本地缓存，下次打开重传）——
function queueReport(): void {
  clearTimeout(reportTimer!)
  reportTimer = setTimeout(report, 800) // 节流上报(UX-28)
}

async function report(): Promise<void> {
  const id = vid()
  if (!id) return
  const { anchor_seq, top, bottom } = computeCurrent()
  const body = JSON.stringify({ anchor_seq, top_percent: top, bottom_percent: bottom })
  try {
    await fetch(`/api/reports/${id}/progress`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body })
    localStorage.removeItem(RETRY_KEY)
  } catch {
    localStorage.setItem(RETRY_KEY, JSON.stringify({ vid: id, body }))
  }
}

async function flushRetry(): Promise<void> {
  const raw = localStorage.getItem(RETRY_KEY)
  if (!raw) return
  const { vid: id, body } = JSON.parse(raw)
  localStorage.removeItem(RETRY_KEY)
  try {
    await fetch(`/api/reports/${id}/progress`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body })
  } catch {
    // 仍失败则留待下次
  }
}

async function getSaved(): Promise<void> {
  const id = vid()
  if (!id) return
  await flushRetry()
  try {
    const r = await fetch(`/api/reports/${id}/progress`)
    if (!r.ok) return
    const data = await r.json()
    saved.value = data
    hasSaved.value = (data.anchor_seq ?? 0) > 0 || (data.top_percent ?? 0) > 5 // 浅阅读(章节 0)也可见
  } catch {
    // 管理面 API 不可达：进度条不出现，阅读不受影响
  }
}

// 恢复:按存储的视口百分比换算绝对滚动位,忠实回跳(比章节锚点精确)
function resume(): void {
  const doc = document.documentElement
  window.scrollTo({ top: (doc.scrollHeight - doc.clientHeight) * ((saved.value?.top_percent ?? 0) / 100), behavior: 'smooth' })
}

async function reset(): Promise<void> {
  const id = vid()
  if (!id) return
  await fetch(`/api/reports/${id}/progress`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ anchor_seq: 0, top_percent: 0, bottom_percent: 0, reset: true }),
  })
  hasSaved.value = false
  window.scrollTo(0, 0)
}

function jump(seq: number): void {
  ignoreScrollOnce.value = true
  document.querySelector(`[data-seq="${seq}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function onKey(e: KeyboardEvent): void {
  if (e.isComposing || !vid()) return
  const maxSeq = document.querySelectorAll('[data-seq]').length - 1
  if (e.key === 'j') jump(Math.min(activeSeq.value + 1, Math.max(maxSeq, 0)))
  else if (e.key === 'k') jump(Math.max(activeSeq.value - 1, 0))
  else if (e.key === '[') window.dispatchEvent(new CustomEvent('sd-font', { detail: -1 }))
  else if (e.key === ']') window.dispatchEvent(new CustomEvent('sd-font', { detail: 1 }))
}

onMounted(() => {
  mounted = true
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('keydown', onKey)
  getSaved()
  update()
})
onUnmounted(() => {
  mounted = false
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('keydown', onKey)
  clearTimeout(spyTimer!)
  clearTimeout(reportTimer!)
})

// SPA 导航换页：进度归属跟着 vid 走
watch(() => vid(), async () => {
  hasSaved.value = false
  saved.value = null
  activeSeq.value = -1
  await getSaved()
})
</script>

<template>
  <span v-if="vid" class="sd-progress">
    <template v-if="hasSaved">
      <span>上次读到 <b>第 {{ (saved?.anchor_seq ?? 0) + 1 }} 章 · {{ Math.round(saved?.top_percent ?? 0) }}%</b></span>
      <button type="button" @click="resume">继续上次 ↪</button>
    </template>
    <button type="button" @click="reset">重置进度</button>
  </span>
</template>

<style scoped>
.sd-progress { display: inline-flex; gap: 10px; align-items: center; font-size: 12px; color: var(--vp-c-text-2); }
.sd-progress button {
  font: inherit; font-size: 12px; cursor: pointer; color: var(--vp-c-text-2);
  background: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider); border-radius: 6px; padding: 2px 10px;
}
.sd-progress button:hover { color: var(--vp-c-brand-1); border-color: var(--vp-c-brand-1); }
</style>
