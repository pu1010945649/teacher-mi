<template>
  <el-card>
    <div class="toolbar">
      <el-button type="success" @click="openDialog()">布置新作业</el-button>
    </div>
    <!-- 手机端卡片列表 -->
    <template v-if="isMobile">
      <el-empty v-if="!list.length" description="暂无作业" />
      <el-card v-for="row in list" :key="row.id" class="m-card" shadow="never">
        <div class="m-head">
          <b>{{ row.title }}</b>
          <el-tag :type="row.assigned_to_all ? 'success' : 'warning'" size="small">
            {{ row.assigned_to_all ? '全体学生' : `${row.target_count} 名学生` }}
          </el-tag>
        </div>
        <p class="m-desc">{{ row.description || '（无作业要求）' }}</p>
        <p v-if="row.student_states?.length" class="m-meta">
          <el-popover placement="bottom-start" :width="260" trigger="click">
            <template #reference>
              <span class="stu-summary">
                <template v-if="row.assigned_to_all">全体 · </template>已交 {{ submittedCount(row) }}/{{ row.student_states.length }}
                <el-icon class="stu-caret"><CaretBottom /></el-icon>
              </span>
            </template>
            <div class="stu-pop">
              <el-tag v-for="s in row.student_states" :key="s.id" :type="s.status" size="small"
                      effect="light" class="stu-tag">{{ s.name }}</el-tag>
            </div>
          </el-popover>
        </p>
        <p class="m-meta">截止：{{ row.deadline?.replace('T', ' ') || '不限' }}</p>
        <p v-if="row.filename" class="m-meta">
          附件：<el-link type="primary" @click="downloadAttachment(row)">{{ row.filename }}</el-link>
        </p>
        <div class="m-ops">
          <el-button size="small" type="primary" plain
                     @click="$router.push({ path: '/teacher/grading', query: { id: row.id } })">
            查看提交
          </el-button>
          <el-button size="small" type="success" plain @click="openTargets(row)">抄送学生</el-button>
          <el-button size="small" type="warning" plain @click="openVideo(row)">
            讲解视频{{ row.has_video ? '' : '（未上传）' }}
          </el-button>
          <el-popconfirm title="删除作业将同时删除其提交记录，确定？" @confirm="remove(row)">
            <template #reference>
              <el-button size="small" type="danger" plain>删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </el-card>
    </template>

    <!-- 桌面端表格 -->
    <el-table v-else :data="list" border stripe>
      <el-table-column prop="title" label="作业标题" width="200" />
      <el-table-column prop="description" label="作业要求" show-overflow-tooltip />
      <el-table-column label="发布时间" width="150">
        <template #default="{ row }">{{ fmtTime(row.created_at) || '—' }}</template>
      </el-table-column>
      <el-table-column label="提交情况" min-width="180">
        <template #default="{ row }">
          <el-popover v-if="row.student_states?.length" placement="bottom-start" :width="280" trigger="hover">
            <template #reference>
              <span class="stu-summary">
                <template v-if="row.assigned_to_all">全体 · </template>已交 {{ submittedCount(row) }}/{{ row.student_states.length }}
                <el-icon class="stu-caret"><CaretBottom /></el-icon>
              </span>
            </template>
            <div class="stu-pop">
              <el-tag v-for="s in row.student_states" :key="s.id" :type="s.status" size="small"
                      effect="light" class="stu-tag">{{ s.name }}</el-tag>
            </div>
          </el-popover>
          <span v-else class="target-names no-target">无下发对象</span>
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
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button link type="primary" @click="$router.push({ path: '/teacher/grading', query: { id: row.id } })">
            查看提交
          </el-button>
          <el-button link type="success" @click="openTargets(row)">抄送学生</el-button>
          <el-button link type="warning" @click="openVideo(row)">
            讲解视频{{ row.has_video ? '' : '（未上传）' }}
          </el-button>
          <el-popconfirm title="删除作业将同时删除其提交记录，确定？" @confirm="remove(row)">
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog.visible" title="布置作业" :width="isMobile ? '94%' : '640px'">
      <el-form :model="dialog.form" label-width="90px">
        <el-form-item label="作业方式">
          <el-radio-group v-model="dialog.mode">
            <el-radio value="manual">手动布置</el-radio>
            <el-radio value="ai">AI 个性化练习</el-radio>
          </el-radio-group>
          <div class="hint" style="margin-left: 12px">
            {{ dialog.mode === 'ai' ? '按每位学生的作业反馈用 AI 生成独立练习，生成后自动下发（含 PDF 附件）' : '自己填写要求并可上传附件' }}
          </div>
        </el-form-item>
        <template v-if="dialog.mode === 'manual'">
          <el-form-item label="科目">
            <el-input v-model="dialog.form.subject" maxlength="50" placeholder="不填则自动使用你的任教科目" />
          </el-form-item>
          <el-form-item label="标题"><el-input v-model="dialog.form.title" /></el-form-item>
        </template>
        <el-form-item label="下发对象">
          <el-select v-model="dialog.form.studentIds" multiple collapse-tags collapse-tags-tooltip
                     placeholder="不选 = 下发给全体学生" style="width: 100%"
                     @change="onStudentsChange">
            <el-option v-for="s in students" :key="s.id"
                       :label="`${s.real_name || s.username}（${s.class_name || '未分班'}）`" :value="s.id" />
          </el-select>
        </el-form-item>
        <template v-if="dialog.mode === 'ai'">
          <el-form-item label="关注点来源">
            <div style="width: 100%">
              <el-select v-model="dialog.form.courseFbIds" multiple collapse-tags collapse-tags-tooltip
                         placeholder="课程反馈（可单节/多节，不选 = 全部）" style="width: 100%" size="small">
                <el-option-group v-for="g in fbGroups" :key="g.student" :label="g.student">
                  <el-option v-for="f in g.items" :key="f.id"
                             :label="`${f.course_title}｜${(f.created_at || '').slice(0, 10)} ${f.content.slice(0, 30)}`"
                             :value="f.id" />
                </el-option-group>
              </el-select>
              <el-select v-model="dialog.form.subIds" multiple collapse-tags collapse-tags-tooltip
                         placeholder="作业批改（可单次/多次，不选 = 全部）" style="width: 100%; margin-top: 6px" size="small">
                <el-option-group v-for="g in subGroups" :key="g.student" :label="g.student">
                  <el-option v-for="s in g.items" :key="s.id"
                             :label="`${s.assignment_title}｜${s.score ?? '未批改'}｜${(s.submitted_at || '').slice(0, 10)}`"
                             :value="s.id" />
                </el-option-group>
              </el-select>
              <div class="hint" style="margin-left: 2px">
                必须至少选择一项课程反馈或作业批改作为练习关注点来源；也可两者组合
              </div>
            </div>
          </el-form-item>
        </template>
        <template v-if="dialog.mode === 'manual'">
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
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button v-if="dialog.mode === 'manual'" type="primary" :loading="saving" @click="save">发布</el-button>
        <el-button v-else type="success" :loading="saving" @click="saveAi">生成练习</el-button>
      </template>
    </el-dialog>

    <!-- 抄送学生 -->
    <el-dialog v-model="targets.visible" :title="`抄送学生 - ${targets.row?.title || ''}`"
               :width="isMobile ? '94%' : '480px'">
      <p v-if="targets.row?.assigned_to_all" class="hint" style="margin: 0 0 10px">
        该作业当前下发给全体学生，抄送后范围将固定为「当前全部学生 + 本次所选」。
      </p>
      <p v-else class="hint" style="margin: 0 0 10px">
        已下发：{{ targets.row?.target_names?.join('、') || '无' }}
      </p>
      <el-select v-model="targets.ids" multiple filterable placeholder="选择要抄送的学生（已下发的不会重复出现）" style="width: 100%">
        <el-option v-for="s in ccCandidates" :key="s.id"
                   :label="`${s.real_name || s.username}（${s.class_name || '未分班'}）`" :value="s.id" />
      </el-select>
      <template #footer>
        <el-button @click="targets.visible = false">取消</el-button>
        <el-button type="primary" :loading="targets.saving" @click="saveTargets">确认抄送</el-button>
      </template>
    </el-dialog>

    <!-- 讲解视频 -->
    <el-dialog v-model="video.visible" :title="`讲解视频 - ${video.row?.title || ''}`"
               :width="isMobile ? '96%' : '680px'" destroy-on-close>
      <div v-if="video.row?.has_video && !video.replacing" class="video-preview">
        <video :src="authUrl(`/api/assignments/${video.row.id}/video`)" controls preload="metadata"
               style="width: 100%; max-height: 60vh; border-radius: 6px; background: #000" />
        <p class="hint" style="margin: 6px 0 0">当前视频：{{ video.row.video_filename }}</p>
        <el-divider style="margin: 12px 0" />
        <div style="margin-bottom: 6px"><b>学生查看记录</b>（每次点开记一次）</div>
        <el-table v-if="video.views.length" :data="video.views" size="small" max-height="200">
          <el-table-column prop="student_name" label="学生" min-width="90" />
          <el-table-column prop="count" label="查看次数" width="90" />
          <el-table-column prop="last_viewed_at" label="最近查看时间" min-width="150" />
        </el-table>
        <p v-else class="hint" style="margin: 4px 0 0">还没有学生查看过</p>
      </div>
      <template v-else>
        <p class="hint" style="margin: 0 0 10px">
          支持上传 mp4 / webm / ogg / mov / m4v，大小不超过 200MB；重新上传会覆盖旧视频。
          超过 15MB 的视频会在本机自动压缩（720p 限码率）后再上传，压缩需按视频时长播放一遍，请耐心等待。
        </p>
        <input type="file" accept="video/mp4,video/webm,video/ogg,video/quicktime,video/x-m4v"
               :disabled="video.compressing > 0" @change="onVideoChange" />
        <div v-if="video.file && video.compressing === 0" class="hint" style="margin-top: 8px">
          已选择：{{ video.file.name }}（{{ (video.file.size / 1024 / 1024).toFixed(1) }} MB）
        </div>
        <div v-if="video.compressing > 0" style="margin-top: 10px">
          <el-progress :percentage="video.compressing" :stroke-width="10" />
          <div class="hint" style="margin-top: 4px">正在本机压缩视频（请勿关闭窗口）…</div>
        </div>
      </template>
      <template #footer>
        <el-button v-if="video.row?.has_video && !video.replacing" type="warning" plain
                   @click="video.replacing = true">重新上传</el-button>
        <el-popconfirm v-if="video.row?.has_video" title="删除后学生将无法再看该讲解视频，确定？"
                       width="230" @confirm="removeVideo">
          <template #reference>
            <el-button type="danger" plain>删除视频</el-button>
          </template>
        </el-popconfirm>
        <el-button @click="video.visible = false">关闭</el-button>
        <el-button type="primary" :disabled="!video.file || video.compressing > 0"
                   :loading="video.saving" @click="saveVideo">
          上传视频
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑 AI 生成草稿 -->
    <el-dialog v-model="edit.visible" title="编辑练习（确认下发前可修改）" :width="isMobile ? '94%' : '640px'">
      <el-form label-width="90px">
        <el-form-item label="练习标题">
          <el-input v-model="edit.form.title" maxlength="100" />
        </el-form-item>
        <el-form-item label="练习内容">
          <el-input v-model="edit.form.content" type="textarea" :rows="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="edit.visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存并重建 PDF</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CaretBottom } from '@element-plus/icons-vue'
