<template>
  <div class="settings-grid">
    <el-card class="settings-card">
      <template #header>{{ isAdmin ? 'AI 模型配置（全体教师默认配置）' : 'AI 模型配置' }}</template>
      <el-alert v-if="isAdmin" type="info" show-icon :closable="false" style="margin-bottom: 12px"
                title="此配置为全体教师的默认配置；教师未自行配置时自动使用该配置。" />
      <el-alert v-else type="info" show-icon :closable="false" style="margin-bottom: 12px"
                title="此处配置您自己的 AI 模型；未配置时自动使用管理员的默认配置。" />
      <el-form :model="form" label-width="110px">
        <el-form-item label="启用 AI 功能">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="接口地址">
          <el-input v-model="form.base_url" placeholder="如 https://api.deepseek.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" show-password
                    :placeholder="config.api_key_set ? '已保存（留空则不修改）' : '请输入 API Key'" />
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input v-model="form.model" placeholder="如 deepseek-chat / qwen-plus / gpt-4o-mini" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
          <el-button :loading="testing" @click="test">测试连通性</el-button>
        </el-form-item>
        <el-alert v-if="testResult" :title="testResult" :type="testOk ? 'success' : 'error'" show-icon :closable="false" />
      </el-form>
    </el-card>

    <el-card v-if="isAdmin" class="settings-card">
      <template #header>PushPlus 消息推送（微信）</template>
      <el-form :model="pushForm" label-width="110px">
        <el-form-item label="发送方 Token">
          <el-input v-model="pushForm.token" type="password" show-password
                    :placeholder="pushConfig.token_set ? '已保存（留空则不修改）' : '管理员的 PushPlus Token，作为全站统一发送身份'" />
        </el-form-item>
        <el-form-item label="我的好友令牌">
          <el-input v-model="pushForm.my_token" type="password" show-password
                    :placeholder="pushConfig.my_token_set ? '已保存（留空则不修改）' : '管理员接收推送用的好友令牌（to）'" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingPush" @click="savePush">保存配置</el-button>
          <el-button :loading="testingPush" @click="testPush">发送测试消息</el-button>
        </el-form-item>
        <el-alert type="info" show-icon :closable="false" style="margin-top: 6px"
                  title="所有消息统一通过此发送方 Token 推送（pushplus.plus → 一对一推送获取）。教师与学生的好友令牌由管理员在「教师管理」「学生管理」中统一维护，教师无需也无法自行配置。" />
      </el-form>
    </el-card>

    <el-card v-if="isAdmin" class="settings-card">
      <template #header>预置科目配置</template>
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px"
                title="教师「任教科目」下拉与学生绑定均从此处读取，统一科目口径，避免按科目划拨数据时匹配不上。" />
      <div class="subject-tags">
        <el-tag v-for="(s, i) in subjectForm.list" :key="s" closable size="large"
                @close="subjectForm.list.splice(i, 1)">{{ s }}</el-tag>
        <el-input v-if="subjectForm.inputVisible" ref="subjectInputRef" v-model="subjectForm.input"
                  size="small" style="width: 100px" @keyup.enter="addSubject" @blur="addSubject" />
        <el-button v-else size="small" @click="showSubjectInput">+ 添加科目</el-button>
      </div>
      <div style="margin-top: 14px">
        <el-button type="primary" :loading="savingSubjects" @click="saveSubjects">保存科目</el-button>
        <el-button @click="loadSubjects">重置</el-button>
      </div>
    </el-card>

    <el-card v-if="isAdmin" class="settings-card">
      <template #header>消息推送（全员通知）</template>
      <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px"
                title="通过上方发送方 Token 推送微信通知，接收人为教师/学生在账号管理中维护的好友令牌。" />
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

    <el-card class="settings-card">
      <template #header>{{ isAdmin ? '存储管理（全站）' : '存储管理（我名下）' }}</template>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="总占用">{{ fmtSize(storage.total_size) }}（{{ storage.total_count }} 个文件）</el-descriptions-item>
        <el-descriptions-item v-for="(c, label) in storage.categories" :key="label" :label="label">
          {{ c.count ? `${c.count} 个 · ${fmtSize(c.size)}` : '无' }}
        </el-descriptions-item>
        <el-descriptions-item v-if="!storage.mine_only" label="未引用文件">
          <span :class="storage.orphans.length ? 'warn-text' : ''">
            {{ storage.orphans.length ? `${storage.orphans.length} 个 · ${fmtSize(storage.orphan_size)}` : '无，很干净' }}
          </span>
        </el-descriptions-item>
      </el-descriptions>
      <template v-if="!storage.mine_only">
        <el-alert v-if="storage.missing_count" type="warning" show-icon :closable="false" style="margin-top: 10px"
                  :title="`有 ${storage.missing_count} 条记录引用的文件已丢失（可能被手动删除），不影响其他功能`" />
        <el-alert v-else type="info" show-icon :closable="false" style="margin-top: 10px"
                  title="清理仅删除数据库中没有任何记录引用的孤儿文件（如编辑/删除练习后遗留的旧 PDF），正常业务文件不受影响" />
      </template>
      <el-alert v-else type="info" show-icon :closable="false" style="margin-top: 10px"
                title="统计的是由您下发的作业、学生提交与批改反馈所占用的存储空间；各人员之间相互隔离。" />
      <div style="margin-top: 12px">
        <el-button :loading="loadingStorage" @click="loadStorage">刷新统计</el-button>
        <el-button v-if="!storage.mine_only" type="danger" :loading="cleaning"
                   :disabled="!storage.orphans.length" @click="cleanup">
          清理未引用文件
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'
import { useAuthStore } from '../../store/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.role === 'admin')

