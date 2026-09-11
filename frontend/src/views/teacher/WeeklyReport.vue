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
      <el-button type="primary" plain @click="openUpload">上传周报文件</el-button>
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
        <p class="m-meta">科目：{{ row.subject || '未设置' }}</p>
        <p class="m-title">{{ row.title }}</p>
        <p v-if="row.file_name" class="m-file">
          <el-icon><Document /></el-icon>{{ row.file_name }}
        </p>
        <p class="m-content">{{ row.content || '（文件周报，无文字内容）' }}</p>
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
      <el-table-column label="科目" width="90">
        <template #default="{ row }">{{ row.subject || '—' }}</template>
      </el-table-column>
      <el-table-column label="所属周" width="130">
        <template #default="{ row }">{{ weekLabel(row.week_start) }}</template>
      </el-table-column>
      <el-table-column label="周报标题" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.title }}
          <el-tag v-if="row.file_name" size="small" effect="plain" class="file-tag">
            <el-icon style="vertical-align:-2px;"><Document /></el-icon>
            {{ row.file_name }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="content" label="周报内容" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">{{ row.content || '（文件周报，无文字内容）' }}</template>
      </el-table-column>
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

    <!-- 上传周报文件 -->
    <el-dialog v-model="upload.visible" title="上传周报文件" :width="isMobile ? '96%' : '560px'">
      <el-form label-width="80px">
        <el-form-item label="所属周">
          <el-date-picker v-model="upload.week" type="date" value-format="YYYY-MM-DD"
                          :clearable="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="学生">
          <el-select v-model="upload.studentId" filterable placeholder="选择学生" style="width: 100%">
            <el-option v-for="s in students" :key="s.id"
                       :label="`${s.real_name || s.username}（${s.class_name || '未分班'}）`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="周报标题">
          <el-input v-model="upload.title" maxlength="100" placeholder="留空默认为「XX 学习周报」" />
        </el-form-item>
        <el-form-item label="周报文件">
          <input ref="fileInput" type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg" @change="onFileChange" />
          <div class="hint" style="margin-top:4px;">支持 pdf/word/excel/图片，20MB 以内；同一学生同一周重复上传将覆盖</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="upload.visible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!upload.file" @click="submitUpload">上传</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document } from '@element-plus/icons-vue'
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
const upload = reactive({ visible: false, week: '', studentId: null, title: '', file: null })
const uploading = ref(false)
const fileInput = ref(null)

function weekLabel(ws) {
  const start = new Date(`${ws}T00:00:00`)
  const end = new Date(start)
  end.setDate(end.getDate() + 6)
  const f = d => `${d.getMonth() + 1}-${d.getDate()}`
  return `${f(start)} ~ ${f(end)}`
}

// 任一日期 → 所在周的周一
function mondayOf(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`)
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return d.toISOString().slice(0, 10)
}

const monday = computed(() => mondayOf(weekDate.value))
const uploadMonday = computed(() => mondayOf(upload.week))

function openUpload() {
  upload.week = weekDate.value
  upload.studentId = studentId.value
  upload.title = ''
  upload.file = null
  upload.visible = true
}

function onFileChange(e) {
  upload.file = e.target.files[0] || null
}

async function submitUpload() {
  if (!upload.studentId) return ElMessage.warning('请选择学生')
  if (!upload.file) return ElMessage.warning('请选择文件')
  if (upload.file.size > 20 * 1024 * 1024) return ElMessage.warning('文件大小不能超过 20MB')
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('student_id', upload.studentId)
    fd.append('week_start', uploadMonday.value)
    fd.append('title', upload.title)
    fd.append('file', upload.file)
    await api.post('/weekly-reports/upload', fd)
    ElMessage.success('已上传，请确认后发送给学生')
    upload.visible = false
    load()
  } finally {
    uploading.value = false
  }
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
.m-file {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #409eff;
  font-size: 12px;
  margin: 4px 0 0;
  word-break: break-all;
}
.file-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  max-width: 200px;
  margin-left: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
}
</style>
