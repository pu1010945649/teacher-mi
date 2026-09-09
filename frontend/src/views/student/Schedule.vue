<template>
  <el-card>
    <div class="toolbar">
      <el-radio-group v-model="tab" size="small">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="upcoming">待上课</el-radio-button>
        <el-radio-button value="past">已结束</el-radio-button>
      </el-radio-group>
    </div>
    <el-empty v-if="!showList.length" description="暂无课程" />
    <div v-for="c in showList" :key="c.id" class="course-card">
      <div class="head">
        <b>{{ c.title }}</b>
        <el-tag :type="c.status === 'upcoming' ? 'primary' : 'info'" size="small">
          {{ c.status === 'upcoming' ? '待上课' : '已结束' }}
        </el-tag>
      </div>
      <p class="meta">
        {{ c.start_time?.slice(0, 16).replace('T', ' ') }}
        <template v-if="c.end_time"> ~ {{ fmtTime(c.end_time) }}</template>
        <template v-if="c.location"> · {{ c.location }}</template>
      </p>
      <p v-if="c.note" class="meta note">{{ c.note }}</p>

      <div v-if="c.feedbacks?.length" class="fbs">
        <div v-for="f in c.feedbacks" :key="f.id" class="fb-item">
          <div class="fb-head">
            <b>老师反馈</b>
            <span class="time">{{ f.created_at?.slice(0, 16).replace('T', ' ') }}</span>
          </div>
          <p class="content">{{ f.content }}</p>
          <div v-if="f.reply" class="reply-box">
            <b>我的回复</b>
            <p class="content">{{ f.reply }}</p>
          </div>
          <template v-else>
            <el-input v-model="f._reply" type="textarea" :rows="2" size="small"
                      placeholder="回复老师的反馈…" class="reply-input" />
            <div style="margin-top: 6px; text-align: right">
              <el-button type="primary" size="small" :loading="f._saving" @click="sendReply(c, f)">
                回复
              </el-button>
            </div>
          </template>
        </div>
      </div>
      <p v-else class="meta">老师还未录入本节课反馈</p>
    </div>
  </el-card>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const courses = ref([])
const tab = ref('all')

const showList = computed(() => {
  const d = new Date()
  const p = n => String(n).padStart(2, '0')
  const now = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  return courses.value
    .map(c => ({ ...c, status: c.start_time.replace('T', ' ').slice(0, 19) >= now ? 'upcoming' : 'past' }))
    .filter(c => tab.value === 'all' || c.status === tab.value)
})

function fmtTime(s) {
  return s ? s.slice(11, 16) : ''
}

async function load() {
  courses.value = await api.get('/courses/my')
}

async function sendReply(course, f) {
  if (!f._reply?.trim()) return ElMessage.warning('请填写回复内容')
  f._saving = true
  try {
    const updated = await api.post(`/courses/feedback/${f.id}/reply`, { content: f._reply.trim() })
    const idx = courses.value.findIndex(c => c.id === course.id)
    if (idx >= 0) courses.value[idx] = updated
    ElMessage.success('回复成功')
  } finally {
    f._saving = false
  }
}

onMounted(load)
</script>

<style scoped>
.course-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.meta { color: #888; font-size: 13px; margin: 6px 0 0; }
.meta.note { color: #555; white-space: pre-wrap; }
.fbs { margin-top: 10px; }
.fb-item {
  background: #fafbfc;
  border-radius: 6px;
  padding: 10px;
  margin-top: 8px;
}
.fb-head { display: flex; align-items: center; gap: 8px; }
.time { color: #999; font-size: 12px; }
.content {
  margin: 6px 0 0;
  padding: 8px;
  background: #fff;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
}
.reply-box .content { background: #f0f9eb; }
.reply-input { margin-top: 8px; }
</style>
