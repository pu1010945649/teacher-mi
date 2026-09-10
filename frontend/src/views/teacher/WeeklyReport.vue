<template>
  <el-card>
    <div class="toolbar">
      <el-date-picker v-model="weekDate" type="date" placeholder="选择任一日期，自动定位所在周"
                      value-format="YYYY-MM-DD" :clearable="false"
                      :style="{ width: isMobile ? '100%' : '220px' }" />
      <el-select v-model="studentId" filterable placeholder="选择学生"
                 :style="{ width: isMobile ? '100%' : '200px' }">
        <el-option v-for="s in students" :key="s.id"
                   :label="`${s.real_name || s.username}（${s.class_name || '未分班'}）`" :value="s.id" />
      </el-select>
      <el-button type="success" :loading="generating" @click="generate">
        AI 生成周报草稿
      </el-button>
      <span class="hint">汇集所选学生本周的作业批改与课堂反馈，生成后编辑确认再发送</span>
    </div>

    <!-- 手机端卡片列表 -->
    <template v-if="isMobile">
      <el-empty v-if="!list.length" description="暂无周报，选择学生后点击上方按钮生成" />
      <el-card v-for="row in list" :key="row.id" class="m-card" shadow="never">
        <div class="m-head">
          <b>{{ row.student_name }} · {{ weekLabel(row.week_start) }}</b>
          <el-tag :type="row.status === 'sent' ? 'success' : 'warning'" size="small">
            {{ row.status === 'sent' ? '已发送' : '草稿' }}
          </el-tag>
        </div>
        <p class="m-title">{{ row.title }}</p>
        <p class="m-content">{{ row.content }}</p>
        <p v-if="row.status === 'sent'" class="m-meta">发送时间：{{ row.sent_at?.slice(0, 16).replace('T', ' ') }}</p>
        <div class="m-ops">
          <el-button v-if="row.status === 'draft'" size="small" type="primary" plain @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.status === 'draft'" size="small" type="success" plain
                     @click="sendReport(row)">发送给学生</el-button>
          <el-popconfirm title="删除该周报？" @confirm="removeReport(row)">
            <template #reference>
              <el-button size="small" type="danger" plain>删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </el-card>
    </template>

    <!-- 桌面端表格 -->
    <el-table v-else :data="list" border stripe>
      <el-table-column prop="student_name" label="学生" width="110" />
      <el-table-column label="所属周" width="130">
        <template #default="{ row }">{{ weekLabel(row.week_start) }}</template>
      </el-table-column>
      <el-table-column prop="title" label="周报标题" min-width="140" show-overflow-tooltip />
      <el-table-column prop="content" label="周报内容" min-width="240" show-overflow-tooltip />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'sent' ? 'success' : 'warning'">
            {{ row.status === 'sent' ? '已发送' : '草稿' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.status === 'draft'" link type="success"
                     @click="sendReport(row)">发送给学生</el-button>
          <span v-else class="hint">{{ row.sent_at?.slice(0, 16).replace('T', ' ') }}</span>
          <el-popconfirm title="删除该周报？" @confirm="removeReport(row)">
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑周报草稿 -->
    <el-dialog v-model="edit.visible" title="编辑周报" :width="isMobile ? '96%' : '680px'">
      <el-form label-width="80px">
        <el-form-item label="周报标题">
          <el-input v-model="edit.form.title" maxlength="100" />
        </el-form-item>
        <el-form-item label="周报内容">
          <el-input v-model="edit.form.content" type="textarea" :rows="12" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="edit.visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'
import { useRealtime } from '../../realtime'
import { useIsMobile } from '../../composables/useIsMobile'
import { ensureAiReady } from '../../composables/useAiReady'

const { isMobile } = useIsMobile()
const list = ref([])
const students = ref([])
const weekDate = ref(new Date().toISOString().slice(0, 10))
const studentId = ref(null)
const generating = ref(false)
const saving = ref(false)
const edit = reactive({ visible: false, form: { id: 0, title: '', content: '' } })

const monday = computed(() => {
  const d = new Date(`${weekDate.value}T00:00:00`)
  const day = (d.getDay() + 6) % 7  // 周一为 0
  d.setDate(d.getDate() - day)
  return d.toISOString().slice(0, 10)
})

function weekLabel(ws) {
  const start = new Date(`${ws}T00:00:00`)
  const end = new Date(start)
  end.setDate(end.getDate() + 6)
  const f = d => `${d.getMonth() + 1}-${d.getDate()}`
  return `${f(start)} ~ ${f(end)}`
}

async function load() {
  list.value = await api.get('/weekly-reports')
  students.value = await api.get('/students')
}

async function generate() {
  if (!studentId.value) return ElMessage.warning('请选择学生')
  // 统一 AI 前置校验（useAiReady）
  if (!(await ensureAiReady())) return
  generating.value = true
  try {
    await api.post('/weekly-reports/generate', {
      student_id: studentId.value,
      week_start: monday.value,
    })
    ElMessage.success('周报草稿已生成，请编辑确认后发送')
    load()
  } finally {
    generating.value = false
  }
}

function openEdit(row) {
  edit.form = { id: row.id, title: row.title, content: row.content }
  edit.visible = true
}

async function saveEdit() {
  if (!edit.form.title.trim() || !edit.form.content.trim()) {
    ElMessage.warning('标题和内容不能为空')
    return
  }
  saving.value = true
  try {
    await api.put(`/weekly-reports/${edit.form.id}`, {
      title: edit.form.title, content: edit.form.content,
    })
    ElMessage.success('已保存')
    edit.visible = false
    load()
  } finally {
    saving.value = false
  }
}

async function sendReport(row) {
  await api.post(`/weekly-reports/${row.id}/send`)
  ElMessage.success('已发送，学生可在「我的消息」中查看')
  load()
}

async function removeReport(row) {
  await api.delete(`/weekly-reports/${row.id}`)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
// 周报多端同步 → 自动刷新
useRealtime(['message'], load)
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.hint { color: #999; font-size: 12px; }
.m-card { margin-bottom: 12px; }
.m-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.m-title { color: #333; font-weight: 600; font-size: 14px; margin: 8px 0 4px; }
.m-content {
  color: #555;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: pre-wrap;
}
.m-meta { color: #999; font-size: 12px; margin: 6px 0 0; }
.m-ops { display: flex; gap: 8px; margin-top: 8px; }
</style>
