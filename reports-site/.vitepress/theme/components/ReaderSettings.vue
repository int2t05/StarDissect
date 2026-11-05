<script setup lang="ts">
// 排版调节与持久化（UX-30..34）：localStorage 本地保存（DEC-04），键带 reports- 前缀
// （与 SPA 的 sd-reader-settings 分开——两套界面各自记忆，互不覆写）。
// 主题不在这里：VitePress 自带深浅色开关。
import { onMounted, onUnmounted, reactive, watch } from 'vue'

const KEY = 'reports-reader-settings'
const defaults = { fontSize: 16.5, width: 'standard', lineHeight: '1.8', contrast: false }

function load(): typeof defaults {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || '{}')
    const fontSize = Number(saved.fontSize)
    return {
      fontSize: Number.isFinite(fontSize) ? Math.min(22, Math.max(12, fontSize)) : defaults.fontSize,
      width: ['narrow', 'standard', 'wide'].includes(saved.width) ? saved.width : defaults.width,
      lineHeight: ['1.6', '1.8', '2.0'].includes(saved.lineHeight) ? saved.lineHeight : defaults.lineHeight,
      contrast: typeof saved.contrast === 'boolean' ? saved.contrast : defaults.contrast,
    }
  } catch {
    return { ...defaults }
  }
}

const settings = reactive({ ...defaults })

// [ ] 键调字号（ProgressTracker 派发）
function onFontKey(e: Event): void {
  adjustFont((e as CustomEvent<number>).detail)
}
onMounted(() => {
  Object.assign(settings, load())
  apply()
  window.addEventListener('sd-font', onFontKey)
})
onUnmounted(() => window.removeEventListener('sd-font', onFontKey))

watch(settings, apply, { deep: true })

function apply(): void {
  const root = document.documentElement
  root.dataset.readerWidth = settings.width
  root.dataset.readerLh = settings.lineHeight
  root.style.setProperty('--reader-font-size', settings.fontSize + 'px')
  root.dataset.readerContrast = settings.contrast ? '1' : '0'
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...settings }))
  } catch {
    // 存储不可写（隐私模式等）：调节本来就是本地尽力而为
  }
}

const fontOptions = [12, 13, 14, 15.5, 16.5, 17, 19, 21, 22].map(v => ({ label: `${v}px`, value: v }))
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

function adjustFont(delta: number): void {
  settings.fontSize = Math.min(22, Math.max(12, settings.fontSize + delta))
}
</script>

<template>
  <span class="reader-settings">
    <label class="reader-setting">字号
      <select v-model.number="settings.fontSize" aria-label="阅读字号">
        <option v-for="o in fontOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
    </label>
    <button class="reader-action" type="button" title="字号减一（[）" aria-label="字号减一" @click="adjustFont(-1)">A−</button>
    <button class="reader-action" type="button" title="字号加一（]）" aria-label="字号加一" @click="adjustFont(1)">A＋</button>
    <label class="reader-setting">行宽
      <select v-model="settings.width" aria-label="阅读行宽">
        <option v-for="o in widthOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
    </label>
    <label class="reader-setting">行高
      <select v-model="settings.lineHeight" aria-label="阅读行高">
        <option v-for="o in lhOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
    </label>
    <button class="reader-action" type="button" :class="{ on: settings.contrast }" aria-label="切换强对比" @click="settings.contrast = !settings.contrast">
      {{ settings.contrast ? '✓ 强对比' : '强对比' }}
    </button>
  </span>
</template>
