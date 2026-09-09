<template>
  <el-card>
    <!-- 手机端卡片列表 -->
    <template v-if="isMobile">
      <el-empty v-if="!list.length" description="暂无作业" />
      <el-card v-for="row in list" :key="row.id" class="m-card" shadow="never">
        <div class="m-head">
          <b>{{ row.title }}</b>
          <el-tag :type="row.submitted ? 'success' : 'warning'" size="small">
            {{ row.submitted ? '已提交' : '待提交' }}
          </el-tag>
        </div>
        <p class="m-desc">{{ row.description || '（无作业要求）' }}</p>
        <p class="m-meta">截止：{{ row.deadline?.replace('T', ' ') || '不限' }}</p>
        <p v-if="row.filename" class="m-meta">
          附件：<el-link type="primary" @click="downloadAttachment(row)">{{ row.filename }}</el-link>
        </p>
        <el-button type="primary" size="small" @click="openUpload(row)">
          {{ row.submitted ? '重新提交' : '提交作业' }}
        </el-button>
      </el-card>
    </template>

    <!-- 桌面端表格 -->
    <el-table v-else :data="list" border stripe>
      <el-table-column prop="title" label="作业标题" width="200" />
      <el-table-column prop="description" label="作业要求" show-overflow-tooltip />
      <el-table-column prop="deadline" label="截止时间" width="170">
        <template #default="{ row }">{{ row.deadline?.replace('T', ' ') || '不限' }}</template>
      </el-table-column>
      <el-table-column label="作业附件" width="160">
        <template #default="{ row }">
          <el-link v-if="row.filename" type="primary" @click="downloadAttachment(row)">
            {{ row.filename }}
          </el-link>
          <span v-else>无</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.submitted ? 'success' : 'warning'">
            {{ row.submitted ? '已提交' : '待提交' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="110">
        <template #default="{ row }">
          <el-button link type="primary" @click="openUpload(row)">
            {{ row.submitted ? '重新提交' : '提交作业' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog.visible" :title="`提交作业 - ${dialog.title}`" :width="isMobile ? '94%' : '560px'">
      <el-form label-width="80px">
        <el-form-item label="作业内容">
          <el-input v-model="dialog.content" type="textarea" :rows="6"
                    placeholder="填写作业文字内容（可与附件同时提交）" />
        </el-form-item>
        <el-form-item label="附件">
          <input type="file" @change="onFileChange" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">提交</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { authUrl } from '../../api'
import { useIsMobile } from '../../composables/useIsMobile'

const { isMobile } = useIsMobile()
const list = ref([])
const dialog = reactive({ visible: false, id: 0, title: '', content: '', file: null })
const submitting = ref(false)

async function load() {
  list.value = await api.get('/assignments')
}

function openUpload(row) {
  dialog.id = row.id
  dialog.title = row.title
  dialog.content = ''
  dialog.file = null
  dialog.visible = true
}

function onFileChange(e) {
  dialog.file = e.target.files[0] || null
}

function downloadAttachment(row) {
  const a = document.createElement('a')
  a.href = authUrl(`/api/assignments/${row.id}/file`)
  a.download = row.filename
  a.click()
}

async function submit() {
  if (!dialog.content && !dialog.file) {
    ElMessage.warning('请填写作业内容或选择附件')
    return
  }
  submitting.value = true
  try {
    const fd = new FormData()
    fd.append('assignment_id', dialog.id)
    fd.append('content', dialog.content)
    if (dialog.file) fd.append('file', dialog.file)
    await api.post('/submissions', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('提交成功')
    dialog.visible = false
    load()
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.m-card { margin-bottom: 12px; }
.m-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.m-desc {
  color: #555;
  margin: 8px 0;
  white-space: pre-wrap;
}
.m-meta { color: #999; font-size: 12px; margin: 4px 0; }
</style>
