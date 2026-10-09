// 格式调节与持久化(UX-30..34):localStorage 本地保存(DEC-04)
import { reactive, watchEffect } from 'vue'

const KEY = 'sd-reader-settings'
const defaults = { fontSize: 15.5, width: 'standard', lineHeight: '1.8', theme: 'dark', contrast: false }

function load() {
  try { return { ...defaults, ...JSON.parse(localStorage.getItem(KEY) || '{}') } } catch { return { ...defaults } }
}

export function useReaderSettings() {
  const settings = reactive(load())
  watchEffect(() => {
    const root = document.documentElement
    root.dataset.theme = settings.theme
    root.dataset.width = settings.width
    root.dataset.lh = settings.lineHeight
    root.style.setProperty('--sd-font-size', settings.fontSize + 'px')
    root.style.setProperty('--sd-contrast', settings.contrast ? '1' : '0')
    localStorage.setItem(KEY, JSON.stringify({ ...settings }))
  })
  return { settings }
}
