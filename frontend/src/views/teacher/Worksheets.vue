<template>
  <el-card>
    <div class="toolbar">
      <el-select v-model="studentId" placeholder="选择学生" style="width: 200px" filterable>
        <el-option v-for="s in students" :key="s.id" :label="s.real_name || s.username" :value="s.id" />
      </el-select>
      <el-input v-model="focus" placeholder="关注点（可选，如：口算能力、单位换算）" style="width: 280px" clearable />
      <el-button type="success" :loading="generating" @click="generate">AI 生成个性化练习</el-button>
    </div>

    <el-table :data="list" border stripe>
      <el-table-column prop="student_name" label="学生" width="120" />
      <el-table-column prop="title" label="练习标题" width="220" />
      <el-table-column prop="content" label="内容预览" show-overflow-tooltip />
      <el-table-column prop="created_at" label="生成时间" width="170">
        <template #default="{ row }">{{ row.created_at?.replace('T', ' ') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="preview(row)">预览</el-button>
          <el-button link type="primary" @click="download(row)">下载 PDF</el-button>
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
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { authUrl } from '../../api'

const students = ref([])
const list = ref([])
const studentId = ref(null)
const focus = ref('')
const generating = ref(false)
const dialogVisible = ref(false)
const previewRow = ref({})

async function load() {
  students.value = await api.get('/students')
  list.value = await api.get('/worksheets')
}

async function generate() {
  if (!studentId.value) {
    ElMessage.warning('请先选择学生')
    return
  }
  generating.value = true
  try {
    await api.post('/worksheets/generate', { student_id: studentId.value, focus: focus.value })
    ElMessage.success('练习已生成')
    load()
  } finally {
    generating.value = false
  }
}

function preview(row) {
  previewRow.value = row
  dialogVisible.value = true
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
}
.ws-content {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 6px;
  white-space: pre-wrap;
  max-height: 50vh;
  overflow: auto;
}
</style>
