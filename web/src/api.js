// 统一 API 访问:非 2xx 抛错并全局 toast,消灭静默白屏
export function toast(message) {
  let host = document.getElementById('sd-toast')
  if (!host) {
    host = document.createElement('div')
    host.id = 'sd-toast'
    document.body.appendChild(host)
  }
  const el = document.createElement('div')
  el.className = 'sd-toast-item'
  el.textContent = message
  host.appendChild(el)
  setTimeout(() => el.remove(), 4000)
}

export async function api(url, options) {
  const res = await fetch(url, options)
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (body.detail) detail = body.detail
    } catch { /* 非 JSON 错误体,保留状态码 */ }
    toast(`请求失败:${detail}`)
    throw new Error(detail)
  }
  return res.json()
}

export async function apiRaw(url) {
  const res = await fetch(url)
  if (!res.ok) {
    toast(`请求失败:HTTP ${res.status}`)
    throw new Error(`HTTP ${res.status}`)
  }
  return res
}
