<!-- 应用壳:顶栏导航 + 居中内容范式(UX-61);组件库 Naive UI 主题映射(UX-60) -->
<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NConfigProvider, NMessageProvider, useOsTheme } from 'naive-ui'
import { useKeyboard } from './composables/useKeyboard'
import { useReaderSettings } from './composables/useReaderSettings'
import { naiveTheme, overridesFor } from './theme'

useReaderSettings()
const { handler, helpVisible } = useKeyboard()
onMounted(() => window.addEventListener('keydown', handler))
onUnmounted(() => window.removeEventListener('keydown', handler))

const route = useRoute()
const router = useRouter()
const osTheme = useOsTheme()
const { settings } = useReaderSettings()

const nTheme = computed(() => naiveTheme(settings.theme, osTheme.value))
const nOverrides = computed(() => overridesFor(settings.theme, osTheme.value))

const menuOptions = [
  { label: '阅读中心', key: '/reading' },
  { label: '仓库库', key: '/repos' },
  { label: '分析管理', key: '/analysis' },
  { label: '系统设置', key: '/settings' },
]
function onMenu(key) {
  router.push(key)
}
</script>

<template>
  <n-config-provider :theme="nTheme" :theme-overrides="nOverrides">
    <n-message-provider>
      <div class="app">
        <header class="topbar">
          <div class="topbar-inner">
            <div class="brand" @click="router.push('/reading')">星剖</div>
            <nav class="nav">
              <RouterLink
                v-for="m in menuOptions"
                :key="m.key"
                :to="m.key"
                :class="{ active: route.path.startsWith(m.key) }"
              >{{ m.label }}</RouterLink>
            </nav>
            <span class="kbd-hint"><kbd>/</kbd> 搜索 <kbd>?</kbd> 快捷键</span>
          </div>
        </header>
        <main class="main"><RouterView /></main>
      </div>
      <div v-if="helpVisible" class="help" @click="helpVisible = false">
        <div class="help-panel">
          <h3>键盘快捷键</h3>
          <p><kbd>g u/b/h/s</kbd> 跳转四区 · <kbd>/</kbd> 搜索 · <kbd>?</kbd> 本帮助</p>
          <p><kbd>j/k</kbd> 移动 · <kbd>o/Enter</kbd> 打开 · <kbd>g g</kbd> 回顶 · <kbd>G</kbd> 到底</p>
          <p><kbd>m</kbd> 已读切换 · <kbd>f</kbd> 收藏 · <kbd>[ ]</kbd> 字号</p>
        </div>
      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.app { min-height: 100vh; display: flex; flex-direction: column; }
.topbar {
  position: sticky; top: 0; z-index: 20;
  background: color-mix(in srgb, var(--sd-bg) 88%, transparent);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--sd-border);
}
.topbar-inner {
  max-width: 1200px; margin: 0 auto; padding: 0 24px; height: 56px;
  display: flex; align-items: center; gap: 32px;
}
.brand { font-size: 18px; font-weight: 700; color: var(--sd-accent); cursor: pointer; letter-spacing: 0.06em; }
.nav { display: flex; gap: 4px; flex: 1; }
.nav a { padding: 6px 14px; border-radius: 6px; color: var(--sd-text-2); font-size: 15px; }
.nav a:hover { color: var(--sd-text); background: var(--sd-accent-soft); }
.nav a.router-link-active { color: var(--sd-accent); background: var(--sd-accent-soft); } /* 当前项单强调色(UX-01) */
.kbd-hint { color: var(--sd-text-3); font-size: 12px; }
.main { flex: 1; }
.help { position: fixed; inset: 0; background: var(--sd-overlay); display: flex; align-items: center; justify-content: center; z-index: 30; }
.help-panel { background: var(--sd-surface); border: 1px solid var(--sd-border-strong); border-radius: 8px; padding: 20px 28px; }
.help-panel h3 { margin-top: 0; color: var(--sd-accent); }
@media (max-width: 767px) {
  .topbar-inner { gap: 12px; padding: 0 12px; }
  .kbd-hint { display: none; }
}
</style>
