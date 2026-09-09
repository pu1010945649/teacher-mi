<template>
  <el-card>
    <div class="toolbar">
      <el-button size="small" @click="shiftWeek(-1)">上一周</el-button>
      <b class="week-label">{{ weekLabel }}</b>
      <el-button size="small" @click="shiftWeek(1)">下一周</el-button>
      <el-button size="small" link type="primary" @click="goThisWeek">本周</el-button>
    </div>

    <!-- 手机端：按天查看课程列表 -->
    <template v-if="isMobile">
      <div class="day-chips">
        <div v-for="(day, di) in weekDays" :key="day.key" class="day-chip"
             :class="{ active: di === selectedDay, today: day.isToday }" @click="selectedDay = di">
          {{ day.label }}<span class="chip-md">{{ day.md }}</span>
        </div>
      </div>
      <template v-if="dayCourses.length">
        <el-card v-for="c in dayCourses" :key="c.id" class="m-course" shadow="never"
                 :class="{ past: isPast(c) }" @click="openFeedback(c)">
          <div class="m-course-head">
            <b>{{ c.title }}</b>
            <el-tag v-if="hasFeedback(c)" type="success" size="small">有反馈</el-tag>
          </div>
          <p class="m-course-time">
            {{ fmtTime(c.start_time) }}<template v-if="c.end_time"> ~ {{ fmtTime(c.end_time) }}</template>
            <template v-if="c.location"> · {{ c.location }}</template>
          </p>
          <p v-if="c.note" class="m-course-note">{{ c.note }}</p>
        </el-card>
      </template>
      <el-empty v-else description="当天暂无课程" :image-size="80" />
    </template>

    <!-- 桌面端：周视图网格（课程块跨行合并） -->
    <div v-else v-loading="loading" class="grid-wrap">
      <div class="grid">
        <!-- 表头：日期 -->
        <div class="corner-cell"></div>
        <div v-for="(day, di) in weekDays" :key="day.key" class="head-cell"
             :class="{ today: day.isToday }" :style="{ gridColumn: di + 2, gridRow: 1 }">
          {{ day.label }}<br /><span class="md">{{ day.md }}</span>
        </div>

        <!-- 小时刻度 + 空白时段格 -->
        <template v-for="(hour, hi) in hours" :key="hour">
          <div class="hour-cell" :style="{ gridRow: hi + 2, gridColumn: 1 }">{{ hour }}:00</div>
          <div v-for="(day, di) in weekDays" :key="day.key + hour" class="slot-cell"
               :style="{ gridRow: hi + 2, gridColumn: di + 2 }"
               :class="{ today: day.isToday }" />
        </template>

        <!-- 课程块：跨多个小时行合并显示 -->
        <div v-for="c in placedCourses" :key="c.id" class="course-block"
             :class="{ past: isPast(c) }" :style="blockStyle(c)"
             @click="openFeedback(c)">
          <b class="c-title">{{ c.title }}</b>
          <div class="c-meta">{{ fmtTime(c.start_time) }}<template v-if="c.end_time">~{{ fmtTime(c.end_time) }}</template></div>
          <div v-if="c.location" class="c-meta">{{ c.location }}</div>
        </div>
      </div>
    </div>
    <p class="hint">提示：点击课程卡片可查看老师反馈并回复</p>
    <el-empty v-if="!courses.length" description="暂无课程" />

    <!-- 课程反馈弹窗 -->
    <el-dialog v-model="fbDialog.visible" :title="`课程学习反馈 - ${fbDialog.course?.title || ''}`"
               :width="isMobile ? '96%' : '620px'">
      <template v-if="fbDialog.course">
        <el-descriptions :column="isMobile ? 1 : 2" border size="small" style="margin-bottom: 14px">
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
            <b>老师反馈</b>
            <span class="fb-time">{{ f.created_at?.slice(0, 16).replace('T', ' ') }}</span>
          </div>
          <p class="fb-content">{{ f.content }}</p>
          <div v-if="f.reply" class="fb-reply">
            <b>我的回复</b>
            <p class="fb-content">{{ f.reply }}</p>
          </div>
          <template v-else>
            <el-input v-model="fbDialog.content" type="textarea" :rows="2"
                      placeholder="回复老师的反馈…" style="margin-top: 8px" />
            <div style="margin-top: 8px; text-align: right">
              <el-button type="primary" size="small" :loading="fbSaving" @click="sendReply(f)">
                回复
              </el-button>
            </div>
          </template>
        </div>
        <p v-if="!fbDialog.course.feedbacks?.length" class="meta">老师还未录入本节课反馈</p>
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

