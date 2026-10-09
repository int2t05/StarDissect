// 阅读进度 composable(UX-26..28 / UIUX §11 UX-58):高水位上报、跨设备恢复、显式重置
import { api } from '../api'

export function useReadingProgress(getVid, computeCurrent) {
  let timer = null

  async function report() {
    const { anchor_seq, top } = computeCurrent()
    await api(`/api/reports/${getVid()}/progress`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ anchor_seq, top_percent: top, bottom_percent: top }),
    })
  }

  function onScroll() {
    clearTimeout(timer)
    timer = setTimeout(report, 800) // 节流上报(UX-28)
  }

  async function restore() {
    const saved = await api(`/api/reports/${getVid()}/progress`)
    const target = document.querySelector(`[data-seq="${saved.anchor_seq ?? 0}"]`)
    if (target) target.scrollIntoView({ block: 'start' })
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
    restore,
    reset,
    mount: () => window.addEventListener('scroll', onScroll, { passive: true }),
    unmount: () => { window.removeEventListener('scroll', onScroll); clearTimeout(timer) },
  }
}
