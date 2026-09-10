<template>
  <el-card>
    <div class="toolbar">
      <el-radio-group v-model="mode" size="small" @change="onModeChange">
        <el-radio-button value="assignment">按作业</el-radio-button>
        <el-radio-button value="student">按学生</el-radio-button>
      </el-radio-group>

      <template v-if="mode === 'assignment'">
        <el-select v-model="assignmentId" placeholder="请选择作业" filterable
                   style="width: 260px" @change="load">
          <el-option v-for="a in assignments" :key="a.id" :label="a.title" :value="a.id" />
        </el-select>
        <el-select v-model="studentId" placeholder="全部学生" clearable filterable
                   style="width: 180px" @change="load">
          <el-option v-for="s in students" :key="s.id"
                     :label="s.real_name || s.username" :value="s.id" />
        </el-select>
      </template>

      <template v-else>
        <el-select v-model="studentId" placeholder="请选择学生" filterable
                   style="width: 200px" @change="load">
          <el-option v-for="s in students" :key="s.id"
                     :label="s.real_name || s.username" :value="s.id" />
        </el-select>
        <el-select v-model="assignmentId" placeholder="全部作业" clearable filterable
                   style="width: 240px" @change="load">
          <el-option v-for="a in assignments" :key="a.id" :label="a.title" :value="a.id" />
        </el-select>
      </template>
    </div>

    <!-- 手机端卡片列表 -->
    <template v-if="isMobile">
      <el-empty v-if="!list.length" description="选择作业或学生后查看提交记录" />
      <el-card v-for="row in list" :key="row.id" class="m-card" shadow="never">
        <div class="m-head">
          <b>{{ mode === 'student' ? row.assignment_title : row.student_name }}</b>
          <el-tag :type="statusTag(row.status).type" size="small">
            {{ statusTag(row.status).text }}<template v-if="row.attempt > 1">·第{{ row.attempt }}次</template>
          </el-tag>
        </div>
        <pre class="m-content">{{ row.content || '（无文字内容）' }}</pre>
        <p class="m-meta">
          <span>下发：{{ fmtTime(row.assigned_at) }} · 提交：{{ fmtTime(row.submitted_at) }}</span>
        </p>
        <p class="m-meta">
          <el-link v-if="row.has_file" type="primary" @click="download(row)">
            附件：{{ row.filename }}
          </el-link>
          <span v-else>无附件</span>
        </p>
        <div class="m-ops">
          <el-button size="small" type="primary" plain @click="openGrade(row)">批改</el-button>
          <el-popconfirm v-if="row.status === 'submitted' || row.status === 'graded'"
                         title="退回后学生可重新提交，老的提交会保留？"
                         width="220" @confirm="returnSubmission(row)">
            <template #reference>
              <el-button size="small" type="warning" plain>退回重交</el-button>
            </template>
          </el-popconfirm>
          <el-button v-if="row.status === 'graded'" size="small" type="success" plain
                     @click="completeSubmission(row)">已完成</el-button>
          <el-button v-if="row.has_file && isDoodleable(row.filename)" size="small" type="success"
                     plain @click="openDoodle(row)">涂鸦批改</el-button>
        </div>
      </el-card>
    </template>

    <!-- 桌面端表格 -->
    <el-table v-else :data="list" border stripe>
      <el-table-column v-if="mode === 'student'" prop="assignment_title" label="作业"
                       width="180" show-overflow-tooltip />
      <el-table-column prop="student_name" label="学生" width="120" />
      <el-table-column label="时间" width="170">
        <template #default="{ row }">
          <div class="time-line">下发：{{ fmtTime(row.assigned_at) }}</div>
          <div class="time-line">提交：{{ fmtTime(row.submitted_at) }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="content" label="提交内容" show-overflow-tooltip />
      <el-table-column label="学生附件" width="180">
        <template #default="{ row }">
          <el-link v-if="row.has_file" type="primary" @click="download(row)">
            {{ row.filename }}
          </el-link>
          <span v-else>无</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status).type">{{ statusTag(row.status).text }}</el-tag>
          <div v-if="row.attempt > 1" class="attempt">第{{ row.attempt }}次</div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button link type="primary" @click="openGrade(row)">批改</el-button>
          <el-popconfirm v-if="row.status === 'submitted' || row.status === 'graded'"
                         title="退回后学生可重新提交，老的提交会保留？"
                         width="220" @confirm="returnSubmission(row)">
            <template #reference>
              <el-button link type="warning">退回重交</el-button>
            </template>
          </el-popconfirm>
          <el-button v-if="row.status === 'graded'" link type="success"
                     @click="completeSubmission(row)">已完成</el-button>
          <el-button v-if="row.has_file && isDoodleable(row.filename)" link type="success"
                     @click="openDoodle(row)">涂鸦批改</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!list.length && (mode === 'student' ? studentId : assignmentId)"
              :description="mode === 'assignment' ? '该作业暂无提交记录' : '该学生暂无提交记录'" />

    <!-- 普通批改弹窗 -->
    <el-dialog v-model="dialog.visible" title="批改作业" :width="isMobile ? '96%' : '680px'">
      <div class="submission">
        <p><b>{{ current.student_name }}</b> 提交内容：</p>
        <pre class="content">{{ current.content || '（无文字内容）' }}</pre>
        <el-link v-if="current.has_file" type="primary" @click="download(current)">
          下载学生附件：{{ current.filename }}
        </el-link>
        <el-link v-if="current.feedback?.has_annotated_file" type="success" style="margin-left: 12px"
                 @click="downloadAnnotated(current)">
          已有批注文件：{{ current.feedback.filename }}
        </el-link>
      </div>
      <el-form label-width="90px" style="margin-top: 16px">
        <el-form-item label="分数">
          <el-input-number v-model="dialog.form.score" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="评语反馈">
          <el-input v-model="dialog.form.content" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="在线批注">
          <el-input v-model="dialog.form.annotation" type="textarea" :rows="4"
                    placeholder="可直接修改学生作业内容，或逐条添加批注（学生会看到）" />
        </el-form-item>
        <el-form-item label="批注文件">
          <div>
            <input type="file" @change="onAnnotatedChange" />
            <div class="hint">可上传批改后的文件，或用列表中的「涂鸦批改」在线标注图片 / PDF</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="success" :loading="aiLoading" @click="aiSuggest">AI 辅助批改</el-button>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" @click="save">保存反馈</el-button>
      </template>
    </el-dialog>

    <!-- 涂鸦批改弹窗 -->
    <el-dialog v-model="doodle.visible" title="在线涂鸦批改" :width="isMobile ? '98%' : '900px'"
               top="4vh" destroy-on-close>
      <DoodleCanvas v-if="doodle.visible" ref="doodleRef" :src="doodle.src" :name="doodle.row?.filename" />
      <div class="doodle-tip">涂鸦完成后点「保存批注」将生成批注图片，连同分数评语一起保存给学生</div>
      <el-form label-width="90px" style="margin-top: 10px">
        <el-form-item label="分数">
          <el-input-number v-model="doodle.form.score" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="评语反馈">
          <el-input v-model="doodle.form.content" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="doodle.visible = false">取消</el-button>
        <el-button type="primary" :loading="doodle.saving" @click="saveDoodle">保存批注</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { authUrl } from '../../api'
