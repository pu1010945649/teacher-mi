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
      <div class="msg-week">
        所属周：{{ weekLabel(r.week_start) }}
        <el-tag v-if="r.subject" size="small" effect="plain" class="msg-tag">{{ r.subject }}</el-tag>
        <el-tag v-if="r.teacher_name" size="small" effect="plain" type="info" class="msg-tag">{{ r.teacher_name }}老师推送</el-tag>
      </div>
      <pre v-if="r.content" class="msg-content">{{ r.content }}</pre>
      <div v-if="r.file_name" class="msg-file">
        <span class="file-name">
          <el-icon><Document /></el-icon>{{ r.file_name }}
        </span>
        <el-button size="small" type="primary" plain @click="viewFile(r)">在线查看</el-button>
        <el-button size="small" plain @click="downloadFile(r)">下载</el-button>
      </div>
    </el-card>
  </el-card>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Document } from '@element-plus/icons-vue'
import api, { authUrl } from '../../api'
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

function viewFile(r) {
  window.open(authUrl(`/api/weekly-reports/${r.id}/file`))
}

function downloadFile(r) {
  const a = document.createElement('a')
  a.href = authUrl(`/api/weekly-reports/${r.id}/file`) + '&download=1'
  a.click()
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
.msg-week { color: #909399; font-size: 12px; margin-top: 4px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.msg-tag { flex-shrink: 0; }
.msg-content {
  margin: 10px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.8;
  color: #444;
}
.msg-file {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.file-name {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #409eff;
  font-size: 13px;
  word-break: break-all;
}
</style>