import api, { authUrl } from '../../api'
import { useRealtime } from '../../realtime'
import { useIsMobile } from '../../composables/useIsMobile'
import { ensureAiReady } from '../../composables/useAiReady'
import { compressVideo, shouldCompress, isCompressSupported } from '../../utils/videoCompress'

const { isMobile } = useIsMobile()
const list = ref([])
const students = ref([])
const pendingTasks = ref([])
const edit = reactive({ visible: false, form: { id: 0, title: '', content: '' } })
const targets = reactive({ visible: false, row: null, ids: [], saving: false })
// 抄送候选：排除已下发范围里的学生，避免重复选择
const ccCandidates = computed(() => {
  const sent = new Set(targets.row?.target_ids || [])
  return students.value.filter(s => !sent.has(s.id))
})
const dialog = reactive({
  visible: false,
  mode: 'manual',  // manual 手动布置 / ai 个性化练习
  form: { subject: '', title: '', description: '', deadline: null, studentIds: [], courseFbIds: [], subIds: [] },
  file: null,
})
// AI 练习关注点来源：只展示所选学生的课程反馈与作业批改记录
const sources = reactive({ feedbacks: [], submissions: [] })
const fbGroups = computed(() => groupByStudent(sources.feedbacks.filter(f => dialog.form.studentIds.includes(f.student_id))))
const subGroups = computed(() => groupByStudent(sources.submissions.filter(s => dialog.form.studentIds.includes(s.student_id))))

