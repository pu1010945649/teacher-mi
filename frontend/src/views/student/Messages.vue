<template>
  <el-card>
    <template v-if="!isMobile">
      <h4 class="page-title">我的消息</h4>
    </template>
    <el-empty v-if="!list.length" description="暂无消息，老师发送学习周报后会在这里出现" />
    <el-card v-for="r in list" :key="r.id" shadow="never" class="msg-card">
      <div class="msg-head">
        <b class="msg-title">{{ r.title }}</b>
        <span class="msg-time">{{ r.sent_at?.slice(0, 16).replace('T', ' ') }}</span>
      </div>
      <div class="msg-week">所属周：{{ weekLabel(r.week_start) }}</div>
      <pre class="msg-content">{{ r.content }}</pre>
    </el-card>
  </el-card>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../../api'
import { useRealtime } from '../../realtime'
import { useIsMobile } from '../../composables/useIsMobile'

const { isMobile } = useIsMobile()
const list = ref([])

function weekLabel(ws) {
  const start = new Date(`${ws}T00:00:00`)
  const end = new Date(start)
  end.setDate(end.getDate() + 6)
  const f = d => `${d.getMonth() + 1}-${d.getDate()}`
  return `${f(start)} ~ ${f(end)}`
}

async function load() {
  list.value = await api.get('/weekly-reports/my')
}

onMounted(load)
// 老师发送新周报（多端同步）→ 自动刷新
useRealtime(['message'], load)
</script>

<style scoped>
.page-title { margin: 0 0 12px; }
.msg-card { margin-bottom: 12px; }
.msg-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.msg-title { font-size: 15px; }
.msg-time { color: #999; font-size: 12px; white-space: nowrap; }
.msg-week { color: #909399; font-size: 12px; margin-top: 4px; }
.msg-content {
  margin: 10px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.8;
  color: #444;
}
</style>