import { useRealtime } from '../../realtime'
import { useIsMobile } from '../../composables/useIsMobile'
import DoodleCanvas from '../../components/DoodleCanvas.vue'

const route = useRoute()
const { isMobile } = useIsMobile()
const assignments = ref([])
const students = ref([])
const mode = ref('assignment')
const assignmentId = ref(null)
const studentId = ref(null)
const list = ref([])
const current = ref({})
const doodleRef = ref(null)
const dialog = reactive({
  visible: false,
  form: { score: 80, content: '', annotation: '' },
  annotatedFile: null,
})
const doodle = reactive({
  visible: false, src: '', saving: false, row: null,
  form: { score: 80, content: '' },
})
const aiLoading = ref(false)

const DOODLE_EXT = /\.(png|jpe?g|gif|bmp|webp|pdf)$/i
function isDoodleable(name) {
  return DOODLE_EXT.test(name || '')
}

// 提交状态标签：submitted 待批改 / graded 已批改 / returned 已退回待重交
function statusTag(status) {
  return {
    submitted: { type: 'warning', text: '待批改' },
    graded: { type: 'success', text: '已批改' },
    returned: { type: 'danger', text: '已退回' },
  }[status] || { type: 'info', text: status }
}

// 时间显示：月-日 时分
function fmtTime(v) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return '—'
  const p = n => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

async function returnSubmission(row) {
  await api.post(`/submissions/${row.id}/return`)
  ElMessage.success('已退回，学生端会收到提醒并可重新提交')
  load()
}