function groupByStudent(items) {
  const map = new Map()
  for (const it of items) {
    if (!map.has(it.student_id)) map.set(it.student_id, { student: it.student_name, items: [] })
    map.get(it.student_id).items.push(it)
  }
  return [...map.values()]
}
const aiLoading = ref(false)
const saving = ref(false)

async function load() {
  list.value = await api.get('/assignments')
  students.value = await api.get('/students')
  loadTasks()
}

// 待确认的 AI 练习（生成完成、等待教师编辑下发）
async function loadTasks() {
  try {
    const tasks = await api.get('/worksheet-tasks', { params: { limit: 100 } })
    pendingTasks.value = tasks.filter(t => t.status === 'generated')
  } catch { /* ignore */ }
}

function openEdit(row) {
  edit.form = { id: row.id, title: row.title, content: row.content }
  edit.visible = true
}

// 时间格式化：年月日 + 24 小时制（YYYY-MM-DD HH:mm）
function fmtTime(s) {
  return s ? s.replace('T', ' ').slice(0, 16) : ''
}

// 已提交人数（非红色状态即有提交）
function submittedCount(row) {
  return (row.student_states || []).filter(s => s.status !== 'danger').length
}

function openTargets(row) {
  targets.row = row
  targets.ids = []
  targets.visible = true
}

