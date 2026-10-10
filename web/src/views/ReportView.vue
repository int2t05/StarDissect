<!-- 报告阅读页:服务端渲染 HTML 直出(REQ-READ-001)、目录定位(REQ-READ-002)、
     进度高水位上报(REQ-READ-003)、格式调节(REQ-READ-001/UX-30..33)、证据块样式(UX-43..47)
     布局:文章居中占主体,目录右浮(UX-61,VitePress 式) -->
<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NSelect } from 'naive-ui'
import { fmtTime } from '../api'
import { useReadingProgress } from '../composables/useReadingProgress'
import { useScrollSpy } from '../composables/useScrollSpy'
import { useReaderSettings } from '../composables/useReaderSettings'

const route = useRoute()
const { settings } = useReaderSettings()
const vid = () => route.params.vid
const report = ref(null)
const sections = ref([])
const state = ref({ read: false, favorited: false })
const violations = ref(-1) // -1=未显示;排版校验违规数(REQ-RPT-003)
const hasSaved = ref(false)
const lastSaved = ref(null)
const activeSeq = ref(-1)

const toc = computed(() => sections.value)

const fontOptions = [12, 13, 14, 15.5, 17, 19, 21, 22].map((v) => ({ label: `${v}px`, value: v }))
const widthOptions = [
  { label: '窄', value: 'narrow' },
  { label: '标准', value: 'standard' },
  { label: '宽', value: 'wide' },
]
const lhOptions = [
  { label: '疏 1.6', value: '1.6' },
  { label: '1.8', value: '1.8' },
  { label: '密 2.0', value: '2.0' },
]
const themeOptions = [
  { label: '浅色', value: 'light' },
  { label: '深色', value: 'dark' },
  { label: '跟随系统', value: 'auto' },
]

const spy = useScrollSpy()

onMounted(async () => {
  report.value = await (await fetch(`/api/reports/${route.params.vid}`)).json()
  sections.value = JSON.parse(report.value.sections || '[]')
  report.value.repo_name = (await (await fetch(`/api/repos/${report.value.repo_id}`)).json()).repo.full_name
  const meta = JSON.parse(report.value.meta || '{}')
  violations.value = meta.typography_check?.status === 'checked' ? meta.typography_check.violations.length : -1
  renderMermaid()
  spy.mount() // scrollspy:UX-59 完整算法(useScrollSpy)
  progress.mount()
  window.addEventListener('keydown', onKey)
  await nextTick()
  const saved = await progress.getSaved() // 进入默认开头;恢复由「继续上次」显式触发
  lastSaved.value = saved
  hasSaved.value = (saved.anchor_seq ?? 0) > 0 || (saved.top_percent ?? 0) > 5  // 浅阅读(章节 0)也可见
  state.value = { read: !!report.value.read, favorited: !!report.value.favorited }  // 持久状态回读
})

// 源码事实点击:跳转锚定 commit 的 GitHub blob(REQ-READ-005)
function openSource(ev) {
  const ref = ev.currentTarget.dataset.ref // path:line 或 path:start-end
  if (!ref || !ref.includes(':')) return
  const [path, lines] = ref.split(':')
  const anchor = lines ? `#L${lines.split('-')[0]}` : ''
  window.open(`https://github.com/${report.value.repo_name}/blob/${report.value.commit_anchor}/${path}${anchor}`, '_blank', 'noopener')
}

