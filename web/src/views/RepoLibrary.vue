<!-- 仓库库:列表筛选、仓库详情(分类/锁定/标签/排除/重新分析/版本列表,US-02/03/08) -->
<script setup>
import { onMounted, ref } from 'vue'

const repos = ref([])
const q = ref('')
const filter = ref('active')
const detail = ref(null)

async function load() {
  repos.value = await (await fetch(`/api/repos?filter=${filter.value}&q=${encodeURIComponent(q.value)}`)).json()
}

async function open(id) {
  detail.value = await (await fetch(`/api/repos/${id}`)).json()
}

async function toggleLock() {
  const c = detail.value.classification
  await fetch(`/api/repos/${detail.value.repo.id}/lock`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ locked: !c.locked }) })
  await open(detail.value.repo.id)
}

async function addTag(e) {
  const name = e.target.value.trim()
  e.target.value = ''
  if (!name) return
  await fetch(`/api/repos/${detail.value.repo.id}/tags`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
  await open(detail.value.repo.id)
  await load()
}

async function delTag(name) {
  await fetch(`/api/repos/${detail.value.repo.id}/tags/${encodeURIComponent(name)}`, { method: 'DELETE' })
  await open(detail.value.repo.id)
}

async function toggleExclude() {
  await fetch(`/api/repos/${detail.value.repo.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ excluded: !detail.value.repo.excluded }) })
  await open(detail.value.repo.id)
  await load()
}

async function analyze() {
  await fetch(`/api/repos/${detail.value.repo.id}/analyze`, { method: 'POST' })
  await open(detail.value.repo.id)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <h1>仓库库</h1>
    <div class="bar">
      <select v-model="filter" @change="load">
        <option value="active">在库</option>
        <option value="all">全部</option>
        <option value="unstarred">已取消收藏</option>
      </select>
      <input v-model="q" placeholder="名称/描述/标签" @keydown.enter="load" />
      <button @click="load">筛选</button>
    </div>

    <ul class="list">
      <li v-for="r in repos" :key="r.id" @click="open(r.id)">
        <div>
          <b>{{ r.full_name }}</b>
          <span v-if="r.type" class="chip">{{ r.type }} · {{ r.confidence }}</span>
          <span v-if="r.locked" class="chip lock">已锁定</span>
          <span v-if="r.excluded" class="chip">已排除</span>
        </div>
        <p class="desc">{{ r.description }}</p>
      </li>
    </ul>

    <div v-if="detail" class="drawer" @click.self="detail = null">
      <div class="panel">
        <h2>{{ detail.repo.full_name }}</h2>
        <p class="desc">{{ detail.repo.description }}</p>
        <div v-if="detail.classification" class="cls">
          <span class="chip">{{ detail.classification.type }} · 置信 {{ detail.classification.confidence }}</span>
          <p class="reason">{{ detail.classification.reason }}</p>
          <button @click="toggleLock">{{ detail.classification.locked ? '解锁分类' : '锁定分类' }}</button>
        </div>
        <p v-else>尚未分类</p>
        <div class="history" v-if="detail.history.length">
          <h3>修正记录</h3>
          <p v-for="h in detail.history" :key="h.created_at">{{ h.old_type }} → {{ h.new_type }}:{{ h.reason }}</p>
        </div>
        <div class="tags">
          <span v-for="t in detail.tags" :key="t" class="chip" @click="delTag(t)">{{ t }} ×</span>
          <input placeholder="+ 标签,回车添加" @keydown.enter="addTag" />
        </div>
        <div class="actions">
          <button @click="analyze">{{ detail.versions.length ? '重新分析' : '开始分析' }}</button>
          <button @click="toggleExclude">{{ detail.repo.excluded ? '取消排除' : '排除(不再自动分析)' }}</button>
        </div>
        <div v-if="detail.versions.length" class="versions">
          <h3>报告版本</h3>
          <p v-for="v in detail.versions" :key="v.id">
            <RouterLink :to="`/repos/${detail.repo.id}/report/${v.id}`">v{{ v.version_no }} · {{ v.created_at }}</RouterLink>
            <a :href="`/api/reports/${v.id}/export`">导出</a>
          </p>
        </div>
        <div v-if="detail.knowledge_points.length" class="kps">
          <h3>知识点</h3>
          <p v-for="k in detail.knowledge_points" :key="k.id">{{ k.statement }}<span v-if="k.human_edited" class="chip">人工修订</span></p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bar { display: flex; gap: 8px; margin: 12px 0; }
.list { list-style: none; padding: 0; max-width: var(--sd-width); }
.list li { padding: 12px 8px; border-bottom: 1px solid var(--sd-border); cursor: pointer; }
.list li:hover { background: var(--sd-accent-soft); }
.desc { color: var(--sd-text-2); margin: 4px 0 0; font-size: 0.9em; }
.chip { display: inline-block; font-size: 0.78em; border: 1px solid var(--sd-border); border-radius: 10px; padding: 1px 8px; margin-left: 8px; color: var(--sd-text-2); }
.chip.lock { color: var(--sd-accent); border-color: var(--sd-accent); }
.drawer { position: fixed; inset: 0; background: #0009; display: flex; justify-content: flex-end; z-index: 20; }
.panel { width: min(520px, 94vw); background: var(--sd-surface); padding: 20px; overflow-y: auto; }
.reason { color: var(--sd-text-2); font-size: 0.9em; }
.tags input { width: 60%; margin-top: 6px; }
.actions { display: flex; gap: 8px; margin: 16px 0; }
h3 { font-size: 0.95em; color: var(--sd-text-2); border-top: 1px solid var(--sd-border); padding-top: 12px; }
</style>