// ===== 讲解视频 =====
const video = reactive({ visible: false, row: null, file: null, replacing: false, saving: false, compressing: 0, views: [] })

async function openVideo(row) {
  video.row = row
  video.file = null
  video.replacing = false
  video.compressing = 0
  video.views = []
  video.visible = true
  if (row.has_video) {
    try {
      video.views = await api.get(`/assignments/${row.id}/video/views`)
    } catch { /* 权限外静默 */ }
  }
}

async function onVideoChange(e) {
  const f = e.target.files[0]
  e.target.value = ''
  if (!f) return
  if (f.size > 200 * 1024 * 1024) {
    ElMessage.warning('视频大小不能超过 200MB')
    return
  }
  video.file = f
  // 大文件自动在前端压缩（720p 限码率），失败则回退用原文件
  if (shouldCompress(f)) {
    if (!isCompressSupported()) {
      ElMessage.warning('当前浏览器不支持自动压缩，将直接上传原视频')
      return
    }
    video.compressing = 0
    try {
      video.file = await compressVideo(f, p => { video.compressing = p })
      ElMessage.success(`压缩完成：${(f.size / 1024 / 1024).toFixed(1)}MB → ${(video.file.size / 1024 / 1024).toFixed(1)}MB`)
    } catch {
      ElMessage.warning('自动压缩失败，将直接上传原视频')
      video.file = f
    } finally {
      video.compressing = 0
    }
  }
}