// mermaid 渲染 + 图题 + 放大层 + 文字后备(UX-48/RPT-005):渲染失败展开源码,不空块
let figIndex = 0
async function renderMermaid() {
  const blocks = [...document.querySelectorAll('.article .mermaid')]
  if (!blocks.length) return
  const theme = document.documentElement.dataset.theme === 'light' ? 'neutral' : 'dark'
  for (const b of blocks) {
    const src = b.textContent
    const fig = document.createElement('figure')
    const holder = document.createElement('div')
    holder.className = 'zoomable'  // 放大触发/hover 仅作用于图本体,不与源码折叠区重叠
    const cap = document.createElement('figcaption')
    cap.textContent = `图 ${++figIndex} · 点击放大`
    const fallback = document.createElement('details')
    fallback.innerHTML = `<summary>图表源码</summary><pre>${src.replace(/</g, '&lt;')}</pre>`
    b.replaceWith(fig)
    fig.append(holder, cap, fallback)
    const mermaid = (await import('mermaid')).default  // 本地依赖随构建打包(E16:内网自托管不依赖外部 CDN)
    mermaid.initialize({ startOnLoad: false, theme })
    // parse 先行验证:失败不产生 mermaid 的孤儿错误图;修复/后备而非页面报错炸弹
    const tryRender = async (text) => {
      if (!(await mermaid.parse(text, { suppressErrors: true }))) throw new Error('parse failed')
      const { svg } = await mermaid.render(`m${Math.random().toString(36).slice(2)}`, text)
      holder.innerHTML = svg
      holder.addEventListener('click', () => openZoom(holder.querySelector('svg'), cap.textContent))
    }
    // 确定性修复:未加引号的节点标签补双引号(引号内 {} 合法);与服务端 _quote_mermaid_labels 同一规则
    const repaired = src.replace(/([A-Za-z0-9_]+)\[(?!")([^\]\[\n"]+)\]/g, '$1["$2"]')
    try {
      await tryRender(src)
    } catch {
      try {
        if (repaired === src) throw new Error('unrepairable')
        await tryRender(repaired)
        cap.textContent += ' · 已自动修复语法'
      } catch {
        fallback.open = true  // 仍失败才走源码后备
      }
    }
  }
}

