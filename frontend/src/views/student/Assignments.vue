<template>
  <el-card>
    <!-- 时间筛选栏 -->
    <div class="filter-bar">
      <el-select v-model="filters.sort" size="small" style="width: 150px" @change="load">
        <el-option label="最新发布优先" value="created_desc" />
        <el-option label="最早发布优先" value="created_asc" />
        <el-option label="截止时间近优先" value="deadline_asc" />
        <el-option label="截止时间远优先" value="deadline_desc" />
      </el-select>
      <el-date-picker v-model="filters.range" type="daterange" size="small"
                      range-separator="至" start-placeholder="发布开始" end-placeholder="发布结束"
                      value-format="YYYY-MM-DD" :style="{ width: isMobile ? '100%' : '240px' }" @change="load" />
      <el-button v-if="filters.range || filters.sort !== 'created_desc'" size="small" link
                 type="primary" @click="resetFilters">重置</el-button>
    </div>

    <!-- 手机端卡片列表 -->
    <template v-if="isMobile">
      <el-empty v-if="!list.length" description="暂无作业" />
      <el-card v-for="row in list" :key="row.id" class="m-card" shadow="never">
        <div class="m-head">
          <b>{{ row.title }}</b>
          <el-tag :type="statusOf(row).type" size="small">
            {{ statusOf(row).text }}
          </el-tag>
        </div>
        <p class="m-desc">{{ row.description || '（无作业要求）' }}</p>
        <p class="m-meta">下发老师：{{ row.created_by_name || '—' }}</p>
        <p class="m-meta">截止：{{ fmtTime(row.deadline) || '不限' }}</p>
        <p v-if="row.filename" class="m-meta">
          附件：<el-link type="primary" @click="downloadAttachment(row)">{{ row.filename }}</el-link>
        </p>
        <p v-if="row.has_video" class="m-meta">
          讲解：
          <el-link v-if="!row.video_locked" type="warning" @click="openVideo(row)">观看讲解视频</el-link>
          <el-tooltip v-else content="老师批改评分后才能观看讲解视频" placement="top">
            <el-link type="info" disabled>批改后可观看</el-link>
          </el-tooltip>
        </p>
        <el-button v-if="!row.submitted || row.returned" :type="row.returned ? 'danger' : 'primary'"
                   size="small" @click="openUpload(row)">
          {{ row.returned ? '重新提交' : '提交作业' }}
        </el-button>
        <el-button v-if="isCompleted(row)" type="success" size="small" plain @click="openHistory(row)">
          查看提交历史
        </el-button>
        <el-button v-if="row.my_feedback" type="success" size="small" plain @click="openFeedback(row)">
          查看反馈
        </el-button>
      </el-card>
    </template>

    <!-- 桌面端表格 -->
    <el-table v-else :data="list" border stripe>
      <el-table-column prop="title" label="作业标题" width="200" />
      <el-table-column label="科目" width="90">
        <template #default="{ row }">{{ row.subject || '—' }}</template>
      </el-table-column>
      <el-table-column label="下发老师" width="100">
        <template #default="{ row }">{{ row.created_by_name || '—' }}</template>
      </el-table-column>
      <el-table-column label="发布时间" width="150">
        <template #default="{ row }">{{ fmtTime(row.created_at) || '—' }}</template>
      </el-table-column>
      <el-table-column label="截止时间" width="150">
        <template #default="{ row }">{{ fmtTime(row.deadline) || '不限' }}</template>
      </el-table-column>
      <el-table-column prop="description" label="作业要求" show-overflow-tooltip />
      <el-table-column label="作业附件" width="160">
        <template #default="{ row }">
          <el-link v-if="row.filename" type="primary" @click="downloadAttachment(row)">
            {{ row.filename }}
          </el-link>
          <span v-else>无</span>
        </template>
      </el-table-column>
      <el-table-column label="讲解视频" width="130">
        <template #default="{ row }">
          <el-button v-if="row.has_video && !row.video_locked" link type="warning" @click="openVideo(row)">观看讲解</el-button>
          <el-tooltip v-else-if="row.has_video" content="老师批改评分后才能观看讲解视频">
            <span style="color: #999">批改后可观看</span>
          </el-tooltip>
          <span v-else style="color: #999">无</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusOf(row).type">
            {{ statusOf(row).text }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="教师反馈" width="120">
        <template #default="{ row }">
          <el-button v-if="row.my_feedback" link type="success" @click="openFeedback(row)">
            查看反馈
          </el-button>
          <span v-else style="color: #999">暂无</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="!row.submitted || row.returned" link type="primary" @click="openUpload(row)">
            {{ row.returned ? '重新提交' : (row.submitted ? '更新提交' : '提交作业') }}
          </el-button>
          <el-button v-else-if="isCompleted(row)" link type="success" @click="openHistory(row)">
            查看提交历史
          </el-button>
          <el-button v-else-if="row.my_feedback" type="success" size="small" plain @click="openFeedback(row)">查看反馈</el-button>
          <el-button v-else link type="primary" @click="openUpload(row)">更新提交</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog.visible" :title="`提交作业 - ${dialog.title}`" :width="isMobile ? '94%' : '560px'">
      <el-alert v-if="dialog.returned" type="warning" :closable="false" show-icon style="margin-bottom: 14px"
                title="老师已退回本次作业，请查看反馈后重新提交（上一轮提交与反馈会保留）" />
      <el-form label-width="80px">
        <el-form-item label="作业内容">
          <el-input v-model="dialog.content" type="textarea" :rows="6"
                    placeholder="填写作业文字内容（可与附件同时提交）" />
        </el-form-item>
        <el-form-item label="附件">
          <input ref="cameraInput" type="file" accept="image/*" capture="environment" class="hidden-input" @change="onFileChange" />
          <input ref="galleryInput" type="file" accept="image/*" class="hidden-input" @change="onFileChange" />
          <input ref="fileInput" type="file" class="hidden-input" @change="onFileChange" />
          <div class="upload-row">
            <el-button size="small" type="primary" plain @click="cameraInput.click()">
              <el-icon><Camera /></el-icon>&nbsp;拍照上传
            </el-button>
            <el-button size="small" type="primary" plain @click="galleryInput.click()">选择照片</el-button>
            <el-button size="small" @click="fileInput.click()">选择文件</el-button>
          </div>
          <div v-if="dialog.file" class="file-tip">
            已选择：{{ dialog.file.name }}（{{ (dialog.file.size / 1024 / 1024).toFixed(1) }} MB）
            <el-link type="danger" :underline="false" @click="clearFile">移除</el-link>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">提交</el-button>
      </template>
    </el-dialog>

    <!-- 教师反馈弹窗 -->
    <el-dialog v-model="fbDialog.visible" :title="`教师反馈 - ${fbDialog.title}`" :width="isMobile ? '96%' : '600px'">
      <template v-if="fbDialog.data">
        <el-descriptions :column="isMobile ? 1 : 2" border size="small">
          <el-descriptions-item label="分数">
            <b style="color: #f56c6c; font-size: 16px">{{ fbDialog.data.score ?? '未评分' }}</b>
          </el-descriptions-item>
          <el-descriptions-item label="时间">{{ fbDialog.data.created_at?.replace('T', ' ').slice(0, 16) }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="fbDialog.data.content" class="fb-section">
          <b>评语</b>
          <p class="fb-content">{{ fbDialog.data.content }}</p>
        </div>
        <div v-if="fbDialog.data.annotation" class="fb-section">
          <b>文字批注</b>
          <p class="fb-content">{{ fbDialog.data.annotation }}</p>
        </div>
        <div v-if="fbDialog.data.has_annotated_file" class="fb-section">
          <b>批注文件</b>
          <p class="fb-actions">
            <el-button v-if="isImageFile(fbDialog.data.filename)" size="small" type="primary" plain
                       @click="viewAnnotated(); previewImage = true">在线查看</el-button>
            <el-button size="small" type="primary" plain @click="downloadAnnotated">
              下载 {{ fbDialog.data.filename }}
            </el-button>
          </p>
        </div>
      </template>
    </el-dialog>

    <!-- 讲解视频播放 -->
    <el-dialog v-model="video.visible" :title="`讲解视频 - ${video.title}`"
               :width="isMobile ? '96%' : '680px'" destroy-on-close>
      <video :src="video.url" controls preload="metadata"
             style="width: 100%; max-height: 60vh; border-radius: 6px; background: #000" />
    </el-dialog>

    <!-- 批注图片在线查看 -->
    <el-dialog v-model="previewImage" title="批注图片预览" :width="isMobile ? '98%' : '720px'" append-to-body>
      <div class="preview-wrap">
        <img :src="annotatedUrl" alt="批注图片" />
      </div>
      <template #footer>
        <el-button @click="previewImage = false">关闭</el-button>
        <el-button type="primary" @click="downloadAnnotated">下载图片</el-button>
      </template>
    </el-dialog>

    <!-- 提交历史弹窗 -->
    <el-dialog v-model="histDialog.visible" :title="`提交历史 - ${histDialog.title}`"
               :width="isMobile ? '96%' : '640px'">
      <el-empty v-if="!histDialog.items.length" description="暂无提交记录" />
      <el-timeline v-else>
        <el-timeline-item v-for="s in histDialog.items" :key="s.id" placement="top"
                          :timestamp="`第 ${s.attempt} 次提交 · ${fmtTime(s.submitted_at)}`">
          <el-tag :type="subStatusOf(s).type" size="small">{{ subStatusOf(s).text }}</el-tag>
          <p v-if="s.content" class="fb-content" style="margin-top: 8px">{{ s.content }}</p>
          <p v-if="s.has_file" style="margin: 8px 0 0">
            附件：<el-link type="primary" @click="downloadSubmissionFile(s)">{{ s.filename }}</el-link>
          </p>
          <div v-if="s.feedback" class="fb-section">
            <b>教师批改</b>
            <p class="fb-content">
              {{ s.feedback.score != null ? `分数：${s.feedback.score}　` : '' }}{{ s.feedback.content || '（无评语）' }}
            </p>
            <p v-if="s.feedback.has_annotated_file" class="fb-actions" style="margin-top: 8px">
              <el-button size="small" type="primary" plain
                         @click="viewAnnotated(s.feedback.submission_id); previewImage = true">在线查看</el-button>
            </p>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Camera } from '@element-plus/icons-vue'
import api, { authUrl } from '../../api'
import { useRealtime } from '../../realtime'
import { useIsMobile } from '../../composables/useIsMobile'

const { isMobile } = useIsMobile()
const list = ref([])
const filters = reactive({ sort: 'created_desc', range: null })
const cameraInput = ref(null)
const galleryInput = ref(null)
const fileInput = ref(null)
const dialog = reactive({ visible: false, id: 0, title: '', content: '', file: null, returned: false })
const submitting = ref(false)

async function load() {
  const params = { sort: filters.sort }
  if (filters.range?.length === 2) {
    params.start_date = filters.range[0]
    params.end_date = filters.range[1]
  }
  list.value = await api.get('/assignments', { params })
}

function resetFilters() {
  filters.sort = 'created_desc'
  filters.range = null
  load()
}

// 时间格式化：年月日 + 24 小时制（YYYY-MM-DD HH:mm）
function fmtTime(s) {
  return s ? s.replace('T', ' ').slice(0, 16) : ''
}

function openUpload(row) {
  dialog.id = row.id
  dialog.title = row.title
  dialog.content = ''
  dialog.file = null
  dialog.returned = row.returned
  dialog.visible = true
}

// 作业状态：退回 > 已完成（已评分）> 已批改（未评分）> 已提交 > 待提交
function statusOf(row) {
  if (row.returned) return { type: 'danger', text: '退回' }
  if (row.my_feedback && row.my_feedback.score != null) return { type: 'success', text: '已完成' }
  if (row.my_feedback) return { type: 'primary', text: '已批改' }
  return row.submitted ? { type: 'success', text: '已提交' } : { type: 'warning', text: '待提交' }
}

function isCompleted(row) {
  return !!(row.my_feedback && row.my_feedback.score != null)
}

function onFileChange(e) {
  const f = e.target.files[0]
  e.target.value = '' // 允许再次选择同一文件
  if (!f) return
  if (f.size > 20 * 1024 * 1024) {
    ElMessage.warning('附件不能超过 20MB，拍照/照片过大时可适当降低相机画质')
    return
  }
  dialog.file = f
}

function clearFile() {
  dialog.file = null
}

// ===== 教师反馈 =====
const fbDialog = reactive({ visible: false, title: '', data: null, submissionId: 0 })
const previewImage = ref(false)
const annotatedUrl = ref('')

const IMAGE_EXT = /\.(png|jpe?g|gif|bmp|webp)$/i
function isImageFile(name) {
  return IMAGE_EXT.test(name || '')
}

function openFeedback(row) {
  fbDialog.title = row.title
  fbDialog.data = row.my_feedback
  fbDialog.submissionId = row.my_feedback?.submission_id
  fbDialog.visible = true
}

function viewAnnotated(submissionId) {
  const sid = submissionId ?? fbDialog.submissionId
  annotatedUrl.value = authUrl(`/api/feedback/submission/${sid}/annotated-file`)
}

function downloadAnnotated() {
  const a = document.createElement('a')
  a.href = authUrl(`/api/feedback/submission/${fbDialog.submissionId}/annotated-file`)
  a.download = fbDialog.data?.filename || 'annotated'
  a.click()
}

function downloadAttachment(row) {
  const a = document.createElement('a')
  a.href = authUrl(`/api/assignments/${row.id}/file`)
  a.download = row.filename
  a.click()
}

// ===== 提交历史 =====
const SUB_STATUS = {
  submitted: { type: 'primary', text: '已提交' },
  returned: { type: 'danger', text: '已退回' },
  graded: { type: 'warning', text: '已批改' },
  completed: { type: 'success', text: '已完成' },
}
function subStatusOf(s) {
  return SUB_STATUS[s.status] || { type: 'info', text: s.status }
}

const histDialog = reactive({ visible: false, title: '', items: [] })
async function openHistory(row) {
  histDialog.title = row.title
  histDialog.items = []
  histDialog.visible = true
  const all = await api.get('/submissions/my')
  histDialog.items = all.filter(s => s.assignment_id === row.id)
    .sort((a, b) => b.attempt - a.attempt)
}

function downloadSubmissionFile(s) {
  const a = document.createElement('a')
  a.href = authUrl(`/api/submissions/${s.id}/file`)
  a.download = s.filename
  a.click()
}

// 讲解视频播放
const video = reactive({ visible: false, title: '', url: '' })
function openVideo(row) {
  video.title = row.title
  video.url = authUrl(`/api/assignments/${row.id}/video`)
  video.visible = true
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
// 作业下发/更新、老师批改反馈、个性化练习发布 → 自动刷新
useRealtime(['assignment', 'feedback', 'worksheet'], load)
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
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.hidden-input { display: none; }
.fb-section { margin-top: 14px; }
.fb-section > b { display: block; margin-bottom: 6px; color: #333; }
.fb-actions { margin: 0; display: flex; gap: 8px; flex-wrap: wrap; }
.fb-content {
  margin: 0;
  padding: 10px;
  background: #f7f8fa;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
}
.preview-wrap {
  max-height: 70vh;
  overflow: auto;
  text-align: center;
}
.preview-wrap img { max-width: 100%; }
.upload-row { display: flex; flex-wrap: wrap; gap: 8px; }
.file-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #666;
  width: 100%;
  word-break: break-all;
}
</style>
