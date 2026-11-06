<script setup lang="ts">
// 报告页外壳：VitePress 负责排版与目录，本组件收口证据处理和图表交互。
import { computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useData } from 'vitepress'
import DefaultTheme from 'vitepress/theme'
import { createMermaidRenderer } from '../mermaid.js'
import ReportToolbar from './ReportToolbar.vue'

const { Layout } = DefaultTheme
const { page } = useData()
const isHome = computed(() => page.value.relativePath === 'index.md')

let mermaidRenderer: ReturnType<typeof createMermaidRenderer> | undefined
onMounted(() => {
  mermaidRenderer = createMermaidRenderer({ onZoom: openZoom })
  mermaidRenderer.observeAppearance()
  decorate()
})
onUnmounted(() => mermaidRenderer?.dispose())

// VitePress 的 SPA 导航会换掉正文内容：每次页面切换后重新加工
watch(() => page.value.relativePath, () => nextTick(decorate))

function decorate(): void {
  decorateEvidence()
  void mermaidRenderer?.render()
}

// 证据折叠:全报告所有证据收进唯一的置底折叠块「证据 ×n」,
// 正文 100% 纯叙述;兼容三代形态(div 展开 / details 单条 / details 合并)
function decorateEvidence(): void {
  const doc = document.querySelector('.vp-doc')
  if (!doc) return
  const blocks = [...doc.querySelectorAll<HTMLElement>('.ev')].filter(
    el => !el.classList.contains('ev-merged') && !el.parentElement?.closest('.ev'),
  )
  if (!blocks.length) return
  const sep = String.fromCharCode(31)

  const det = document.createElement('details')
  det.className = 'ev ev-merged'
  const refs = blocks.flatMap(el =>
    el.dataset.refs ? el.dataset.refs.split(sep) : el.dataset.ref ? [el.dataset.ref] : [],
  )
  if (refs.length) det.dataset.refs = refs.join(sep)
  const summary = document.createElement('summary')
  summary.append(Object.assign(document.createElement('span'), { className: 'ev-label', textContent: '证据' }))
  summary.append(Object.assign(document.createElement('span'), { className: 'ev-count', textContent: '×' + blocks.length }))
  const body = document.createElement('div')
  body.className = 'ev-body'
  blocks.forEach(el => {
    const item = document.createElement('div')
    item.className = 'ev-item'
    const label = el.querySelector('.ev-label')
    if (label) item.appendChild(label.cloneNode(true))
    if (el.tagName === 'DETAILS') {
      const b = el.querySelector('.ev-body')
      if (b) [...b.childNodes].forEach(n => item.appendChild(n))
    } else {
      ;[...el.childNodes].forEach(n => {
        if (n !== label) item.appendChild(n)
      })
    }
    body.appendChild(item)
  })
  det.append(summary, body)
  injectSourceLinks(det)
  doc.append(det) // 证据统一放文章最后面(用户定稿)
  blocks.forEach(el => el.remove())
}

// 源码条目注入锚定 commit 的 GitHub 链接(REQ-READ-005;折叠路径共用)
function injectSourceLinks(det: HTMLElement): void {
  const fm = useData().frontmatter.value
  const refs = det.dataset.refs ? det.dataset.refs.split(String.fromCharCode(31)) : []
  if (!refs.length || !fm.repo || !fm.commit || det.querySelector('.ev-links')) return
  const row = document.createElement('p')
  row.className = 'ev-links'
  refs.forEach(ref => {
    const [path, lines] = ref.split(':')
    const a = document.createElement('a')
    a.href =
      `https://github.com/${fm.repo}/blob/${fm.commit}/${path}` +
      (lines ? `#L${lines.split('-')[0]}` : '')
    a.target = '_blank'
    a.rel = 'noopener'
    a.textContent = '↗ ' + path.split('/').pop() + (lines ? ':' + lines.split('-')[0] : '')
    row.appendChild(a)
  })
  det.querySelector('.ev-body')!.appendChild(row)
}

