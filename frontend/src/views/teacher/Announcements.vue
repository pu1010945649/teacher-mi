<template>
  <div class="settings-grid">
    <el-card class="settings-card">
      <template #header>公告发布（页面顶部展示栏）</template>
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px"
                title="发布后在教师端/学生端页面顶部横幅展示，展示内容始终为最新一条；用户可自行关闭横幅。" />
      <el-form label-width="0" style="max-width: 640px">
        <el-input v-model="content" type="textarea" :rows="4" maxlength="500" show-word-limit
                  placeholder="输入要发布给教师端/学生端的公告内容（发布后自动替换当前公告）" />
        <el-button type="primary" style="margin-top: 10px" :loading="publishing" @click="publish">
          发布公告
        </el-button>
      </el-form>

      <el-table :data="list" border stripe style="margin-top: 18px">
        <el-table-column prop="content" label="公告内容" show-overflow-tooltip />
        <el-table-column prop="created_by_name" label="发布人" width="90" />
        <el-table-column label="发布时间" width="150">
          <template #default="{ row }">{{ row.created_at?.replace('T', ' ').slice(0, 16) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '展示中' : '已关闭' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button link :type="row.is_active ? 'warning' : 'success'" @click="toggle(row)">
              {{ row.is_active ? '关闭展示' : '开启展示' }}
            </el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="settings-card">
      <template #header>消息推送（全员通知，微信）</template>
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px"
                title="通过「后台设置」中的发送方 Token 推送微信通知，接收人为教师/学生在账号管理中维护的好友令牌。" />
      <el-form :model="broadcast.form" label-width="90px">
        <el-form-item label="接收范围">
          <el-radio-group v-model="broadcast.form.audience">
            <el-radio value="all">全部人员</el-radio>
            <el-radio value="teachers">仅教师</el-radio>
            <el-radio value="students">仅学生</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="broadcast.form.title" placeholder="通知标题" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="broadcast.form.content" type="textarea" :rows="4" placeholder="通知内容" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="broadcast.sending" @click="sendBroadcast">发送</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const list = ref([])
const content = ref('')
const publishing = ref(false)

const broadcast = reactive({
  form: { audience: 'all', title: '', content: '' },
  sending: false,
})

async function load() {
  list.value = await api.get('/announcements')
}

async function publish() {
  if (!content.value.trim()) return ElMessage.warning('请输入公告内容')
  publishing.value = true
  try {
    await api.post('/announcements', { content: content.value.trim() })
    ElMessage.success('发布成功，教师端/学生端顶部已展示')
    content.value = ''
    load()
  } finally {
    publishing.value = false
  }
}

async function toggle(row) {
  await api.put(`/announcements/${row.id}/toggle`)
  load()
}

async function remove(row) {
  await ElMessageBox.confirm('确认删除该条公告？', '提示', { type: 'warning' })
  await api.delete(`/announcements/${row.id}`)
  ElMessage.success('已删除')
  load()
}

async function sendBroadcast() {
  if (!broadcast.form.title.trim() || !broadcast.form.content.trim()) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  broadcast.sending = true
  try {
    const res = await api.post('/settings/broadcast', broadcast.form)
    const names = (res.sent_names || []).join('、')
    ElMessageBox.alert(
      names ? `成功推送给 ${res.count} 人：${names}` : `成功推送给 ${res.count} 人`,
      '推送结果', { confirmButtonText: '知道了' })
    broadcast.form.title = ''
    broadcast.form.content = ''
  } finally {
    broadcast.sending = false
  }
}

onMounted(load)
</script>

<style scoped>
.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  align-items: start;
}
.settings-card { height: 100%; }
@media (max-width: 1200px) {
  .settings-grid { grid-template-columns: 1fr; }
}
</style>
