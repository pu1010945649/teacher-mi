<template>
  <div v-if="activeCount" class="monitor" :class="{ mobile: isMobile }">
    <el-popover placement="top-end" :width="isMobile ? 300 : 380" trigger="click">
      <template #reference>
        <div class="pill">
          <el-icon class="spin"><Loading /></el-icon>
          <span>{{ runningCount }} 生成中<template v-if="pendingCount"> · {{ pendingCount }} 排队</template><template v-if="generatedCount"> · {{ generatedCount }} 待确认</template></span>
        </div>
      </template>

      <div class="panel">
        <div class="panel-head">
          <b>AI 练习生成任务</b>
          <span class="setting">
            并发数
            <el-input-number v-model="concurrency" size="small" :min="1" :max="10"
                             style="width: 90px" @change="saveConcurrency" />
          </span>
        </div>

        <div v-for="t in visibleTasks" :key="t.id" class="task-row">
          <el-tag size="small" :type="statusType(t.status)">{{ statusText(t.status) }}</el-tag>
          <span class="t-name">{{ t.student_name }}</span>
          <span class="t-time">{{ shortTime(t.finished_at || t.created_at) }}</span>
          <el-tooltip v-if="t.error" :content="t.error" placement="top">
            <el-icon class="t-error"><WarningFilled /></el-icon>
          </el-tooltip>
          <el-button v-if="t.status === 'pending'" link size="small" type="danger"
                     @click="cancel(t)">取消</el-button>
        </div>

        <div class="panel-foot">
          <el-button link size="small" type="primary" @click="goWorksheets">查看已生成的练习</el-button>
        </div>
      </div>
    </el-popover>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, WarningFilled } from '@element-plus/icons-vue'
import api from '../api'
import { useIsMobile } from '../composables/useIsMobile'

const { isMobile } = useIsMobile()
const router = useRouter()
const tasks = ref([])
const concurrency = ref(2)
let timer = null

const runningCount = computed(() => tasks.value.filter(t => t.status === 'running').length)
const pendingCount = computed(() => tasks.value.filter(t => t.status === 'pending').length)
const activeCount = computed(() => runningCount.value + pendingCount.value)
// 弹出面板显示活动任务 + 待确认练习 + 最近 2 分钟内完成的任务
const visibleTasks = computed(() => {
  const cutoff = Date.now() - 2 * 60 * 1000
  const fresh = ts => ts && new Date(ts.replace('T', ' ')).getTime() > cutoff
  return tasks.value.filter(t =>
    ['pending', 'running', 'generated'].includes(t.status)
    || ['done', 'failed', 'rejected'].includes(t.status) && fresh(t.finished_at))
})

function statusText(s) {
  return {
    pending: '排队中', running: '生成中', generated: '待确认',
    done: '已下发', failed: '失败', canceled: '已取消', rejected: '已驳回',
  }[s] || s
}
function statusType(s) {
  return {
    pending: 'info', running: 'primary', generated: 'warning',
    done: 'success', failed: 'danger', canceled: 'info', rejected: 'info',
  }[s] || 'info'
}
function shortTime(s) {
  return s ? s.replace('T', ' ').slice(5, 16) : ''
}

async function refresh() {
  try {
    const all = await api.get('/worksheet-tasks', { params: { limit: 20 } })
    // 活动任务优先展示；全部完成时保留最近任务一段时间再隐藏
    tasks.value = all
  } catch { /* 未登录等场景忽略 */ }
}

async function saveConcurrency(v) {
  const r = await api.put('/worksheet-tasks/settings', { concurrency: v })
  concurrency.value = r.concurrency
  ElMessage.success(`并发数已设为 ${r.concurrency}`)
}

async function cancel(t) {
  await api.post(`/worksheet-tasks/${t.id}/cancel`)
  refresh()
}

function goAssignments() {
  router.push('/teacher/assignments')
}

onMounted(async () => {
  try {
    const r = await api.get('/worksheet-tasks/settings')
    concurrency.value = r.concurrency
  } catch { /* ignore */ }
  refresh()
  timer = setInterval(refresh, 3000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.monitor {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2000;
}
.monitor.mobile { right: 12px; bottom: 12px; }
.pill {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #409eff;
  color: #fff;
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
}
.spin { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.setting { font-size: 12px; color: #666; display: flex; align-items: center; gap: 6px; }
.task-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px solid #f5f5f5;
  font-size: 13px;
}
.t-name { flex: 1; }
.t-time { color: #999; font-size: 12px; }
.t-error { color: #e6a23c; }
.panel-foot { text-align: right; margin-top: 8px; }
</style>
