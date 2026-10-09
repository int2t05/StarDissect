// 键盘处理器(UX-35..37,miniflux 两键队列模型):g 前缀导航、单键动作;输入焦点忽略
import { ref } from 'vue'

const routes = { u: '/reading', b: '/repos', h: '/analysis', s: '/settings' }
const pending = ref(false)
const helpVisible = ref(false)

export function useKeyboard() {
  function handler(e) {
    if (e.target instanceof HTMLElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return
    if (e.isComposing) return // UX-39:中文输入法组词回车不触发
    if (pending.value) {
      pending.value = false
      if (e.key === 'g') { window.scrollTo({ top: 0 }); e.preventDefault(); return } // g g 回顶
      if (routes[e.key]) { location.hash = '#' + routes[e.key]; e.preventDefault() }
      return
    }
    if (e.key === 'G') { window.scrollTo({ top: document.body.scrollHeight }); e.preventDefault(); return } // G 到底
    if (e.key === 'g') { pending.value = true; setTimeout(() => (pending.value = false), 800); e.preventDefault(); return }
    if (e.key === '?') { helpVisible.value = !helpVisible.value; e.preventDefault(); return }
    if (e.key === '/') { location.hash = '#/reading'; setTimeout(() => document.querySelector('[data-search-open]')?.click(), 50); e.preventDefault() }
  }
  return { handler, helpVisible }
}
