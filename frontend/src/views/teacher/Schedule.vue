<template>
  <el-card>
    <div class="toolbar">
      <el-button size="small" @click="shiftWeek(-1)">上一周</el-button>
      <b class="week-label">{{ weekLabel }}</b>
      <el-button size="small" @click="shiftWeek(1)">下一周</el-button>
      <el-button size="small" link type="primary" @click="goThisWeek">本周</el-button>
      <div class="spacer" />
      <el-select v-model="filterStudent" size="small" clearable placeholder="全部学生"
                 style="width: 140px" @change="load">
        <el-option v-for="s in students" :key="s.id" :label="s.real_name || s.username"
                   :value="s.id" />
      </el-select>
      <el-button v-if="filterStudent" size="small" type="primary" plain @click="backToMine">
        我的课表
      </el-button>
    </div>

    <!-- 手机端：按天查看 + 点空白格排课 -->
    <template v-if="isMobile">
      <div class="day-chips">
        <div v-for="(day, di) in weekDays" :key="day.key" class="day-chip"
             :class="{ active: di === selectedDay, today: day.isToday }" @click="selectedDay = di">
          {{ day.label }}<span class="chip-md">{{ day.md }}</span>
        </div>
      </div>
      <div v-loading="loading">
        <template v-if="dayCourses.length">
          <el-card v-for="c in dayCourses" :key="c.id" class="m-course" shadow="never"
                   :class="{ past: isPast(c), others: !c.is_mine }"
                   :style="{ borderLeftColor: isPast(c) ? '#c0c4cc' : (c.is_mine ? colorOf(c.student_id).bd : '#c0c4cc') }"
                   @click="c.is_mine && openFeedback(c)">
            <div class="m-course-head">
              <b>{{ c.title }}</b>
              <el-tag v-if="!c.is_mine" type="info" size="small">{{ c.teacher_name }}排课</el-tag>
              <el-tag v-else-if="c.feedbacks?.length" type="success" size="small">有反馈</el-tag>
            </div>
            <p class="m-course-time">
              {{ fmtTime(c.start_time) }}<template v-if="c.end_time"> ~ {{ fmtTime(c.end_time) }}</template>
              · {{ c.student_name }}
              <template v-if="c.location"> · {{ c.location }}</template>
            </p>
            <p v-if="c.note" class="m-course-note">{{ c.note }}</p>
            <div v-if="c.is_mine" class="m-course-ops" @click.stop>
              <el-button size="small" type="primary" plain @click="openEdit(c)">编辑课程</el-button>
              <el-popconfirm title="确定删除该课程？" @confirm="removeCourse(c)">
                <template #reference>
                  <el-button size="small" type="danger" plain>删除</el-button>
                </template>
              </el-popconfirm>
            </div>
            <p v-else class="m-course-note" style="color:#999">其他老师排的课程，仅展示</p>
          </el-card>
        </template>
        <el-empty v-else description="当天暂无课程" :image-size="80" />
      </div>
      <div class="hint" style="margin-top: 10px">
        提示：点自己排的课程卡片录入反馈；选择学生后可查看该学生全部课程（其他老师的课仅展示）
      </div>
    </template>

    <!-- 桌面端：周视图网格（课程块按分钟比例占位，同小时剩余时间可继续排课） -->
    <div v-else v-loading="loading" class="grid-wrap">
      <div class="grid" :class="{ mobile: isMobile }">
        <!-- 表头：日期 -->
        <div class="corner-cell"></div>
        <div v-for="(day, di) in weekDays" :key="day.key" class="head-cell"
             :class="{ today: day.isToday }">
          {{ day.label }}<br /><span class="md">{{ day.md }}</span>
        </div>

        <!-- 小时刻度列 -->
        <div class="hour-col">
          <div v-for="hour in hours" :key="hour" class="hour-cell">{{ hour }}:00</div>
        </div>

        <!-- 每天一列：空白格供拖选排课，课程块按时间比例绝对定位 -->
        <div v-for="(day, di) in weekDays" :key="day.key + '-col'" class="day-col"
             :class="{ today: day.isToday }">
          <div v-for="hour in hours" :key="hour" class="slot-cell"
               :class="{ selecting: isSelecting(day.key, hour) }"
               @mousedown="selectStart(day.key, hour)"
               @mouseenter="selectOver(day.key, hour)"
               @mouseup="selectEnd()" />
          <!-- 课程块（他人课程只读展示） -->
          <div v-for="c in coursesOf(day.key)" :key="c.id" class="course-block"
               :class="{ past: isPast(c), others: !c.is_mine }" :style="blockStyle(c)"
               :title="c.is_mine ? '点击录入学习反馈' : `其他老师（${c.teacher_name}）排课，仅展示`"
               @mousedown.stop @click.stop="c.is_mine && openFeedback(c)">
            <b class="c-title">{{ c.title }}</b>
            <div class="c-meta">
              {{ fmtTime(c.start_time) }}<template v-if="c.end_time">~{{ fmtTime(c.end_time) }}</template>
              · {{ c.is_mine ? c.student_name : c.teacher_name }}
            </div>
            <div v-if="c.is_mine && c._h > 40" class="c-ops" @click.stop>
              <el-button link type="primary" size="small" @click="openEdit(c)">编辑</el-button>
              <el-popconfirm title="确定删除该课程？" @confirm="removeCourse(c)">
                <template #reference>
                  <el-button link type="danger" size="small">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </div>
    </div>
    <p class="hint">提示：课程块按实际起止时间比例显示，点击空白时段排课（可按住拖动选连续多小时）；同一小时已有课程时，剩余时间仍可点击排课（在弹窗中把时间调整到空闲部分即可）；点击自己排的课程录入学习反馈；右上角选择学生可查看该学生全部课程，其他老师的课仅灰色展示不可操作</p>

    <!-- 排课 / 编辑弹窗 -->
    <el-dialog v-model="dialog.visible" :title="dialog.id ? '编辑课程' : '新增排课'"
               :width="isMobile ? '94%' : '520px'">
      <el-form label-width="80px">
        <el-form-item label="学生" required>
          <el-select v-model="dialog.student_id" filterable placeholder="选择学生" style="width: 100%">
            <el-option v-for="s in students" :key="s.id"
                       :label="`${s.real_name || s.username}${s.class_name ? '（' + s.class_name + '）' : ''}`"
                       :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="课程名称" required>
          <el-input v-model="dialog.title" placeholder="如：数学一对一辅导" />
        </el-form-item>
        <el-form-item v-if="!dialog.id && selRange.count > 0" label="已选时段">
          <el-tag size="small" type="info" effect="plain">
            {{ selRange.start }} ~ {{ selRange.end }}（{{ selRange.count }} 小时，可微调下方时间）
          </el-tag>
        </el-form-item>
        <el-form-item label="日期" required>
          <el-date-picker v-model="dialog.date" type="date" value-format="YYYY-MM-DD"
                          style="width: 100%" />
        </el-form-item>
        <el-form-item label="时间" required>
          <el-time-picker v-model="dialog.start" format="HH:mm" value-format="HH:mm"
                          placeholder="开始" style="width: 46%" />
          <span style="margin: 0 6px">~</span>
          <el-time-picker v-model="dialog.end" format="HH:mm" value-format="HH:mm"
                          placeholder="结束" style="width: 46%" />
        </el-form-item>
        <el-form-item label="快速加时">
          <el-radio-group v-model="quickHours" @change="applyQuickHours">
            <el-radio-button :value="1">1 小时</el-radio-button>
            <el-radio-button :value="2">2 小时</el-radio-button>
            <el-radio-button :value="3">3 小时</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="地点">
          <el-input v-model="dialog.location" placeholder="选填，如：教室 A / 线上" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="dialog.note" type="textarea" :rows="2" placeholder="本节课教学内容计划（选填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 课程反馈弹窗 -->
    <el-dialog v-model="fbDialog.visible" :title="`课程学习反馈 - ${fbDialog.course?.title || ''}`"
               :width="isMobile ? '96%' : '620px'">
      <template v-if="fbDialog.course">
        <el-descriptions :column="isMobile ? 1 : 2" border size="small" style="margin-bottom: 14px">
          <el-descriptions-item label="学生">{{ fbDialog.course.student_name }}</el-descriptions-item>
          <el-descriptions-item label="时间">
            {{ fbDialog.course.start_time?.slice(0, 16).replace('T', ' ') }}
            <template v-if="fbDialog.course.end_time">~ {{ fmtTime(fbDialog.course.end_time) }}</template>
          </el-descriptions-item>
          <el-descriptions-item v-if="fbDialog.course.location" label="地点">
            {{ fbDialog.course.location }}
          </el-descriptions-item>
          <el-descriptions-item v-if="fbDialog.course.note" label="备注" :span="isMobile ? 1 : 2">
            {{ fbDialog.course.note }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-for="f in fbDialog.course.feedbacks" :key="f.id" class="fb-item">
          <div class="fb-head">
            <b>教师反馈</b>
            <span class="fb-time">{{ f.created_at?.slice(0, 16).replace('T', ' ') }}</span>
            <el-popconfirm title="删除该条反馈？" @confirm="removeFeedback(f)">
              <template #reference>
                <el-button link type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
          <p class="fb-content">{{ f.content }}</p>
          <div v-if="f.reply" class="fb-reply">
            <b>学生回复</b>
            <p class="fb-content">{{ f.reply }}</p>
          </div>
        </div>

        <el-divider content-position="left">录入新反馈</el-divider>
        <el-input v-model="fbDialog.content" type="textarea" :rows="4"
                  placeholder="记录本节课学习情况、掌握程度、课后建议等，可先写要点再用 AI 润色" />
        <div style="margin-top: 10px; display: flex; justify-content: space-between">
          <el-button :loading="polishing" @click="polishFeedback">
            AI 润色扩写
          </el-button>
          <el-button type="primary" :loading="fbSaving" @click="saveFeedback">保存反馈</el-button>
        </div>
        <div class="hint" style="margin-top: 6px">
          AI 润色会根据上面的要点生成完整反馈，生成后可继续编辑，确认无误再保存
        </div>
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
const students = ref([])
const courses = ref([])
const filterStudent = ref(null)
const loading = ref(false)
const saving = ref(false)
const fbSaving = ref(false)

// 时间表显示 8:00 ~ 21:00
const hours = Array.from({ length: 14 }, (_, i) => i + 8)

// 课程块浅色配色（按学生区分，同一学生固定同色）
const PALETTE = [
  { bg: '#e6f4ff', bd: '#409eff' },  // 蓝
  { bg: '#f0f9eb', bd: '#67c23a' },  // 绿
  { bg: '#fdf6ec', bd: '#e6a23c' },  // 橙
  { bg: '#fef0f0', bd: '#f56c6c' },  // 红
  { bg: '#f4f0ff', bd: '#9a6fe0' },  // 紫
  { bg: '#e8f8f5', bd: '#36cfc9' },  // 青
  { bg: '#fff0f6', bd: '#eb2f96' },  // 粉
  { bg: '#ecf7fd', bd: '#5cadff' },  // 浅蓝
]
const colorOf = sid => PALETTE[sid % PALETTE.length]

const weekStart = ref(getMonday(new Date()))
const dialog = reactive({ visible: false, id: 0, student_id: null, title: '', date: '', start: '', end: '', location: '', note: '' })
const fbDialog = reactive({ visible: false, course: null, content: '' })
const polishing = ref(false)
// 手机端当前查看的星期下标（0=周一），默认定位到今天
const selectedDay = ref(Math.max(0, (new Date().getDay() || 7) - 1))

// 手机端：当前选中那天的课程（按开始时间排序）
const dayCourses = computed(() => {
  const key = weekDays.value[selectedDay.value]?.key
  if (!key) return []
  return courses.value
    .filter(c => c.start_time.slice(0, 10) === key)
    .sort((a, b) => a.start_time.localeCompare(b.start_time))
})

// —— 网格连续多时段选择（mousedown 起点拖到 mouseup，或单格点击）——
const selAnchor = ref(null)   // { date, hour } 起点
const selCursor = ref(null)   // { date, hour } 当前悬停
const quickHours = ref(1)

const selRange = computed(() => {
  if (!selAnchor.value || !selCursor.value) return { start: '', end: '', count: 0 }
  const a = selAnchor.value, b = selCursor.value
  const h1 = Math.min(a.hour, b.hour), h2 = Math.max(a.hour, b.hour)
  return {
    start: `${a.date} ${String(h1).padStart(2, '0')}:00`,
    end: `${b.date} ${String(h2 + 1).padStart(2, '0')}:00`,
    count: (a.date === b.date) ? h2 - h1 + 1 : 0,
  }
})

function isSelecting(dateKey, hour) {
  const a = selAnchor.value, c = selCursor.value
  if (!a || !c || a.date !== c.date) return false
  const h1 = Math.min(a.hour, c.hour), h2 = Math.max(a.hour, c.hour)
  return a.date === dateKey && hour >= h1 && hour <= h2
}

function selectStart(dateKey, hour) {
  selAnchor.value = { date: dateKey, hour }
  selCursor.value = { date: dateKey, hour }
}
function selectOver(dateKey, hour) {
  if (selAnchor.value) selCursor.value = { date: dateKey, hour }
}
function selectEnd() {
  const a = selAnchor.value, c = selCursor.value
  selAnchor.value = null
  selCursor.value = null
  if (!a || !c) return
  // 仅同一天支持连选成课；单格点击 = 直接排课
  const h1 = Math.min(a.hour, c.hour), h2 = Math.max(a.hour, c.hour)
  if (a.date !== c.date) return
  // 分钟级预检：存在重叠时不硬拦截，仅提示冲突课程（后端保存时仍会精确校验 409），
  // 方便老师把新课排进同一小时的空闲部分
  const sMin = h1 * 60, eMin = (h2 + 1) * 60
  const clash = (courses.value).find(o => {
    if (o.start_time.slice(0, 10) !== a.date) return false
    const [sh, sm] = o.start_time.slice(11, 16).split(':').map(Number)
    const so = sh * 60 + sm
    let eo = so + 60
    if (o.end_time) {
      const [eh, em] = o.end_time.slice(11, 16).split(':').map(Number)
      eo = eh * 60 + em
    }
    return sMin < eo && so < eMin
  })
  if (clash) {
    ElMessage.warning(clash.is_mine
      ? `提示：所选时段与《${clash.title}》（${fmtTime(clash.start_time)}~${fmtTime(clash.end_time || '')}）重叠，请在下方调整时间避开`
      : `提示：所选时段已有其他老师的课程《${clash.title}》（${clash.teacher_name}），请调整时间避开`)
  }
  Object.assign(dialog, {
    visible: true, id: 0,
    student_id: filterStudent.value || null,  // 查看某学生课表时预选该学生
    title: '', date: a.date,
    start: `${String(h1).padStart(2, '0')}:00`,
    end: `${String(h2 + 1).padStart(2, '0')}:00`,
    location: '', note: '',
  })
  quickHours.value = h2 - h1 + 1
}

// 弹窗内快速加时：从开始时间起 N 小时
function applyQuickHours(n) {
  if (!dialog.start) return
  const [h, m] = dialog.start.split(':').map(Number)
  const end = new Date(2000, 0, 1, h + n, m)
  const p = x => String(x).padStart(2, '0')
  dialog.end = `${p(end.getHours())}:${p(end.getMinutes())}`
}

function getMonday(d) {
  const dt = new Date(d)
  const day = dt.getDay() || 7
  dt.setDate(dt.getDate() - day + 1)
  dt.setHours(0, 0, 0, 0)
  return dt
}
function fmtDate(d) {
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
const weekLabel = computed(() => `${fmtDate(weekStart.value)} ~ ${fmtDate(new Date(weekStart.value.getTime() + 6 * 86400000))}`)

const weekDays = computed(() => {
  const names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const today = fmtDate(new Date())
  return names.map((label, i) => {
    const d = new Date(weekStart.value.getTime() + i * 86400000)
    return { label, key: fmtDate(d), md: `${d.getMonth() + 1}/${d.getDate()}`, isToday: fmtDate(d) === today }
  })
})

function shiftWeek(n) {
  const d = new Date(weekStart.value)
  d.setDate(d.getDate() + n * 7)
  weekStart.value = d
  load()
}
function goThisWeek() {
  weekStart.value = getMonday(new Date())
  selectedDay.value = Math.max(0, (new Date().getDay() || 7) - 1)
  load()
}

// 回到自己的课表（清除学生筛选）
function backToMine() {
  filterStudent.value = null
  load()
}

// 某一天的课程：解析为分钟区间（供按比例绝对定位），裁剪掉可见范围之外的部分
function coursesOf(dayKey) {
  const first = hours[0] * 60
  const last = (hours[hours.length - 1] + 1) * 60
  return courses.value
    .filter(c => c.start_time.slice(0, 10) === dayKey)
    .map(c => {
      const [sh, sm] = c.start_time.slice(11, 16).split(':').map(Number)
      const startMin = sh * 60 + sm
      let endMin = startMin + 60
      if (c.end_time) {
        const [eh, em] = c.end_time.slice(11, 16).split(':').map(Number)
        endMin = eh * 60 + em
        if (endMin <= startMin) endMin = startMin + 60  // 结束时间异常时兜底
      }
      return { ...c, _startMin: startMin, _endMin: endMin, _color: colorOf(c.student_id) }
    })
    .filter(c => c._startMin < last && c._endMin > first)
}

// 课程块样式：top/height 按分钟比例计算（一小时 = 64px 行高 + 4px 间距）
function blockStyle(c) {
  const past = isPast(c)
  const first = hours[0] * 60
  const last = (hours[hours.length - 1] + 1) * 60
  const ROW = 68  // 行高64 + 间距4
  const top = (Math.max(c._startMin, first) - first) / 60 * ROW + 2
  const h = Math.max(26, (Math.min(c._endMin, last) - Math.max(c._startMin, first)) / 60 * ROW - 8)
  return {
    top: `${top}px`,
    height: `${h}px`,
    background: (past || !c.is_mine) ? '#f4f4f5' : c._color.bg,
    borderLeftColor: (past || !c.is_mine) ? '#c0c4cc' : c._color.bd,
  }
}
function isPast(c) {
  return new Date(c.start_time.replace('T', ' ')) < new Date()
}
function fmtTime(s) {
  return s ? s.slice(11, 16) : ''
}

async function load() {
  loading.value = true
  try {
    const start = fmtDate(weekStart.value)
    const end = fmtDate(new Date(weekStart.value.getTime() + 7 * 86400000))
    const params = { start: `${start} 00:00`, end: `${end} 00:00` }
    if (filterStudent.value) {
      // 学生视图：展示该学生全部课程（其他老师的课灰色只读）
      courses.value = await api.get('/courses', { params: { ...params, student_id: filterStudent.value } })
    } else {
      courses.value = await api.get('/courses', { params })
    }
  } finally {
    loading.value = false
  }
}

function openEdit(c) {
  Object.assign(dialog, {
    visible: true, id: c.id, student_id: c.student_id, title: c.title,
    date: c.start_time.slice(0, 10), start: fmtTime(c.start_time),
    end: c.end_time ? fmtTime(c.end_time) : '', location: c.location, note: c.note,
  })
}

async function save() {
  if (!dialog.student_id) return ElMessage.warning('请选择学生')
  if (!dialog.title.trim()) return ElMessage.warning('请填写课程名称')
  if (!dialog.date) return ElMessage.warning('请选择日期')
  if (!dialog.start) return ElMessage.warning('请选择开始时间')
  saving.value = true
  try {
    const body = {
      student_id: dialog.student_id,
      title: dialog.title.trim(),
      start_time: `${dialog.date} ${dialog.start}`,
      end_time: dialog.end ? `${dialog.date} ${dialog.end}` : null,
      location: dialog.location,
      note: dialog.note,
    }
    if (dialog.id) await api.put(`/courses/${dialog.id}`, body)
    else await api.post('/courses', body)
    ElMessage.success('保存成功')
    dialog.visible = false
    load()
  } finally {
    saving.value = false
  }
}

async function removeCourse(c) {
  await api.delete(`/courses/${c.id}`)
  ElMessage.success('已删除')
  load()
}

function openFeedback(c) {
  fbDialog.course = c
  fbDialog.content = ''
  fbDialog.visible = true
}

// AI 润色：校验后转入后台生成，完成后回填编辑框供教师确认；期间可继续手动编辑
async function polishFeedback() {
  if (!fbDialog.content.trim()) return ElMessage.warning('请先填写反馈要点')
  if (polishing.value) return
  // 统一 AI 前置校验（useAiReady）
  if (!(await ensureAiReady())) return
  polishing.value = true
  const snapshot = fbDialog.content  // 记录提交时的要点
  // 后台执行：不阻塞弹窗，教师可继续编辑；完成后回填
  api.post('/courses/feedback/polish', { content: snapshot })
    .then(data => {
      fbDialog.content = data.content
      ElMessage.success('AI 润色完成，已回填编辑框，请检查修改后再保存')
    })
    .catch(() => { /* 错误已由拦截器弹出提示 */ })
    .finally(() => { polishing.value = false })
}

async function saveFeedback() {
  if (!fbDialog.content.trim()) return ElMessage.warning('请填写反馈内容')
  fbSaving.value = true
  try {
    const updated = await api.post(`/courses/${fbDialog.course.id}/feedback`, { content: fbDialog.content.trim() })
    ElMessage.success('反馈已保存')
    fbDialog.course = updated
    fbDialog.content = ''
    load()
  } finally {
    fbSaving.value = false
  }
}

async function removeFeedback(f) {
  await api.delete(`/courses/feedback/${f.id}`)
  ElMessage.success('已删除')
  const updated = courses.value.find(c => c.id === f.course_id)
  if (updated) fbDialog.course = updated
  load()
}

onMounted(async () => {
  students.value = await api.get('/students')
  load()
})
// 课程反馈被学生回复、课表变动（多端同步）→ 自动刷新
useRealtime(['course', 'student'], async () => {
  students.value = await api.get('/students')
  load()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}
.week-label { min-width: 200px; text-align: center; }
.spacer { flex: 1; }
.hint { color: #999; font-size: 12px; margin-top: 10px; }

/* 手机端：星期切换条 + 当日课程卡片 */
.day-chips {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 4px;
  margin-bottom: 12px;
}
.day-chip {
  flex: 1 0 44px;
  text-align: center;
  padding: 8px 0 6px;
  border-radius: 8px;
  background: #f5f7fa;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid transparent;
}
.day-chip .chip-md { display: block; color: #999; font-size: 11px; margin-top: 2px; }
.day-chip.today { border-color: #a0cfff; background: #ecf5ff; }
.day-chip.active { background: #409eff; color: #fff; }
.day-chip.active .chip-md { color: rgba(255, 255, 255, 0.85); }
.m-course {
  margin-bottom: 10px;
  border-left: 3px solid #409eff;
}
.m-course.past { opacity: 0.75; }
.m-course-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.m-course-time { color: #666; font-size: 13px; margin: 6px 0 0; }
.m-course-note { color: #999; font-size: 12px; margin: 4px 0 0; white-space: pre-wrap; }
.m-course-ops {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.grid-wrap { overflow-x: auto; }
.grid {
  display: grid;
  grid-template-columns: 56px repeat(7, minmax(110px, 1fr));
  gap: 4px;
  align-items: start;
  min-width: 840px;
}
.grid.mobile {
  grid-template-columns: 48px repeat(7, minmax(150px, 1fr));
  min-width: 1100px;
}
.head-cell {
  text-align: center;
  font-weight: 600;
  padding: 6px 0;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 13px;
}
.head-cell .md { color: #999; font-weight: 400; font-size: 12px; }
.head-cell.today { background: #ecf5ff; }
.corner-cell { background: transparent; }

/* 小时刻度列：每行 64px + 4px 间距，与课程块定位公式保持一致 */
.hour-col {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hour-cell {
  height: 64px;
  font-size: 12px;
  color: #888;
  text-align: right;
  padding: 4px 6px 0 0;
}

/* 每天一列：内含空白格与按分钟比例绝对定位的课程块 */
.day-col {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-radius: 6px;
}
.day-col.today .slot-cell { background: #ecf5ff; border-color: #a0cfff; }
.slot-cell {
  height: 64px;
  background: #fafbfc;
  border: 1px dashed #e4e7ed;
  border-radius: 6px;
  user-select: none;
  cursor: crosshair;
}
.slot-cell.today { border-color: #a0cfff; }
.slot-cell.selecting { background: #d9ecff; border-color: #409eff; }
.course-block {
  position: absolute;
  left: 3px;
  right: 3px;
  z-index: 2;
  background: #e6f4ff; /* 占位色，实际由 blockStyle 内联覆盖 */
  border-left: 3px solid #409eff;
  border-radius: 4px;
  padding: 3px 6px;
  cursor: pointer;
  font-size: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.course-block:hover { box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15); }

/* 其他老师排的课程：灰色只读样式，不可点击 */
.course-block.others,
.m-course.others {
  border-style: dashed;
  cursor: default;
  opacity: 0.85;
}
.course-block.others:hover { box-shadow: none; }
.c-title { display: block; font-size: 12px; }
.c-meta { color: #888; margin-top: 2px; }
.c-ops { display: flex; gap: 2px; margin-top: 2px; }
.fb-item {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
}
.fb-head { display: flex; align-items: center; gap: 8px; }
.fb-time { color: #999; font-size: 12px; flex: 1; }
.fb-content {
  margin: 6px 0 0;
  padding: 8px;
  background: #f7f8fa;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
}
.fb-reply { margin-top: 8px; }
.fb-reply .fb-content { background: #f0f9eb; }
</style>
