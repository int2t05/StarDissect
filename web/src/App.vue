// 应用壳:四区导航(UX-21)+ 键盘注册 + 路由出口;桌面左导航 208px(UX-22)
<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useKeyboard } from './composables/useKeyboard'
import { useReaderSettings } from './composables/useReaderSettings'

useReaderSettings()
const { handler } = useKeyboard()
onMounted(() => window.addEventListener('keydown', handler))
onUnmounted(() => window.removeEventListener('keydown', handler))
</script>

<template>
  <div class="shell">
    <nav class="side">
      <div class="brand">星剖</div>
      <RouterLink to="/reading">阅读中心 <kbd>g u</kbd></RouterLink>
      <RouterLink to="/repos">仓库库 <kbd>g b</kbd></RouterLink>
      <RouterLink to="/analysis">分析管理 <kbd>g h</kbd></RouterLink>
      <RouterLink to="/settings">系统设置 <kbd>g s</kbd></RouterLink>
    </nav>
    <main class="main"><RouterView /></main>
  </div>
</template>

<style scoped>
.shell { display: flex; min-height: 100vh; }
.side {
  width: 208px; flex: none; padding: 16px 12px;
  background: var(--sd-surface); border-right: 1px solid var(--sd-border);
  display: flex; flex-direction: column; gap: 4px; position: sticky; top: 0; height: 100vh;
}
.brand { font-size: 18px; font-weight: 600; padding: 4px 8px 16px; color: var(--sd-accent); }
.side a { padding: 8px; border-radius: 6px; color: var(--sd-text-2); display: flex; justify-content: space-between; }
.side a.router-link-active { background: var(--sd-accent-soft); color: var(--sd-accent); } /* 当前项单强调色(UX-01) */
kbd { font-size: 11px; color: var(--sd-text-3); font-family: var(--sd-font-mono); }
.main { flex: 1; min-width: 0; padding: 24px; }
@media (max-width: 767px) { /* UX-24:移动抽屉简化为顶部横排 */
  .shell { flex-direction: column; }
  .side { width: 100%; height: auto; position: static; flex-direction: row; }
  .main { padding: 12px; }
}
</style>