// 放大层(UX-48):滚轮缩放、拖拽平移、Esc/点背景退出、焦点圈闭
function openZoom(svg: SVGElement, title: string, origin?: HTMLElement): void {
  if (!svg || document.getElementById('sd-zoom')) return
  const ov = document.createElement('div')
  ov.id = 'sd-zoom'
  ov.tabIndex = -1
  ov.setAttribute('role', 'dialog')
  ov.setAttribute('aria-modal', 'true')
  ov.setAttribute('aria-label', title)
  const head = document.createElement('div')
  head.className = 'zoom-head'
  const titleEl = document.createElement('span')
  titleEl.textContent = title
  const closeButton = document.createElement('button')
  closeButton.className = 'zoom-close'
  closeButton.type = 'button'
  closeButton.textContent = '关闭 (Esc)'
  head.append(titleEl, closeButton)
  const stage = document.createElement('div')
  stage.className = 'zoom-stage'
  const canvas = document.createElement('div')
  canvas.className = 'zoom-canvas'
  stage.appendChild(canvas)
  const hint = document.createElement('div')
  hint.className = 'zoom-hint'
  hint.textContent = '滚轮缩放 · 拖拽平移 · Esc 关闭'
  ov.append(head, stage, hint)
  canvas.appendChild(svg.cloneNode(true))
  document.body.appendChild(ov)
  closeButton.focus()
  let scale = 1, tx = 0, ty = 0
  const applyT = () => { canvas.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})` }
  const onWheel = (e: WheelEvent) => {
    e.preventDefault()
    scale = Math.min(6, Math.max(0.4, scale * (e.deltaY < 0 ? 1.15 : 0.87)))
    applyT()
  }
  // 拖拽状态机:pointer capture 会让松开后的合成 click 目标落到覆盖层,
  // 因此「点空白关闭」在 pointerup 时按按下位置+是否真拖动判定,而非 click 事件
  let drag: { x: number; y: number; moved: boolean } | null = null
  let downOnBackdrop = false
  const onDown = (e: PointerEvent) => {
    if ((e.target as HTMLElement).closest('.zoom-head, button')) return
    downOnBackdrop = e.target === stage
    drag = { x: e.clientX - tx, y: e.clientY - ty, moved: false }
    ov.setPointerCapture(e.pointerId)
  }
  const onMove = (e: PointerEvent) => {
    if (!drag) return
    const nx = e.clientX - drag.x
    const ny = e.clientY - drag.y
    if (Math.abs(nx - tx) > 3 || Math.abs(ny - ty) > 3) drag.moved = true
    tx = nx
    ty = ny
    applyT()
  }
  const onUp = () => {
    const backdropTap = downOnBackdrop && drag && !drag.moved
    drag = null
    if (backdropTap) close() // 点空白关闭;拖拽后松开不关闭
  }
  let closed = false
  const close = () => {
    if (closed) return
    closed = true
    ov.removeEventListener('wheel', onWheel)
    ov.removeEventListener('pointerdown', onDown)
    ov.removeEventListener('pointermove', onMove)
    ov.removeEventListener('pointerup', onUp)
    ov.removeEventListener('pointercancel', onUp)
    ov.removeEventListener('keydown', onKey)
    window.removeEventListener('keydown', onKey, true)
    ov.remove()
    origin?.focus()
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') { e.preventDefault(); close() }
    else if (e.key === 'Tab') { e.preventDefault(); (ov.querySelector('.zoom-close') as HTMLElement).focus() } // 焦点圈闭
  }
  ov.addEventListener('wheel', onWheel, { passive: false })
  // 拖拽仅从图区起始:控制区(pointerdown 落在按钮/标题栏)不抢指针捕获,
  // 否则后续 click 的 target 被重定向到覆盖层,关闭按钮永远点不中
  ov.addEventListener('pointerdown', (e) => {
    if ((e.target as HTMLElement).closest('.zoom-head, button')) return
    onDown(e)
  })
  ov.addEventListener('pointermove', onMove)
  ov.addEventListener('pointerup', onUp)
  ov.addEventListener('pointercancel', onUp)
  closeButton.addEventListener('click', close)
  ov.addEventListener('keydown', onKey)
  window.addEventListener('keydown', onKey, true)
}
</script>

<template>
  <div :class="{ 'archive-home': isHome }">
    <Layout>
      <template #doc-top>
        <ReportToolbar />
      </template>
    </Layout>
  </div>
</template>
