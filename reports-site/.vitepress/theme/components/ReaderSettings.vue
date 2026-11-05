<script setup lang="ts">
// 排版调节与持久化（UX-30..34）：localStorage 本地保存（DEC-04），键带 reports- 前缀
// （与 SPA 的 sd-reader-settings 分开——两套界面各自记忆，互不覆写）。
// 主题不在这里：VitePress 自带深浅色开关。
import { onMounted, onUnmounted, reactive, watchEffect } from 'vue'

const KEY = 'reports-reader-settings'
const defaults = { fontSize: 15.5, width: 'standard', lineHeight: '1.8', contrast: false }

function load(): typeof defaults {
  try {
    return { ...defaults, ...JSON.parse(localStorage.getItem(KEY) || '{}') }
  } catch {
    return { ...defaults }
  }
}

const settings = reactive(load())

// [ ] 键调字号（ProgressTracker 派发）
function onFontKey(e: Event): void {
  adjustFont((e as CustomEvent<number>).detail)
}
onMounted(() => window.addEventListener('sd-font', onFontKey))
onUnmounted(() => window.removeEventListener('sd-font', onFontKey))

watchEffect(() => {
  const root = document.documentElement
  root.dataset.sdWidth = settings.width
  root.dataset.sdLh = settings.lineHeight
  root.style.setProperty('--sd-font-size', settings.fontSize + 'px')
  root.dataset.sdContrast = settings.contrast ? '1' : '0'
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...settings }))
  } catch {
    // 存储不可写（隐私模式等）：调节本来就是本地尽力而为
  }
})

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
  <span class="sd-ctl">
    <label>字号
      <select v-model.number="settings.fontSize">
        <option v-for="o in fontOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
    </label>
    <button type="button" title="字号减一（[）" @click="adjustFont(-1)">A−</button>
    <button type="button" title="字号加一（]）" @click="adjustFont(1)">A＋</button>
    <label>行宽
      <select v-model="settings.width">
        <option v-for="o in widthOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
    </label>
    <label>行高
      <select v-model="settings.lineHeight">
        <option v-for="o in lhOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
    </label>
    <button type="button" :class="{ on: settings.contrast }" @click="settings.contrast = !settings.contrast">
      {{ settings.contrast ? '✓ 强对比' : '强对比' }}
    </button>
  </span>
</template>

<style scoped>
.sd-ctl { display: inline-flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 12px; color: var(--vp-c-text-2); }
.sd-ctl select {
  font: inherit; color: var(--vp-c-text-1); background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider); border-radius: 6px; padding: 2px 6px;
}
.sd-ctl button {
  font: inherit; cursor: pointer; color: var(--vp-c-text-2);
  background: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider); border-radius: 6px; padding: 2px 8px;
}
.sd-ctl button:hover, .sd-ctl button.on { color: var(--vp-c-brand-1); border-color: var(--vp-c-brand-1); }
</style>