async function saveVideo() {
  if (!video.file) return
  video.saving = true
  try {
    const fd = new FormData()
    fd.append('file', video.file)
    await api.post(`/assignments/${video.row.id}/video`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('讲解视频已上传，学生端可观看')
    video.visible = false
    load()
  } finally {
    video.saving = false
  }
}

async function removeVideo() {
  await api.delete(`/assignments/${video.row.id}/video`)
  ElMessage.success('讲解视频已删除')
  video.visible = false
  load()
}

async function saveTargets() {
  if (!targets.ids.length) {
    ElMessage.warning('请选择要抄送的学生')
    return
  }
  targets.saving = true
  try {
    await api.post(`/assignments/${targets.row.id}/targets`, { student_ids: targets.ids })
    ElMessage.success('已抄送')
    targets.visible = false
    load()
  } finally {
    targets.saving = false
  }
}

async function saveEdit() {
  if (!edit.form.title.trim() || !edit.form.content.trim()) {
    ElMessage.warning('标题和内容不能为空')
    return
  }
  saving.value = true
  try {
    await api.put(`/worksheet-tasks/${edit.form.id}`, {
      title: edit.form.title, content: edit.form.content,
    })
    ElMessage.success('已保存并重建 PDF')
    edit.visible = false
    loadTasks()
  } finally {
    saving.value = false
  }
}

async function publishTask(row) {
  await api.post(`/worksheet-tasks/${row.id}/publish`)
  ElMessage.success('已下发到学生作业列表')
  loadTasks()
}

async function rejectTask(row) {
  await api.post(`/worksheet-tasks/${row.id}/reject`)
  ElMessage.success('已驳回')
  loadTasks()
}

function openDialog() {
  dialog.mode = 'manual'
  dialog.form = { subject: '', title: '', description: '', deadline: null, studentIds: [], courseFbIds: [], subIds: [] }
  dialog.file = null
  dialog.visible = true
  loadSources()
}

// 加载关注点来源：课程反馈 + 作业提交（一次全量，前端按学生分组）
async function loadSources() {
  try {
    const [fbs, subs] = await Promise.all([
      api.get('/courses/feedback-source'),
      api.get('/submissions/source'),
    ])
    sources.feedbacks = fbs
    sources.submissions = subs
  } catch { /* 加载失败时下拉为空，不影响手动布置 */ }
}

function onFileChange(e) {
  dialog.file = e.target.files[0] || null
}

// 学生选择变化时，清除不属于所选学生的关注点来源勾选
function onStudentsChange() {
  const ids = dialog.form.studentIds
  const fbOk = id => sources.feedbacks.find(f => f.id === id && ids.includes(f.student_id))
  const subOk = id => sources.submissions.find(s => s.id === id && ids.includes(s.student_id))
  dialog.form.courseFbIds = dialog.form.courseFbIds.filter(fbOk)
  dialog.form.subIds = dialog.form.subIds.filter(subOk)
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
    fd.append('subject', dialog.form.subject)
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

// AI 个性化练习：每位学生独立生成一份练习草稿，完成后由教师编辑确认再下发
async function saveAi() {
  if (!dialog.form.studentIds.length) {
    ElMessage.warning('AI 个性化练习需要选择学生（每人生成独立练习）')
    return
  }
  if (!dialog.form.courseFbIds.length && !dialog.form.subIds.length) {
    ElMessage.warning('请先选择关注点来源（课程反馈或作业批改记录）')
    return
  }
  saving.value = true
  try {
    // 统一 AI 前置校验（useAiReady）
    if (!(await ensureAiReady())) return
    // 按学生拆分所选关注点来源
    const fbById = Object.fromEntries(sources.feedbacks.map(f => [f.id, f]))
    const subById = Object.fromEntries(sources.submissions.map(s => [s.id, s]))
    const course_feedback_ids = {}
    const submission_ids = {}
    for (const sid of dialog.form.studentIds) {
      const fbs = dialog.form.courseFbIds.filter(id => fbById[id]?.student_id === sid)
      const subs = dialog.form.subIds.filter(id => subById[id]?.student_id === sid)
      if (fbs.length) course_feedback_ids[sid] = fbs
      if (subs.length) submission_ids[sid] = subs
    }
    const tasks = await api.post('/worksheet-tasks', {
      student_ids: dialog.form.studentIds,
      course_feedback_ids,
      submission_ids,
    })
    ElMessage.success(`已创建 ${tasks.length} 个后台生成任务，完成后请在“AI 练习待确认”中编辑并下发`)
    dialog.visible = false
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
// 学生提交作业、作业增删、AI 练习生成完成（多端同步）→ 自动刷新
useRealtime(['submission', 'assignment', 'worksheet'], load)
</script>

<style scoped>
.toolbar { margin-bottom: 14px; }
.section-title { margin: 0 0 10px; color: #e6a23c; }
.hint { margin-left: 8px; color: #999; font-size: 12px; }
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
.m-ops { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.target-names { color: #606266; font-size: 13px; cursor: default; }
.target-names.no-target { color: #c0c4cc; }
.stu-tag { margin: 2px 4px 2px 0; }
.stu-summary {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: #409eff;
  cursor: default;
  font-size: 13px;
}
.stu-caret { font-size: 12px; color: #a0a6b1; }
.stu-pop { max-height: 320px; overflow: auto; }
</style>
