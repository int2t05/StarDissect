// 入口:装配路由三区(UX-21)+ 组件库注册(UX-60);报告阅读面在 /reports 静态站(ADR-0009)
import { createApp, h } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import naive from 'naive-ui'

import App from './App.vue'
import './styles/tokens.css'
import { toast } from './api'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/reading' },
    { path: '/reading', component: () => import('./views/ReadingHome.vue') },
    { path: '/repos', component: () => import('./views/RepoLibrary.vue') },
    { path: '/analysis', component: () => import('./views/AnalysisBoard.vue') },
    { path: '/settings', component: () => import('./views/SettingsView.vue') },
  ],
})

createApp({ render: () => h(App) }).use(router).use(naive).mount('#app')

window.addEventListener('unhandledrejection', (e) => {
  toast(`出错了:${e.reason?.message ?? '未知错误'}`)
})