// 放大层(UX-48):滚轮缩放、拖拽平移、Esc/点背景退出、焦点圈闭
function openZoom(svg, title) {
  if (!svg || document.getElementById('sd-zoom')) return
  const ov = document.createElement('div')
  ov.id = 'sd-zoom'
  ov.tabIndex = -1
  ov.innerHTML = `
    <div class="zoom-head">${title.replace(/</g, '&lt;')}<button type="button" class="zoom-close">关闭 (Esc)</button></div>
    <div class="zoom-stage"><div class="zoom-canvas"></div></div>
    <div class="zoom-hint">滚轮缩放 · 拖拽平移 · Esc 关闭</div>`
  const canvas = ov.querySelector('.zoom-canvas')
  canvas.appendChild(svg.cloneNode(true))
  document.body.appendChild(ov)
  ov.focus()
  let scale = 1, tx = 0, ty = 0
  const applyT = () => { canvas.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})` }
  const onWheel = (e) => {
    e.preventDefault()
    scale = Math.min(6, Math.max(0.4, scale * (e.deltaY < 0 ? 1.15 : 0.87)))
    applyT()
  }
  // 拖拽状态机:pointer capture 会让松开后的合成 click 目标落到覆盖层,
  // 因此「点空白关闭」在 pointerup 时按按下位置+是否真拖动判定,而非 click 事件
  const stage = ov.querySelector('.zoom-stage')
  let drag = null
  let downOnBackdrop = false
  const onDown = (e) => {
    if (e.target.closest('.zoom-head, button')) return
    downOnBackdrop = e.target === stage
    drag = { x: e.clientX - tx, y: e.clientY - ty, moved: false }
    ov.setPointerCapture(e.pointerId)
  }
  const onMove = (e) => {
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
    if (backdropTap) close()  // 点空白关闭;拖拽后松开不关闭
  }
  let closed = false
  const close = () => {
    if (closed) return
    closed = true
    ov.removeEventListener('wheel', onWheel)
    ov.removeEventListener('pointerdown', onDown)
    ov.removeEventListener('pointermove', onMove)
    ov.removeEventListener('pointerup', onUp)
    ov.removeEventListener('keydown', onKey)
    window.removeEventListener('keydown', onKey, true)
    ov.remove()
    document.querySelector('.article .fig-ok')?.focus?.()
  }
  const onKey = (e) => { if (e.key === 'Escape') { e.preventDefault(); close() } }
  ov.addEventListener('wheel', onWheel, { passive: false })
  // 拖拽仅从图区起始:控制区(pointerdown 落在按钮/标题栏)不抢指针捕获,
  // 否则后续 click 的 target 被重定向到覆盖层,关闭按钮永远点不中
  ov.addEventListener('pointerdown', (e) => {
    if (e.target.closest('.zoom-head, button')) return
    onDown(e)
  })
  ov.addEventListener('pointermove', onMove)
  ov.addEventListener('pointerup', onUp)
  ov.addEventListener('pointercancel', onUp)
  ov.querySelector('.zoom-close').addEventListener('click', close)
  ov.addEventListener('keydown', onKey)
  window.addEventListener('keydown', onKey, true)
}

async function toggleState(field) {
  await fetch(`/api/reports/${route.params.vid}/state`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ [field]: !state.value[field] }),
  })
  state.value[field] = !state.value[field]
}

// 阅读键 m/f(REQ-READ-004/006);j/k 按章节移动;[ ] 字号(UX-30)
function onKey(e) {
  if (e.isComposing) return
  if (e.key === 'm') toggleState('read')
  else if (e.key === 'f') toggleState('favorited')
  else if (e.key === 'j') jump(Math.min(activeSeq.value + 1, sections.value.length - 1))
  else if (e.key === 'k') jump(Math.max(activeSeq.value - 1, 0))
  else if (e.key === '[') settings.fontSize = Math.max(12, settings.fontSize - 1)
  else if (e.key === ']') settings.fontSize = Math.min(22, settings.fontSize + 1)
}

onUnmounted(() => {
  spy.unmount()
  progress.unmount()
  window.removeEventListener('keydown', onKey)
})

// 当前阅读位置:scrollspy 判定的章节 + 页面滚动百分比(与目录高亮同源)
function computeCurrent() {
  const doc = document.documentElement
  const top = Math.round((doc.scrollTop / Math.max(1, doc.scrollHeight - doc.clientHeight)) * 100)
  const bottom = Math.round(((doc.scrollTop + doc.clientHeight) / Math.max(1, doc.scrollHeight)) * 100)
  return { anchor_seq: Math.max(spy.activeSeq.value, 0), top, bottom }
}

const progress = useReadingProgress(vid, computeCurrent)

function jump(seq) {
  document.querySelector(`[data-seq="${seq}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<template>
  <div v-if="report" class="reader">
    <div class="body">
      <aside class="panel">
        <div class="pgroup">
          <div class="ptitle">报告</div>
          <div class="pbig">{{ report.repo_name }}</div>
          <div class="prow">v{{ report.version_no }} · commit {{ report.commit_anchor.slice(0, 8) }}</div>
          <div class="prow">{{ fmtTime(report.created_at) }}</div>
          <div v-if="violations > 0" class="prow warn">排版提示 {{ violations }} 处</div>
        </div>
        <div class="pgroup">
          <div class="ptitle">阅读状态 <kbd>m</kbd><kbd>f</kbd></div>
          <n-button size="tiny" block :type="state.read ? 'primary' : 'default'" secondary @click="toggleState('read')">{{ state.read ? '✓ 已读' : '标为已读' }}</n-button>
          <n-button size="tiny" block :type="state.favorited ? 'warning' : 'default'" secondary @click="toggleState('favorited')">{{ state.favorited ? '★ 已收藏' : '☆ 收藏' }}</n-button>
        </div>
        <div class="pgroup">
          <div class="ptitle">排版(本地保存)</div>
          <label class="prow">字号 <n-select v-model:value="settings.fontSize" :options="fontOptions" size="tiny" style="width: 76px" /></label>
          <label class="prow">行宽 <n-select v-model:value="settings.width" :options="widthOptions" size="tiny" style="width: 76px" /></label>
          <label class="prow">行高 <n-select v-model:value="settings.lineHeight" :options="lhOptions" size="tiny" style="width: 76px" /></label>
          <label class="prow">主题 <n-select v-model:value="settings.theme" :options="themeOptions" size="tiny" style="width: 76px" /></label>
          <n-button size="tiny" block quaternary @click="settings.contrast = !settings.contrast">{{ settings.contrast ? '✓ 强对比' : '强对比' }}</n-button>
        </div>
        <div class="pgroup">
          <div class="ptitle">进度与导出</div>
          <div v-if="hasSaved" class="prow">上次读到 <b>第 {{ (lastSaved.anchor_seq ?? 0) + 1 }} 章 · {{ Math.round(lastSaved.top_percent ?? 0) }}%</b></div>
          <n-button v-if="hasSaved" size="tiny" block quaternary @click="progress.resume(lastSaved)">继续上次</n-button>
          <n-button size="tiny" block quaternary @click="progress.reset()">重置进度</n-button>
          <n-button size="tiny" block quaternary tag="a" :href="`/api/reports/${route.params.vid}/export`">导出 Markdown</n-button>
        </div>
      </aside>

      <article class="article" v-html="report.html" @click="(e) => e.target.closest('.ev-source') && openSource({ currentTarget: e.target.closest('.ev-source') })"></article>

      <aside v-if="toc.length" class="toc">
        <div class="toc-title">本页大纲</div>
        <ul class="toc-list">
          <li v-for="s in toc" :key="s.seq">
            <a
              :href="`#sec-${s.seq}`"
              :class="{ active: activeSeq === s.seq, sub: s.level === 3 }"
              :data-seq="s.seq"
              @click.prevent="spy.ignoreScrollOnce = true; jump(s.seq)"
            >{{ s.title }}</a>
          </li>
        </ul>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.reader { padding: 24px 32px 80px; }
.body {
  /* 两侧对称 1fr:正文视口居中,面板贴左缘、大纲贴右缘,与正文间距一致(UX-61) */
  display: grid; grid-template-columns: minmax(200px, 1fr) min(var(--sd-width), 100%) minmax(200px, 1fr);
  gap: 72px;
}
.panel {
  grid-column: 1; justify-self: start; width: 200px;
  position: sticky; top: 76px; align-self: start;
  display: flex; flex-direction: column; gap: 18px;
}
.pgroup { display: flex; flex-direction: column; gap: 8px; }
.ptitle {
  font-size: 11px; font-weight: 600; color: var(--sd-text-3);
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 2px;
}
.ptitle kbd { font-size: 9px; margin-left: 4px; }
.pbig { font-weight: 600; font-size: 0.95em; overflow-wrap: anywhere; }
.prow { color: var(--sd-text-2); font-size: 0.82em; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.prow.warn { color: var(--sd-ev-infer); }
.panel :deep(kbd) { font-size: 9px; }
.article { grid-column: 2; }
.toc {
  grid-column: 3; width: 200px; justify-self: end;
  position: sticky; top: 56px; align-self: start;
  height: calc(100vh - 56px); overflow-y: auto;
  padding: 32px 0 0;
}
.toc::-webkit-scrollbar { width: 4px; }
.toc::-webkit-scrollbar-thumb { background: var(--sd-border); border-radius: 2px; }
.toc-title {
  font-size: 12px; font-weight: 600; color: var(--sd-text-3);
  text-transform: uppercase; letter-spacing: 0.08em; padding-bottom: 12px;
}
.toc-list { list-style: none; margin: 0; padding: 0; border-left: 1px solid var(--sd-border); }
.toc-list a {
  display: block; padding: 5px 0 5px 16px;
  font-size: 13px; color: var(--sd-text-2); letter-spacing: -0.12px;
  border-left: 2px solid transparent; margin-left: -1px;
  transition: all 0.12s; cursor: pointer;
}
.toc-list a:hover { color: var(--sd-text); }
.toc-list a.sub { padding-left: 28px; font-size: 12px; }
.toc-list a.active { color: var(--sd-accent); border-left-color: var(--sd-accent); font-weight: 500; } /* 指示条跟随(UX-59) */
@media (max-width: 1365px) {
  .toc { display: none; } /* 窄屏收起目录 */
  .body { grid-template-columns: 200px min(var(--sd-width), 100%); }
  .article { grid-column: 2; }
}
@media (max-width: 1023px) {
  /* 移动/平板:面板转为顶部横排流式,不再占据左栏 */
  .body { display: flex; flex-direction: column; gap: 24px; }
  .panel { position: static; flex-direction: row; flex-wrap: wrap; gap: 16px 24px; }
  .pgroup { min-width: 180px; }
  .article { width: 100%; }
}
@media (max-width: 767px) { .reader { padding: 12px 12px 48px; } }
</style>

<style>
/* 服务端渲染正文内证据块(UX-43..47):虚线只属于分析推断 */
.article { overflow-wrap: break-word; font-size: var(--sd-font-size); line-height: var(--sd-line-height); }
.article h2, .article h3 { border-top: 1px solid var(--sd-border); padding-top: 28px; margin-top: 44px; }
.article h2 { font-size: 1.25em; } .article h3 { font-size: 1.08em; }
.article p { margin: 0.9em 0; }
.article pre { background: var(--sd-code-bg); color: var(--sd-text); font-family: var(--sd-font-mono); padding: 14px; border-radius: 6px; overflow-x: auto; font-size: 0.88em; }
.article code { font-family: var(--sd-font-mono); }
.article table { border-collapse: collapse; display: block; overflow-x: auto; max-width: 100%; }
.article th, .article td { border: 1px solid var(--sd-border); padding: 6px 12px; }
.article blockquote { border-left: 3px solid var(--sd-accent); margin: 0; padding: 2px 16px; color: var(--sd-text-2); }
.article .ev { border: 1px solid var(--sd-border); border-radius: 6px; padding: 10px 14px; margin: 14px 0; background: var(--sd-surface); }
.article .ev .ev-label { font-size: 0.75em; letter-spacing: 0.1em; color: var(--sd-text-3); display: block; margin-bottom: 4px; }
.article .ev .ev-ref { font-family: var(--sd-font-mono); font-size: 0.9em; }
.article .ev p { margin: 4px 0; }
.article .ev-source { border-left: 3px solid var(--sd-ev-source); cursor: pointer; }
.article .ev-source:hover { background: color-mix(in srgb, var(--sd-ev-source) 6%, var(--sd-surface)); }
.article .ev-author { border-left: 3px solid var(--sd-ev-author); }
.article .ev-infer { border-left: 3px dashed var(--sd-ev-infer); }
.article .ev-external { border-left: 3px solid var(--sd-ev-external); }
.article .ev-unknown { border-left: 3px solid var(--sd-ev-unknown); }
.article .ev a { word-break: break-all; }
.article .ev .ev-date { color: var(--sd-text-3); font-size: 0.8em; margin-left: 8px; }
.article .mermaid { text-align: center; }
.article figcaption { font-size: 0.75em; color: var(--sd-text-3); text-align: center; padding-top: 6px; letter-spacing: 0.04em; }
.article .zoomable { cursor: zoom-in; border-radius: 6px; }
.article .zoomable:hover { background: color-mix(in srgb, var(--sd-accent) 4%, var(--sd-surface)); }
#sd-zoom { position: fixed; inset: 0; z-index: 60; background: #000d; display: flex; flex-direction: column; outline: none; }
#sd-zoom .zoom-head { color: var(--sd-text); padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; background: var(--sd-surface); }
#sd-zoom .zoom-close { background: var(--sd-elevated); }
#sd-zoom .zoom-stage { flex: 1; overflow: hidden; display: flex; align-items: center; justify-content: center; cursor: grab; touch-action: none; }
#sd-zoom .zoom-canvas { width: min(92vw, 1100px); transition: transform 0.06s; }
#sd-zoom .zoom-canvas svg { width: 100%; height: auto; }
#sd-zoom .zoom-hint { color: var(--sd-text-3); text-align: center; padding: 10px; font-size: 0.82em; }
</style>
