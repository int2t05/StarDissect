// 阅读进度 composable(UX-26..28 / UIUX §11 UX-58):高水位上报、跨设备恢复、显式重置
import { api } from '../api'

const RETRY_KEY = 'sd-progress-retry'

export function useReadingProgress(getVid, computeCurrent) {
  let timer = null

  async function report() {
    const { anchor_seq, top, bottom } = computeCurrent()
    const vid = getVid()
    const body = JSON.stringify({ anchor_seq, top_percent: top, bottom_percent: bottom })
    try {
      await api(`/api/reports/${vid}/progress`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body,
      })
      localStorage.removeItem(RETRY_KEY)
    } catch {
      localStorage.setItem(RETRY_KEY, JSON.stringify({ vid, body })) // 上报失败本地缓存,下次打开重传(UX-28)
    }
  }

  async function flushRetry() {
    const raw = localStorage.getItem(RETRY_KEY)
    if (!raw) return
    const { vid, body } = JSON.parse(raw)
    localStorage.removeItem(RETRY_KEY)
    try {
      await api(`/api/reports/${vid}/progress`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body })
    } catch { /* 仍失败则留待下次 */ }
  }

  function onScroll() {
    clearTimeout(timer)
    timer = setTimeout(report, 800) // 节流上报(UX-28)
  }

  async function getSaved() {
    await flushRetry()
    return api(`/api/reports/${getVid()}/progress`) // 进入默认开头;恢复由用户显式触发(resume)
  }

  function resume(saved) {
    const target = document.querySelector(`[data-seq="${saved.anchor_seq ?? 0}"]`)
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  async function reset() {
    await api(`/api/reports/${getVid()}/progress`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ anchor_seq: 0, top_percent: 0, bottom_percent: 0, reset: true }),
    })
    window.scrollTo(0, 0)
  }

  return {
    report,
    getSaved,
    resume,
    reset,
    mount: () => window.addEventListener('scroll', onScroll, { passive: true }),
    unmount: () => { window.removeEventListener('scroll', onScroll); clearTimeout(timer) },
  }
}
