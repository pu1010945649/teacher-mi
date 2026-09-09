<template>
  <el-card>
    <div class="toolbar">
      <el-button type="success" @click="openDialog()">布置新作业</el-button>
    </div>
    <el-table :data="list" border stripe>
      <el-table-column prop="title" label="作业标题" width="200" />
      <el-table-column prop="description" label="作业要求" show-overflow-tooltip />
      <el-table-column label="下发范围" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.assigned_to_all" type="success">全体学生</el-tag>
          <el-tag v-else type="warning">{{ row.target_count }} 名学生</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="附件" width="160">
        <template #default="{ row }">
          <el-link v-if="row.filename" type="primary" @click="downloadAttachment(row)">
            {{ row.filename }}
          </el-link>
          <span v-else>无</span>
        </template>
      </el-table-column>
      <el-table-column prop="deadline" label="截止时间" width="160">
        <template #default="{ row }">{{ row.deadline?.replace('T', ' ') || '不限' }}</template>
      </el-table-column>
      <el-table-column prop="submission_count" label="已提交" width="80" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="$router.push({ path: '/teacher/grading', query: { id: row.id } })">
            查看提交
          </el-button>
          <el-popconfirm title="删除作业将同时删除其提交记录，确定？" @confirm="remove(row)">
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog.visible" title="布置作业" width="640px">
      <el-form :model="dialog.form" label-width="90px">
        <el-form-item label="标题"><el-input v-model="dialog.form.title" /></el-form-item>
        <el-form-item label="下发对象">
          <el-select v-model="dialog.form.studentIds" multiple collapse-tags collapse-tags-tooltip
                     placeholder="不选 = 下发给全体学生" style="width: 100%">
            <el-option v-for="s in students" :key="s.id"
                       :label="`${s.real_name || s.username}（${s.class_name || '未分班'}）`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="作业要求">
          <div style="width: 100%">
            <el-input v-model="dialog.form.description" type="textarea" :rows="5" />
            <div style="margin-top: 6px">
              <el-button size="small" type="success" :loading="aiLoading" @click="aiGenerate">
                AI 综合反馈生成
              </el-button>
              <span class="hint">根据所选学生的学习反馈综合生成作业要求</span>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="作业附件">
          <input type="file" @change="onFileChange" />
        </el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker v-model="dialog.form.deadline" type="datetime" placeholder="可不设置"
                          value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">发布</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { authUrl } from '../../api'

const list = ref([])
const students = ref([])
const dialog = reactive({
  visible: false,
  form: { title: '', description: '', deadline: null, studentIds: [] },
  file: null,
})
const aiLoading = ref(false)
const saving = ref(false)

async function load() {
  list.value = await api.get('/assignments')
  students.value = await api.get('/students')
}

function openDialog() {
  dialog.form = { title: '', description: '', deadline: null, studentIds: [] }
  dialog.file = null
  dialog.visible = true
}

function onFileChange(e) {
  dialog.file = e.target.files[0] || null
}

async function aiGenerate() {
  aiLoading.value = true
  try {
    const data = await api.post('/assignments/generate-description', {
      student_ids: dialog.form.studentIds,
      hint: dialog.form.title,
    })
    dialog.form.description = data.description
    ElMessage.success('已根据学生反馈生成作业要求，可修改后发布')
  } finally {
    aiLoading.value = false
  }
}

async function save() {
  if (!dialog.form.title) {
    ElMessage.warning('请填写作业标题')
    return
  }
  saving.value = true
  try {
    const fd = new FormData()
    fd.append('title', dialog.form.title)
    fd.append('description', dialog.form.description)
    if (dialog.form.deadline) fd.append('deadline', dialog.form.deadline)
    fd.append('student_ids', dialog.form.studentIds.join(','))
    if (dialog.file) fd.append('file', dialog.file)
    await api.post('/assignments', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('已发布')
    dialog.visible = false
    load()
  } finally {
    saving.value = false
  }
}

function downloadAttachment(row) {
  const a = document.createElement('a')
  a.href = authUrl(`/api/assignments/${row.id}/file`)
  a.download = row.filename
  a.click()
}

async function remove(row) {
  await api.delete(`/assignments/${row.id}`)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 14px; }
.hint { margin-left: 8px; color: #999; font-size: 12px; }
</style>