const config = reactive({ api_key_set: false })
const form = reactive({ base_url: '', api_key: '', model: '', enabled: false })
const saving = ref(false)
const testing = ref(false)
const testResult = ref('')
const testOk = ref(false)

const storage = reactive({ total_size: 0, total_count: 0, categories: {}, orphans: [], orphan_size: 0, missing_count: 0, mine_only: false })
const loadingStorage = ref(false)
const cleaning = ref(false)

const pushConfig = reactive({ token_set: false, my_token_set: false })
const pushForm = reactive({ token: '', my_token: '' })
const savingPush = ref(false)
const testingPush = ref(false)

const subjectForm = reactive({ list: [], input: '', inputVisible: false })
const subjectInputRef = ref(null)
const savingSubjects = ref(false)

const broadcast = reactive({
  form: { audience: 'all', title: '', content: '' },
  sending: false,
})

function fmtSize(n) {
  if (!n) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++ }
  return `${n.toFixed(n >= 100 || i === 0 ? 0 : 1)} ${units[i]}`
}

async function load() {
  const data = await api.get('/ai/config')
  Object.assign(config, { api_key_set: data.api_key_set })
  Object.assign(form, { base_url: data.base_url, api_key: '', model: data.model, enabled: data.enabled })
}

async function save() {
  saving.value = true
  try {
    await api.put('/ai/config', form)
    ElMessage.success('配置已保存')
    load()
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  testResult.value = ''
  try {
    const data = await api.post('/ai/test', { ...form })
    testOk.value = true
    testResult.value = `连接成功，模型回复：${data.reply}`
  } finally {
    testing.value = false
  }
}

async function loadStorage() {
  loadingStorage.value = true
  try {
    Object.assign(storage, await api.get('/storage/stats'))
  } finally {
    loadingStorage.value = false
  }
}

async function cleanup() {
  try {
    await ElMessageBox.confirm(
      `将删除 ${storage.orphans.length} 个未引用文件，释放 ${fmtSize(storage.orphan_size)}，不可恢复。确定清理？`,
      '清理未引用文件', { type: 'warning', confirmButtonText: '清理', cancelButtonText: '取消' })
  } catch {
    return
  }
  cleaning.value = true
  try {
    const data = await api.post('/storage/cleanup')
    ElMessage.success(`已清理 ${data.removed} 个文件，释放 ${fmtSize(data.freed)}`)
    loadStorage()
  } finally {
    cleaning.value = false
  }
}

async function loadPush() {
  if (!isAdmin.value) return
  const data = await api.get('/settings/pushplus')
  Object.assign(pushConfig, data)
  pushForm.token = ''
  pushForm.my_token = ''
}

async function savePush() {
  savingPush.value = true
  try {
    const data = await api.put('/settings/pushplus', pushForm)
    Object.assign(pushConfig, data)
    pushForm.token = ''
    pushForm.my_token = ''
    ElMessage.success('推送配置已保存')
  } finally {
    savingPush.value = false
  }
}

async function testPush() {
  testingPush.value = true
  try {
    await api.post('/settings/pushplus/test')
    ElMessage.success('测试消息已发送，请在微信中查收')
  } finally {
    testingPush.value = false
  }
}

async function loadSubjects() {
  if (!isAdmin.value) return
  subjectForm.list = await api.get('/settings/subjects')
}

function showSubjectInput() {
  subjectForm.inputVisible = true
  nextTick(() => subjectInputRef.value?.focus())
}

function addSubject() {
  const s = subjectForm.input.trim()
  if (s && !subjectForm.list.includes(s)) subjectForm.list.push(s)
  subjectForm.input = ''
  subjectForm.inputVisible = false
}

async function saveSubjects() {
  if (!subjectForm.list.length) {
    ElMessage.warning('预置科目不能为空')
    return
  }
  savingSubjects.value = true
  try {
    subjectForm.list = await api.put('/settings/subjects', { subjects: subjectForm.list })
    ElMessage.success('预置科目已保存')
  } finally {
    savingSubjects.value = false
  }
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

onMounted(() => { load(); loadStorage(); loadPush(); loadSubjects() })
</script>

<style scoped>
.warn-text { color: var(--el-color-danger); }
.subject-tags { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
/* 设置模块左右横排：固定两列等宽，同行卡片等高 */
.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.settings-card { height: 100%; }
@media (max-width: 1200px) {
  .settings-grid { grid-template-columns: 1fr; }
}
</style>
