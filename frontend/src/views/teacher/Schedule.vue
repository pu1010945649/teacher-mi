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
      <el-button type="primary" size="small" @click="openAdd">
        <el-icon><Plus /></el-icon>&nbsp;排课
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
                   :class="{ past: isPast(c) }" :style="{ borderLeftColor: isPast(c) ? '#c0c4cc' : colorOf(c.student_id).bd }"
                   @click="openFeedback(c)">
            <div class="m-course-head">
              <b>{{ c.title }}</b>
              <el-tag v-if="c.feedbacks?.length" type="success" size="small">有反馈</el-tag>
            </div>
            <p class="m-course-time">
              {{ fmtTime(c.start_time) }}<template v-if="c.end_time"> ~ {{ fmtTime(c.end_time) }}</template>
              · {{ c.student_name }}
              <template v-if="c.location"> · {{ c.location }}</template>
            </p>
            <p v-if="c.note" class="m-course-note">{{ c.note }}</p>
            <div class="m-course-ops" @click.stop>
              <el-button size="small" type="primary" plain @click="openEdit(c)">编辑课程</el-button>
              <el-popconfirm title="确定删除该课程？" @confirm="removeCourse(c)">
                <template #reference>
                  <el-button size="small" type="danger" plain>删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </el-card>
        </template>
        <el-empty v-else description="当天暂无课程" :image-size="80" />
      </div>
      <div class="hint" style="margin-top: 10px">
        提示：点课程卡片录入反馈；手机排课请点右上「排课」按钮
      </div>
    </template>

    <!-- 桌面端：周视图网格（课程块跨行合并） -->
    <div v-else v-loading="loading" class="grid-wrap">
      <div class="grid" :class="{ mobile: isMobile }">
        <!-- 表头：日期 -->
        <div class="corner-cell"></div>
        <div v-for="(day, di) in weekDays" :key="day.key" class="head-cell"
             :class="{ today: day.isToday }" :style="{ gridColumn: di + 2, gridRow: 1 }">
          {{ day.label }}<br /><span class="md">{{ day.md }}</span>
        </div>

        <!-- 小时刻度 + 空白时段格（供点选排课） -->
        <template v-for="(hour, hi) in hours" :key="hour">
          <div class="hour-cell" :style="{ gridRow: hi + 2, gridColumn: 1 }">{{ hour }}:00</div>
          <div v-for="(day, di) in weekDays" :key="day.key + hour" class="slot-cell"
               :style="{ gridRow: hi + 2, gridColumn: di + 2 }"
               :class="{ today: day.isToday, selecting: isSelecting(day.key, hour) }"
               @mousedown="selectStart(day.key, hour)"
               @mouseenter="selectOver(day.key, hour)"
               @mouseup="selectEnd()" />
        </template>

        <!-- 课程块：跨多个小时行合并显示 -->
        <div v-for="c in placedCourses" :key="c.id" class="course-block"
             :class="{ past: isPast(c) }" :style="blockStyle(c)"
             @mousedown.stop @click.stop="openFeedback(c)">
          <b class="c-title">{{ c.title }}</b>
          <div class="c-meta">{{ fmtTime(c.start_time) }}<template v-if="c.end_time">~{{ fmtTime(c.end_time) }}</template> · {{ c.student_name }}</div>
          <div class="c-ops" @click.stop>
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
    <p class="hint">提示：点击空白时段开始选课，按住拖动或依次点击可选连续多个小时（如两节课连上）；再次单格点击或点击有课格可重选；点击课程卡片录入学习反馈</p>

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
import { Plus } from '@element-plus/icons-vue'
import api from '../../api'
import { useRealtime } from '../../realtime'
import { useIsMobile } from '../../composables/useIsMobile'

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
  Object.assign(dialog, {
    visible: true, id: 0, student_id: null, title: '', date: a.date,
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

// 课程块位置：计算每个课程在网格中的列、起始行与跨行数（跨多小时合并为一个块）
const placedCourses = computed(() => {
  const dayKeys = weekDays.value.map(d => d.key)
  const first = hours[0], last = hours[hours.length - 1]
  return courses.value.map(c => {
    const dateKey = c.start_time.slice(0, 10)
    const di = dayKeys.indexOf(dateKey)
    if (di < 0) return null
    const [sh, sm] = c.start_time.slice(11, 16).split(':').map(Number)
    const startMin = sh * 60 + sm
    let endMin = startMin + 60
    if (c.end_time) {
      const [eh, em] = c.end_time.slice(11, 16).split(':').map(Number)
      endMin = eh * 60 + em
      if (endMin <= startMin) endMin = startMin + 60  // 结束时间异常时兜底
    }
    // 裁剪到可见小时范围（8:00 ~ 21:00）
    const rowStart = Math.max(Math.floor(startMin / 60), first) - first
    let span = Math.ceil(Math.min(endMin / 60, last + 1)) - Math.max(Math.floor(startMin / 60), first)
    span = Math.max(1, Math.min(span, hours.length - rowStart))
    return { ...c, _col: di + 2, _row: rowStart + 2, _span: span, _color: colorOf(c.student_id) }
  }).filter(Boolean)
})

function blockStyle(c) {
  const past = isPast(c)
  return {
    gridColumn: c._col,
    gridRow: `${c._row} / span ${c._span}`,
    background: past ? '#f4f4f5' : c._color.bg,
    borderLeftColor: past ? '#c0c4cc' : c._color.bd,
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
    if (filterStudent.value) params.student_id = filterStudent.value
    courses.value = await api.get('/courses', { params })
  } finally {
    loading.value = false
  }
}

function openAdd() {
  Object.assign(dialog, { visible: true, id: 0, student_id: null, title: '', date: fmtDate(new Date()), start: '', end: '', location: '', note: '' })
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
  // 先校验 AI 是否已配置启用
  const cfg = await api.get('/ai/config')
  if (!cfg.enabled || !cfg.api_key_set || !cfg.base_url || !cfg.model) {
    ElMessage.warning('AI 模型未配置或未启用，请先在「AI 设置」中完成配置')
    return
  }
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
  grid-template-rows: auto repeat(14, minmax(64px, auto));
  gap: 4px;
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
.head-cell.today, .slot-cell.today { background: #ecf5ff; }
.corner-cell { background: transparent; }
.hour-cell {
  font-size: 12px;
  color: #888;
  text-align: right;
  padding: 4px 6px 0 0;
}
.slot-cell {
  background: #fafbfc;
  border: 1px dashed #e4e7ed;
  border-radius: 6px;
  min-height: 64px;
  padding: 3px;
  user-select: none;
  cursor: crosshair;
}
.slot-cell.today { border-color: #a0cfff; }
.slot-cell.selecting { background: #d9ecff; border-color: #409eff; }
.course-block {
  background: #e6f4ff; /* 占位色，实际由 blockStyle 内联覆盖 */
  border-left: 3px solid #409eff;
  border-radius: 4px;
  padding: 4px 6px;
  cursor: pointer;
  font-size: 12px;
  z-index: 2;
  height: calc(100% - 4px);
  margin: 2px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.course-block:hover { box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15); }
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