async function loadStudents() {
  students.value = await api.get('/students')
}

async function loadAssignments() {
  assignments.value = await api.get('/assignments')
  if (route.query.id) {
    assignmentId.value = Number(route.query.id)
    mode.value = 'assignment'
    load()
  }
}

async function load() {
  if (mode.value === 'assignment') {
    if (!assignmentId.value) { list.value = []; return }
    const params = studentId.value ? `?student_id=${studentId.value}` : ''
    list.value = await api.get(`/submissions/by-assignment/${assignmentId.value}${params}`)
  } else {
    if (!studentId.value) { list.value = []; return }
    list.value = await api.get(`/submissions/by-student/${studentId.value}`)
    // 「全部作业」时按作业标题过滤
    if (assignmentId.value) {
      list.value = list.value.filter(s => s.assignment_id === assignmentId.value)
    }
  }
}

function onModeChange() {
  list.value = []
  load()
}

function openGrade(row) {
  current.value = row
  const fb = row.feedback
  dialog.form = {
    score: fb?.score ?? 80,
    content: fb?.content ?? '',
    annotation: fb?.annotation ?? '',
  }
  dialog.annotatedFile = null
  dialog.visible = true
}

function openDoodle(row) {
  doodle.row = row
  doodle.src = authUrl(`/api/submissions/${row.id}/file`)
  const fb = row.feedback
  doodle.form = { score: fb?.score ?? 80, content: fb?.content ?? '' }
  doodle.visible = true
}

async function saveDoodle() {
  doodle.saving = true
  try {
    const file = await doodleRef.value.exportFile(doodle.row.filename)
    const fd = new FormData()
    fd.append('score', doodle.form.score ?? '')
    fd.append('content', doodle.form.content)
    fd.append('annotation', '见涂鸦批注文件')
    fd.append('ai_assisted', 'false')
    if (file) fd.append('file', file)
    await api.post(`/feedback/${doodle.row.id}`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('涂鸦批注已保存')
    doodle.visible = false
    load()
  } finally {
    doodle.saving = false
  }
}

function onAnnotatedChange(e) {
  dialog.annotatedFile = e.target.files[0] || null
}

async function aiSuggest() {
  aiLoading.value = true
  try {
    const data = await api.post(`/ai/grade/${current.value.id}`)
    if (data.score != null) dialog.form.score = data.score
    if (data.comment) dialog.form.content = data.comment
    ElMessage.success('AI 建议已填入，可自行修改后保存')
  } finally {
    aiLoading.value = false
  }
}

async function save() {
  const fd = new FormData()
  fd.append('score', dialog.form.score ?? '')
  fd.append('content', dialog.form.content)
  fd.append('annotation', dialog.form.annotation)
  fd.append('ai_assisted', 'true')
  if (dialog.annotatedFile) fd.append('file', dialog.annotatedFile)
  await api.post(`/feedback/${current.value.id}`, fd,
    { headers: { 'Content-Type': 'multipart/form-data' } })
  ElMessage.success('反馈已保存')
  dialog.visible = false
  load()
}

function download(row) {
  const a = document.createElement('a')
  a.href = authUrl(`/api/submissions/${row.id}/file`)
  a.download = row.filename
  a.click()
}

function downloadAnnotated(row) {
  const a = document.createElement('a')
  a.href = authUrl(`/api/feedback/submission/${row.id}/annotated-file`)
  a.download = row.feedback.filename
  a.click()
}

onMounted(() => {
  loadStudents()
  loadAssignments()
})
// 学生提交作业、学生增删改 → 自动刷新
useRealtime(['submission', 'student'], () => {
  loadStudents()
  loadAssignments()
  load()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.content {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 6px;
  white-space: pre-wrap;
  max-height: 200px;
  overflow: auto;
}
.hint { color: #999; font-size: 12px; margin-top: 4px; }
.time-line { font-size: 12px; color: #909399; line-height: 1.6; }
.attempt { font-size: 12px; color: #999; margin-top: 2px; }
.doodle-tip { color: #999; font-size: 12px; }
.m-card { margin-bottom: 12px; }
.m-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.m-content {
  background: #f5f7fa;
  padding: 8px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
  font-size: 13px;
  color: #555;
  max-height: 120px;
  overflow: auto;
  margin: 8px 0 4px;
}
.m-meta { color: #999; font-size: 12px; margin: 4px 0; }
.m-ops { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
</style>
