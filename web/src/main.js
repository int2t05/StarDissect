// 入口:装配路由四区(UX-21)+ 组件库注册(UX-60)
import { createApp, h } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import naive from 'naive-ui'

import App from './App.vue'
import './styles/tokens.css'
import AnalysisBoard from './views/AnalysisBoard.vue'
import ReadingHome from './views/ReadingHome.vue'
import RepoLibrary from './views/RepoLibrary.vue'
import ReportView from './views/ReportView.vue'
import SettingsView from './views/SettingsView.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/reading' },
    { path: '/reading', component: ReadingHome },
    { path: '/repos', component: RepoLibrary },
    { path: '/repos/:id/report/:vid', component: ReportView },
    { path: '/analysis', component: AnalysisBoard },
    { path: '/settings', component: SettingsView },
  ],
})

createApp({ render: () => h(App) }).use(router).use(naive).mount('#app')

window.addEventListener('unhandledrejection', (e) => {
  import('./api').then(({ toast }) => toast(`出错了:${e.reason?.message ?? '未知错误'}`))
})
