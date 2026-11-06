// 格式调节与持久化(UX-30..34):localStorage 本地保存(DEC-04)
import { reactive, watchEffect } from 'vue'

const KEY = 'sd-reader-settings'
const THEME_KEY = 'vitepress-theme-appearance'
const defaults = { fontSize: 16.5, width: 'standard', lineHeight: '1.8', theme: 'light', contrast: false }

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || '{}')
    const theme = localStorage.getItem(THEME_KEY)
    return { ...defaults, ...saved, theme: theme === 'dark' ? 'dark' : 'light' }
  } catch { return { ...defaults } }
}

let instance = null

export function useReaderSettings() {
  if (instance) return instance  // 单例:多视图共享同一偏好状态,避免双写
  const settings = reactive(load())
  watchEffect(() => {
    const root = document.documentElement
    root.dataset.theme = settings.theme
    root.dataset.width = settings.width
    root.dataset.lh = settings.lineHeight
    root.style.setProperty('--sd-font-size', settings.fontSize + 'px')
    root.dataset.contrast = settings.contrast ? '1' : '0'  // 匹配 tokens 的 [data-contrast] 选择器
    try {
      localStorage.setItem(KEY, JSON.stringify({ ...settings }))
      localStorage.setItem(THEME_KEY, settings.theme)
    } catch {
      // 隐私模式禁用本地存储时，当前会话仍可切换主题与排版
    }
  })
  window.addEventListener('storage', (event) => {
    if (event.key === THEME_KEY && ['light', 'dark'].includes(event.newValue)) settings.theme = event.newValue
  })
  instance = { settings }
  return instance
}
