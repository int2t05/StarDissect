// scrollspy composable(UX-59:移植 VitePress useActiveAnchor 算法)
// 节流防抖(首调立即、尾部防抖 100ms);判定=最后一个越过视口顶(+scroll-margin+4px 容差)的标题;
// 页顶置空、页底取最后;坐标经 offsetParent 链累加(过滤 display:none);目录点击置 ignoreScrollOnce 防闪跳
import { ref } from 'vue'

export function useScrollSpy(headerOffset = 4) {
  const activeSeq = ref(-1)
  const ignoreScrollOnce = ref(false)
  let timer = null
  let lastCall = 0

  function throttleAndDebounce(fn) {
    return () => {
      const now = Date.now()
      if (now - lastCall >= 100) {
        lastCall = now
        fn()
      }
      clearTimeout(timer)
      timer = setTimeout(() => {
        lastCall = Date.now()
        fn()
      }, 100)
    }
  }

  function getAbsoluteTop(el) {
    let top = 0
    let cur = el
    while (cur) {
      if (getComputedStyle(cur).display === 'none') return 0
      top += cur.offsetTop
      cur = cur.offsetParent
    }
    return top
  }

  function getScrollMarginTop(el) {
    return parseFloat(getComputedStyle(el).scrollMarginTop || '0')
  }

  function update() {
    if (ignoreScrollOnce.value) {
      ignoreScrollOnce.value = false
      return
    }
    const anchors = [...document.querySelectorAll('.article [data-seq]')]
    if (!anchors.length) return
    const doc = document.documentElement
    const scrollTop = window.scrollY
    if (scrollTop <= 0) {
      activeSeq.value = -1 // 页顶置空
      return
    }
    if (scrollTop >= doc.scrollHeight - doc.clientHeight - 1) {
      activeSeq.value = Number(anchors[anchors.length - 1].dataset.seq) // 页底取最后
      return
    }
    let current = -1
    for (const el of anchors) {
      if (getAbsoluteTop(el) - getScrollMarginTop(el) - headerOffset <= scrollTop) {
        current = Number(el.dataset.seq)
      } else {
        break
      }
    }
    if (current !== activeSeq.value) {
      activeSeq.value = current
      const btn = document.querySelector(`.toc [data-seq="${current}"]`)
      btn?.scrollIntoView({ block: 'nearest' }) // 目录跟随滚动不闪跳
    }
  }

  const onScroll = throttleAndDebounce(update)

  function mount() {
    window.addEventListener('scroll', onScroll, { passive: true })
    update()
  }

  function unmount() {
    window.removeEventListener('scroll', onScroll)
    clearTimeout(timer)
  }

  return { activeSeq, ignoreScrollOnce, mount, unmount }
}
