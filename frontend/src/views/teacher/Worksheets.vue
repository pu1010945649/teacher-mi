<template>
  <el-card>
    <div class="toolbar">
      <el-select v-model="studentIds" multiple collapse-tags collapse-tags-tooltip
                 placeholder="选择学生（可多选）" filterable style="width: 320px">
        <el-option v-for="s in students" :key="s.id"
                   :label="s.real_name || s.username" :value="s.id" />
      </el-select>
      <el-input v-model="focus" placeholder="关注点（可选，如：口算能力、单位换算）"
                style="width: 260px" clearable />
      <el-button type="success" :loading="submitting" @click="generate">
        提交生成任务（后台执行）
      </el-button>
    </div>

    <!-- 单选学生时可勾选参考哪些作业反馈 -->
    <div v-if="studentIds.length === 1" class="fb-panel">
      <div class="fb-title">
        参考作业反馈（{{ selection.length || '全部' }}/{{ submissions.length || 0 }}）
        <el-button link size="small" type="primary" @click="toggleAll">
          {{ allSelected ? '取消全选' : '全选' }}
        </el-button>
      </div>
      <el-checkbox-group v-if="submissions.length" v-model="selection" class="fb-list">
        <el-checkbox v-for="s in submissions" :key="s.id" :value="s.id" class="fb-item">
          <span class="fb-label">
            《{{ s.assignment_title }}》
            <el-tag size="small" :type="s.status === 'graded' ? 'success' : 'warning'">
              {{ s.status === 'graded' ? `已批改 ${s.feedback?.score ?? ''}分` : '待批改' }}
            </el-tag>
            <span v-if="s.feedback?.content" class="fb-excerpt">评语：{{ s.feedback.content.slice(0, 40) }}</span>
          </span>
        </el-checkbox>
      </el-checkbox-group>
      <div v-else class="fb-empty">该学生暂无作业提交记录，将无法生成有针对性的练习</div>
    </div>
    <el-alert v-else-if="studentIds.length > 1"
              :title="`将为 ${studentIds.length} 名学生分别创建独立生成任务（每人使用其全部作业反馈）`"
              type="info" :closable="false" style="margin-bottom: 14px" />

    <el-table :data="list" border stripe>
      <el-table-column prop="student_name" label="学生" width="120" />
      <el-table-column prop="title" label="练习标题" width="220" />
      <el-table-column prop="content" label="内容预览" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="生成时间" width="170">
        <template #default="{ row }">{{ row.created_at?.replace('T', ' ') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button link type="primary" @click="preview(row)">预览</el-button>
          <el-button link type="primary" @click="download(row)">PDF</el-button>
          <template v-if="row.status === 'pending'">
            <el-popconfirm title="确认内容无误并发送给学生？" width="220" @confirm="publish(row)">
              <template #reference>
                <el-button link type="success">确认发送</el-button>
              </template>
            </el-popconfirm>
            <el-popconfirm title="驳回该生成结果？" width="200" @confirm="reject(row)">
              <template #reference>
                <el-button link type="danger">驳回</el-button>
              </template>
            </el-popconfirm>
          </template>
          <el-tag v-else-if="row.status === 'published'" size="small" type="success" effect="plain">
            已发至作业
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="previewRow.title" width="680px">
      <pre class="ws-content">{{ previewRow.content }}</pre>
      <template #footer>
        <el-button type="primary" @click="download(previewRow)">下载 PDF</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api, { authUrl } from '../../api'

const students = ref([])
const submissions = ref([])
const list = ref([])
const studentIds = ref([])
const selection = ref([])
const focus = ref('')
const submitting = ref(false)
const dialogVisible = ref(false)
const previewRow = ref({})

const allSelected = computed(() =>
  submissions.value.length > 0 && selection.value.length === submissions.value.length)

// 单选学生时加载其提交记录
watch(() => studentIds.value, async ids => {
  if (ids.length === 1) {
    submissions.value = await api.get(`/submissions/by-student/${ids[0]}`)
    selection.value = submissions.value.map(s => s.id)  // 默认全选
  } else {
    submissions.value = []
    selection.value = []
  }
})

function toggleAll() {
  selection.value = allSelected.value ? [] : submissions.value.map(s => s.id)
}

async function load() {
  students.value = await api.get('/students')
  list.value = await api.get('/worksheets')
}

async function generate() {
  if (!studentIds.value.length) {
    ElMessage.warning('请先选择学生')
    return
  }
  submitting.value = true
  try {
    const body = { student_ids: studentIds.value, focus: focus.value }
    if (studentIds.value.length === 1 && selection.value.length) {
      body.submission_ids = { [String(studentIds.value[0])]: selection.value }
    }
    const tasks = await api.post('/worksheet-tasks', body)
    ElMessage.success(`已创建 ${tasks.length} 个后台生成任务，完成后自动出现在列表中`)
  } finally {
    submitting.value = false
  }
}

function preview(row) {
  previewRow.value = row
  dialogVisible.value = true
}

function statusText(s) {
  return { pending: '待确认', published: '已发送', rejected: '已驳回' }[s] || s
}
function statusType(s) {
  return { pending: 'warning', published: 'success', rejected: 'danger' }[s] || 'info'
}

async function publish(row) {
  await api.post(`/worksheets/${row.id}/publish`)
  ElMessage.success('已发送到学生的作业列表')
  list.value = await api.get('/worksheets')
}

async function reject(row) {
  await api.post(`/worksheets/${row.id}/reject`)
  ElMessage.info('已驳回')
  list.value = await api.get('/worksheets')
}

function download(row) {
  window.open(authUrl(`/api/worksheets/${row.id}/pdf`))
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.fb-panel {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 14px;
  max-height: 220px;
  overflow: auto;
}
.fb-title { font-weight: 600; margin-bottom: 6px; }
.fb-list { display: flex; flex-direction: column; }
.fb-item { height: 28px; margin-right: 0; }
.fb-label { font-size: 13px; }
.fb-excerpt { color: #999; margin-left: 8px; }
.fb-empty { color: #999; font-size: 13px; padding: 6px 0; }
.ws-content {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 6px;
  white-space: pre-wrap;
  max-height: 50vh;
  overflow: auto;
}
</style>
