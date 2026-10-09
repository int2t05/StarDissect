<!-- 报告阅读页:服务端渲染 HTML 直出(REQ-READ-001)、目录定位(REQ-READ-002)、
     进度高水位上报(REQ-READ-003)、格式调节(REQ-READ-001/UX-30..33)、证据块样式(UX-43..47)
     布局:文章居中占主体,目录右浮(UX-61,VitePress 式) -->
<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NSelect } from 'naive-ui'
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
  await progress.restore()  // 跨设备恢复(REQ-READ-003)
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
      const mermaid = (await import('mermaid')).default  // 本地依赖随构建打包(E16:内网自托管不依赖外部 CDN)
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
    <header class="bar">
      <div class="title">
        <h1>{{ report.repo_name }} · v{{ report.version_no }}</h1>
        <span class="meta">commit {{ report.commit_anchor.slice(0, 8) }} · {{ report.created_at }}</span>
        <span v-if="violations > 0" class="meta warn">排版提示 {{ violations }} 处</span>
      </div>
      <div class="tools">
        <n-button size="tiny" secondary @click="toggleState('read')">{{ state.read ? '已读' : '未读' }} <kbd>m</kbd></n-button>
        <n-button size="tiny" secondary @click="toggleState('favorited')">{{ state.favorited ? '★ 已藏' : '☆ 收藏' }} <kbd>f</kbd></n-button>
        <n-select v-model:value="settings.fontSize" :options="fontOptions" size="tiny" style="width: 84px" />
        <n-select v-model:value="settings.width" :options="widthOptions" size="tiny" style="width: 76px" />
        <n-select v-model:value="settings.lineHeight" :options="lhOptions" size="tiny" style="width: 90px" />
        <n-select v-model:value="settings.theme" :options="themeOptions" size="tiny" style="width: 96px" />
        <n-button size="tiny" quaternary @click="settings.contrast = !settings.contrast">{{ settings.contrast ? '标准对比' : '强对比' }}</n-button>
        <n-button size="tiny" quaternary @click="progress.reset()">重置进度</n-button>
        <n-button size="tiny" quaternary tag="a" :href="`/api/reports/${route.params.vid}/export`">导出 MD</n-button>
      </div>
    </header>

    <div class="body">
      <article class="article" v-html="report.html" @click="(e) => e.target.closest('.ev-source') && openSource({ currentTarget: e.target.closest('.ev-source') })"></article>
      <aside v-if="toc.length" class="toc">
        <button
          v-for="s in toc"
          :key="s.seq"
          :class="{ active: activeSeq === s.seq, sub: s.level === 3 }"
          :data-seq="s.seq"
          @click="spy.ignoreScrollOnce = true; jump(s.seq)"
        >
          {{ s.title }}
        </button>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.reader { padding: 20px 24px 72px; }
.bar {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; flex-wrap: wrap;
  max-width: calc(var(--sd-width) + 560px); margin: 0 auto 28px;
  padding-bottom: 16px; border-bottom: 1px solid var(--sd-border);
}
.bar h1 { font-size: 19px; margin: 0 0 4px; }
.meta { color: var(--sd-text-3); font-size: 0.82em; font-family: var(--sd-font-mono); margin-right: 12px; }
.meta.warn { color: var(--sd-ev-infer); }
.tools { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.tools kbd { font-size: 9px; margin-left: 2px; }
.body { display: flex; justify-content: center; gap: 64px; }
.article { width: min(var(--sd-width), 100%); flex: none; }
.toc {
  width: 230px; flex: none; position: sticky; top: 76px; align-self: flex-start;
  max-height: calc(100vh - 110px); overflow-y: auto;
  display: flex; flex-direction: column; border-left: 2px solid var(--sd-border);
}
.toc button { text-align: left; border: 0; background: none; color: var(--sd-text-2); padding: 4px 12px; font-size: 0.85em; cursor: pointer; }
.toc button:hover { color: var(--sd-text); }
.toc button.sub { padding-left: 26px; }
.toc button.active { color: var(--sd-accent); border-left: 2px solid var(--sd-accent); margin-left: -2px; } /* 指示条跟随(UX-59) */
@media (max-width: 1365px) { .toc { display: none; } } /* 窄屏收起目录 */
@media (max-width: 767px) { .reader { padding: 12px 12px 48px; } }
</style>

<style>
/* 服务端渲染正文内证据块(UX-43..47):虚线只属于分析推断 */
.article { overflow-wrap: break-word; font-size: var(--sd-font-size); line-height: var(--sd-line-height); }
.article h2, .article h3 { border-top: 1px solid var(--sd-border); padding-top: 24px; margin-top: 36px; }
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
</style>
