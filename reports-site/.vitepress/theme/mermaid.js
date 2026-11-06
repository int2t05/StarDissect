/**
 * Mermaid 阅读面渲染器：Markdown 插件与客户端共用标签规范化规则，
 * 客户端统一处理异步渲染、主题切换、失败源码和放大交互。
 */

/** 未加引号的节点标签补双引号，避免 `{}` 等字符被解析成 Mermaid 语法。 */
export function normalizeMermaidSource(source) {
  return source.replace(/([A-Za-z0-9_]+)\[(?!")([^\]\[\n"]+)\]/g, '$1["$2"]')
}

/** 管理报告页的 Mermaid 图表生命周期。 */
export function createMermaidRenderer({ documentRef = globalThis.document, onZoom }) {
  const sources = new WeakMap()
  let generation = 0
  let nextDiagramId = 0
  let appearanceObserver = null

  function currentTheme() {
    return documentRef.documentElement.classList.contains('dark') ? 'dark' : 'neutral'
  }

  function makeFigure(block, number, source) {
    const figure = documentRef.createElement('figure')
    figure.className = 'mermaid-figure'
    figure.dataset.mermaidFigure = 'true'
    figure.dataset.diagramNumber = String(number)

    const holder = documentRef.createElement('div')
    holder.className = 'zoomable'
    holder.tabIndex = 0
    holder.setAttribute('role', 'button')
    holder.setAttribute('aria-label', `放大图 ${number}`)
    holder.textContent = '图表渲染中…'

    const caption = documentRef.createElement('figcaption')
    caption.textContent = `图 ${number} · 点击放大`

    const fallback = documentRef.createElement('details')
    fallback.className = 'mermaid-fallback'
    const summary = documentRef.createElement('summary')
    summary.textContent = '图表源码'
    const pre = documentRef.createElement('pre')
    pre.textContent = source
    fallback.append(summary, pre)
    figure.append(holder, caption, fallback)
    sources.set(figure, source)

    const activate = () => {
      const svg = holder.querySelector('svg')
      if (svg) onZoom?.(svg, caption.textContent ?? '', holder)
    }
    holder.addEventListener('click', activate)
    holder.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        activate()
      }
    })
    block.replaceWith(figure)
    return figure
  }

  function setFailure(figure) {
    if (!figure.isConnected) return
    const number = figure.dataset.diagramNumber
    const holder = figure.querySelector('.zoomable')
    const caption = figure.querySelector('figcaption')
    const fallback = figure.querySelector('.mermaid-fallback')
    holder.textContent = '图表暂时无法渲染'
    holder.removeAttribute('role')
    holder.removeAttribute('tabindex')
    caption.textContent = `图 ${number} · 渲染失败，已展开源码`
    fallback.open = true
    figure.dataset.renderState = 'error'
  }

  /** 渲染当前报告；新导航或主题切换会让旧任务失效。 */
  async function render() {
    const doc = documentRef.querySelector('.vp-doc')
    if (!doc) return

    const blocks = [...doc.querySelectorAll('.mermaid')]
    let number = doc.querySelectorAll('figure.mermaid-figure').length
    for (const block of blocks) {
      number += 1
      const source = block.querySelector('.mermaid-source')?.textContent ?? block.textContent ?? ''
      makeFigure(block, number, source)
    }

    const figures = [...doc.querySelectorAll('figure.mermaid-figure')]
    if (!figures.length) return

    const run = ++generation
    try {
      const mermaid = (await import('mermaid')).default
      if (run !== generation) return
      mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: currentTheme() })

      for (const figure of figures) {
        if (run !== generation) return
        if (!figure.isConnected) continue

        const source = normalizeMermaidSource(sources.get(figure) ?? '')
        const number = figure.dataset.diagramNumber
        const holder = figure.querySelector('.zoomable')
        const caption = figure.querySelector('figcaption')
        const fallback = figure.querySelector('.mermaid-fallback')

        try {
          if (!(await mermaid.parse(source, { suppressErrors: true }))) throw new Error('Mermaid 语法无效')
          const { svg } = await mermaid.render(`sd-mermaid-${++nextDiagramId}`, source)
          if (run !== generation || !figure.isConnected) return
          holder.innerHTML = svg
          holder.setAttribute('role', 'button')
          holder.setAttribute('tabindex', '0')
          holder.setAttribute('aria-label', `放大图 ${number}`)
          caption.textContent = `图 ${number} · 点击放大`
          fallback.open = false
          figure.dataset.renderState = 'ready'
        } catch {
          if (run !== generation) return
          setFailure(figure)
        }
      }
    } catch {
      if (run === generation) figures.forEach(setFailure)
    }
  }

  /** Mermaid 会把主题写入已生成的 SVG，因此须在 VitePress 明暗切换后重新输出。 */
  function observeAppearance() {
    if (appearanceObserver || !documentRef.documentElement) return
    const Observer = documentRef.defaultView?.MutationObserver ?? globalThis.MutationObserver
    if (!Observer) return
    appearanceObserver = new Observer(() => { void render() })
    appearanceObserver.observe(documentRef.documentElement, { attributes: true, attributeFilter: ['class'] })
  }

  function dispose() {
    generation += 1
    appearanceObserver?.disconnect()
    appearanceObserver = null
  }

  return { render, observeAppearance, dispose }
}
