// 入口:装配路由三区(UX-21)+ 组件库注册(UX-60);报告阅读面在 /reports 静态站(ADR-0009)
import { createApp, h } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import naive from 'naive-ui'

import App from './App.vue'
import './styles/tokens.css'
import AnalysisBoard from './views/AnalysisBoard.vue'
import ReadingHome from './views/ReadingHome.vue'
import RepoLibrary from './views/RepoLibrary.vue'
import SettingsView from './views/SettingsView.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/reading' },
    { path: '/reading', component: ReadingHome },
    { path: '/repos', component: RepoLibrary },
    { path: '/analysis', component: AnalysisBoard },
    { path: '/settings', component: SettingsView },
  ],
})

createApp({ render: () => h(App) }).use(router).use(naive).mount('#app')

window.addEventListener('unhandledrejection', (e) => {
  import('./api').then(({ toast }) => toast(`出错了:${e.reason?.message ?? '未知错误'}`))
})
