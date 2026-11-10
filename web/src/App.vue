<!-- 应用壳:顶栏导航 + 居中内容范式(UX-61);组件库 Naive UI 主题映射(UX-60) -->
<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { dateZhCN, NConfigProvider, NMessageProvider, zhCN } from 'naive-ui'
import { useKeyboard } from './composables/useKeyboard'
import { useReaderSettings } from './composables/useReaderSettings'
import { naiveTheme, overridesFor } from './theme'

useReaderSettings()
const { handler, helpVisible, echo } = useKeyboard()
onMounted(() => window.addEventListener('keydown', handler))
onUnmounted(() => window.removeEventListener('keydown', handler))

const route = useRoute()
const { settings } = useReaderSettings()

const nTheme = computed(() => naiveTheme(settings.theme))
const nOverrides = computed(() => overridesFor(settings.theme))

const menuOptions = [
  { label: '阅读中心', key: '/reading' },
  { label: '仓库库', key: '/repos' },
  { label: '分析管理', key: '/analysis' },
  { label: '系统设置', key: '/settings' },
  { label: '报告', key: '/reports/', external: true },
]
function toggleTheme() {
  settings.theme = settings.theme === 'dark' ? 'light' : 'dark'
}
</script>

<template>
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN" :theme="nTheme" :theme-overrides="nOverrides">
    <n-message-provider>
      <div class="app">
        <header class="topbar">
          <div class="topbar-inner">
            <RouterLink class="brand" to="/reading">星剖</RouterLink>
            <nav class="nav" aria-label="主导航">
              <template v-for="m in menuOptions" :key="m.key">
                <a v-if="m.external" :href="m.key">{{ m.label }}</a>
                <RouterLink v-else :to="m.key" :class="{ active: route.path.startsWith(m.key) }">{{ m.label }}</RouterLink>
              </template>
            </nav>
            <div class="topbar-tools">
              <button class="theme-toggle" type="button" @click="toggleTheme">
                {{ settings.theme === 'dark' ? '浅色模式' : '深色模式' }}
              </button>
              <span class="kbd-hint"><kbd>/</kbd> 搜索 <kbd>?</kbd> 快捷键</span>
            </div>
          </div>
        </header>
        <main class="main"><RouterView /></main>
      </div>
      <Transition name="key-echo">
        <div v-if="echo" key="echo" class="key-echo">{{ echo }}</div>
      </Transition>
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
  background: var(--sd-bg);
  border-bottom: 1px solid var(--sd-border);
}
.topbar-inner {
  max-width: 1100px; margin: 0 auto; padding: 0 24px; height: 56px;
  display: flex; align-items: center; gap: 24px;
}
.brand { font-size: 16px; font-weight: 600; color: var(--sd-text); letter-spacing: 0.02em; }
.nav { display: flex; gap: 4px; flex: 1; }
.nav a { padding: 6px 10px; border-radius: 6px; color: var(--sd-text-2); font-size: 13px; white-space: nowrap; }
.nav a:hover { color: var(--sd-text); background: var(--sd-accent-soft); }
.nav a.router-link-active { color: var(--sd-accent); box-shadow: inset 0 -2px var(--sd-accent); }
.kbd-hint { color: var(--sd-text-3); font-size: 12px; }
.topbar-tools { display: flex; align-items: center; gap: 14px; white-space: nowrap; }
.theme-toggle { padding: 4px 9px; border-color: var(--sd-border); background: transparent; color: var(--sd-text-2); font-size: 12px; }
.theme-toggle:hover { color: var(--sd-accent); border-color: var(--sd-border-strong); }
.main { flex: 1; }
.key-echo {
  position: fixed; left: 20px; bottom: 20px; z-index: 40;
  background: var(--sd-elevated); color: var(--sd-accent);
  border: 1px solid var(--sd-border-strong); border-radius: 8px;
  font-family: var(--sd-font-mono); font-size: 15px; font-weight: 600;
  padding: 8px 14px;
}
.key-echo-enter-active, .key-echo-leave-active { transition: all 0.18s; }
.key-echo-enter-from, .key-echo-leave-to { opacity: 0; transform: translateY(6px); }
.help { position: fixed; inset: 0; background: var(--sd-overlay); display: flex; align-items: center; justify-content: center; z-index: 30; }
.help-panel { background: var(--sd-surface); border: 1px solid var(--sd-border-strong); border-radius: 10px; padding: 20px 28px; }
.help-panel h3 { margin-top: 0; color: var(--sd-accent); }
@media (max-width: 767px) {
  .topbar-inner { height: auto; min-height: 56px; gap: 4px 12px; padding: 8px 12px 4px; flex-wrap: wrap; }
  .brand { order: 0; }
  .topbar-tools { order: 1; gap: 8px; margin-left: auto; }
  .nav { order: 2; flex: 1 0 100%; width: 100%; min-width: 0; gap: 4px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: none; }
  .nav::-webkit-scrollbar { display: none; }
  .nav a { flex: 0 0 auto; min-height: 32px; display: inline-flex; align-items: center; padding-inline: 8px; font-size: 12px; }
  .kbd-hint { display: none; }
}
</style>