const { isMobile } = useIsMobile()
const courses = ref([])
const loading = ref(false)
const fbSaving = ref(false)
const fbDialog = reactive({ visible: false, course: null, content: '' })

// 时间表显示 8:00 ~ 21:00
const hours = Array.from({ length: 14 }, (_, i) => i + 8)

const weekStart = ref(getMonday(new Date()))
// 手机端当前查看的星期下标（0=周一），默认定位到今天
const selectedDay = ref(Math.max(0, (new Date().getDay() || 7) - 1))

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
}
function goThisWeek() {
  weekStart.value = getMonday(new Date())
  selectedDay.value = Math.max(0, (new Date().getDay() || 7) - 1)
}

// 手机端：当前选中那天的课程（按开始时间排序）
const dayCourses = computed(() => {
  const key = weekDays.value[selectedDay.value]?.key
  if (!key) return []
  return courses.value
    .filter(c => c.start_time.slice(0, 10) === key)
    .sort((a, b) => a.start_time.localeCompare(b.start_time))
})

function hasFeedback(c) {
  return !!c.feedbacks?.length
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
    return { ...c, _col: di + 2, _row: rowStart + 2, _span: span }
  }).filter(Boolean)
})

function blockStyle(c) {
  return { gridColumn: c._col, gridRow: `${c._row} / span ${c._span}` }
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
    courses.value = await api.get('/courses/my')
  } finally {
    loading.value = false
  }
}

function openFeedback(c) {
  fbDialog.course = c
  fbDialog.content = ''
  fbDialog.visible = true
}

async function sendReply(f) {
  if (!fbDialog.content.trim()) return ElMessage.warning('请填写回复内容')
  fbSaving.value = true
  try {
    const updated = await api.post(`/courses/feedback/${f.id}/reply`, { content: fbDialog.content.trim() })
    const idx = courses.value.findIndex(c => c.id === updated.id)
    if (idx >= 0) courses.value[idx] = updated
    fbDialog.course = updated
    fbDialog.content = ''
    ElMessage.success('回复成功')
  } finally {
    fbSaving.value = false
  }
}

onMounted(load)
// 老师调整课表或课程反馈 → 自动刷新
useRealtime('course', load)
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
.hint { color: #999; font-size: 12px; margin-top: 10px; }
.meta { color: #888; font-size: 13px; }

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
.m-course { margin-bottom: 10px; border-left: 3px solid #409eff; }
.m-course.past { border-left-color: #c0c4cc; opacity: 0.75; }
.m-course-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.m-course-time { color: #666; font-size: 13px; margin: 6px 0 0; }
.m-course-note { color: #999; font-size: 12px; margin: 4px 0 0; white-space: pre-wrap; }

.grid-wrap { overflow-x: auto; }
.grid {
  display: grid;
  grid-template-columns: 56px repeat(7, minmax(110px, 1fr));
  grid-template-rows: auto repeat(14, minmax(64px, auto));
  gap: 4px;
  min-width: 840px;
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
}
.slot-cell.today { background: #ecf5ff; border-color: #a0cfff; }
.course-block {
  background: #e6f4ff;
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
.course-block:hover { box-shadow: 0 2px 6px rgba(64, 158, 255, 0.3); }
.course-block.past { background: #f4f4f5; border-left-color: #c0c4cc; }
.c-title { display: block; font-size: 12px; }
.c-meta { color: #888; margin-top: 2px; }
.fb-item {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
}
.fb-head { display: flex; align-items: center; gap: 8px; }
.fb-time { color: #999; font-size: 12px; }
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
