<template>
  <div class="settings-grid">
    <el-card class="settings-card">
      <template #header>{{ isAdmin ? 'AI 模型配置（全体教师默认配置）' : 'AI 模型配置' }}</template>
      <el-alert v-if="isAdmin" type="info" show-icon :closable="false" style="margin-bottom: 12px"
                title="此配置为全体教师的默认配置；教师未自行配置时自动使用该配置。" />
      <el-alert v-else type="info" show-icon :closable="false" style="margin-bottom: 12px"
                title="「启用 AI 功能」是所有 AI 功能的总开关；开启后优先使用您自己的模型，未配置时若管理员已开放权限并启用了默认模型，将自动使用管理员的模型。" />
      <el-form :model="form" label-width="110px">
        <el-form-item label="启用 AI 功能">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="接口地址">
          <el-input v-model="form.base_url" placeholder="如 https://api.deepseek.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" show-password
                    placeholder="请输入 API Key（清空后保存即删除配置）" />
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
                    placeholder="管理员的 PushPlus Token，作为全站统一发送身份（清空后保存即删除）" />
        </el-form-item>
        <el-form-item label="我的好友令牌">
          <el-input v-model="pushForm.my_token" type="password" show-password
                    placeholder="管理员接收推送用的好友令牌（to）（清空后保存即删除）" />
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
      <template #header>对象存储（可选，默认本地）</template>
      <el-form :model="ossForm" label-width="110px">
        <el-form-item label="存储模式">
          <el-radio-group v-model="ossForm.backend">
            <el-radio value="local">本地磁盘（默认）</el-radio>
            <el-radio value="oss">对象存储（S3兼容）</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="ossForm.backend === 'oss'">
          <el-form-item label="Endpoint">
            <el-input v-model="ossForm.endpoint" placeholder="如 https://oss-cn-hangzhou.aliyuncs.com" />
          </el-form-item>
          <el-form-item label="Bucket">
            <el-input v-model="ossForm.bucket" placeholder="桶名（私有读写）" />
          </el-form-item>
          <el-form-item label="AccessKey">
            <el-input v-model="ossForm.access_key" placeholder="RAM 子账号 AccessKeyId（最小权限）" />
          </el-form-item>
          <el-form-item label="SecretKey">
            <el-input v-model="ossForm.secret_key" type="password" show-password
                      :placeholder="ossConfig.secret_set ? '已保存（留空则不修改）' : 'AccessKeySecret'" />
          </el-form-item>
        </template>
        <el-form-item>
          <el-button type="primary" :loading="savingOss" @click="saveOss">保存配置</el-button>
          <el-button v-if="ossForm.backend === 'oss'" :loading="testingOss" @click="testOss">测试连接</el-button>
          <el-button v-if="ossForm.backend === 'oss'" :loading="migrateState.running" @click="startMigrate">
            {{ migrateState.running ? '迁移中…' : '一键迁移历史数据' }}
          </el-button>
        </el-form-item>
        <el-alert v-if="ossForm.backend === 'oss' && migrateState.running" type="warning" show-icon
                  :closable="false" style="margin-top: 6px"
                  :title="`迁移进行中：共 ${migrateState.total} 个文件，已上传 ${migrateState.done}，跳过 ${migrateState.skipped}（本地文件保留不删除），请勿关闭后端服务`" />
        <el-alert v-else-if="ossForm.backend === 'oss' && migrateState.finished" :type="migrateState.failed ? 'error' : 'success'"
                  show-icon :closable="false" style="margin-top: 6px"
                  :title="`迁移结束：新上传 ${migrateState.done}，已存在跳过 ${migrateState.skipped}，失败 ${migrateState.failed}${migrateState.failed ? '（可重新点击迁移按钮续传）' : ''}`" />
        <el-alert type="info" show-icon :closable="false" style="margin-top: 6px"
                  title="默认使用服务器本地磁盘存储，无需配置。切换到对象存储后，新上传的附件与讲解视频将存到云端：播放/下载经鉴权后 302 跳转签名直链（10 分钟有效），不占用服务器带宽。兼容阿里云 OSS、腾讯云 COS、MinIO 等一切 S3 兼容端点。切换前请先「测试连接」并「一键迁移历史数据」，迁移只上传不删除，本地文件保留作回退副本。" />
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
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
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

const pushConfig = reactive({ token_set: false, my_token_set: false, token_mask: '', my_token_mask: '' })
const pushForm = reactive({ token: '', my_token: '' })
const savingPush = ref(false)
const testingPush = ref(false)

const ossConfig = reactive({ secret_set: false })
const ossForm = reactive({ backend: 'local', endpoint: '', bucket: '', access_key: '', secret_key: '' })
const savingOss = ref(false)
const testingOss = ref(false)
const migrateState = reactive({ running: false, total: 0, done: 0, skipped: 0, failed: 0, finished: false, errors: [] })
let migrateTimer = null

async function loadOss() {
  if (!isAdmin.value) return
  const data = await api.get('/settings/storage')
  Object.assign(ossConfig, { secret_set: data.secret_set })
  Object.assign(ossForm, { backend: data.backend, endpoint: data.endpoint,
    bucket: data.bucket, access_key: data.access_key, secret_key: '' })
  if (data.backend === 'oss') pollMigrate() // 恢复未关闭页面时的迁移进度
}

async function saveOss() {
  savingOss.value = true
  try {
    const data = await api.put('/settings/storage', ossForm)
    Object.assign(ossConfig, { secret_set: data.secret_set })
    ossForm.secret_key = ''
    ElMessage.success('存储配置已保存')
  } finally {
    savingOss.value = false
  }
}

async function testOss() {
  testingOss.value = true
  try {
    await api.post('/settings/storage/test')
    ElMessage.success('连接成功：上传/读取/删除校验均通过')
  } finally {
    testingOss.value = false
  }
}

async function startMigrate() {
  try {
    await ElMessageBox.confirm(
      '将把服务器上的历史文件（作业附件、讲解视频、学生提交、批改标注等）全部上传到对象存储，原文件保留在本地不删除。已迁移过的文件自动跳过，可重复执行。确定开始？',
      '一键迁移历史数据', { type: 'warning', confirmButtonText: '开始迁移', cancelButtonText: '取消' })
  } catch {
    return
  }
  try {
    await api.post('/settings/storage/migrate')
    migrateState.running = true
    migrateState.finished = false
    migrateTimer = setInterval(pollMigrate, 1500)
  } finally { /* 错误由拦截器提示 */ }
}

async function pollMigrate() {
  if (!isAdmin.value) return
  try {
    Object.assign(migrateState, await api.get('/settings/storage/migrate'))
  } catch { return }
  clearInterval(migrateTimer)
  if (migrateState.running) migrateTimer = setInterval(pollMigrate, 1500)
  else if (migrateState.finished) {
    const s = migrateState
    ElMessage[s.failed ? 'warning' : 'success'](
      `迁移结束：新上传 ${s.done}，已存在跳过 ${s.skipped}，失败 ${s.failed}`)
  }
}

onUnmounted(() => clearInterval(migrateTimer))

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
  Object.assign(config, { api_key_set: data.api_key_set, api_key_mask: data.api_key_mask || '' })
  // 已配置时输入框直接显示掩码；掩码回传后端视为未修改，清空保存即删除
  Object.assign(form, { base_url: data.base_url, api_key: data.api_key_mask || '', model: data.model, enabled: data.enabled })
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

function fileListHtml(names) {
  // 文件名做 HTML 转义，防注入
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const items = names.map(n => `<li style="margin:2px 0;word-break:break-all;">${esc(n)}</li>`).join('')
  return `<ul style="max-height:220px;overflow:auto;margin:8px 0 0;padding-left:18px;font-size:12px;">${items}</ul>`
}

async function cleanup() {
  try {
    await ElMessageBox.confirm(
      `将删除 ${storage.orphans.length} 个未引用文件，释放 ${fmtSize(storage.orphan_size)}，不可恢复：${fileListHtml(storage.orphans.map(o => o.name))}`,
      '清理未引用文件', { type: 'warning', confirmButtonText: '清理', cancelButtonText: '取消',
        dangerouslyUseHTMLString: true, customStyle: { maxWidth: '560px' } })
  } catch {
    return
  }
  cleaning.value = true
  try {
    const data = await api.post('/storage/cleanup')
    ElMessageBox.alert(
      `已清理 ${data.removed} 个文件，释放 ${fmtSize(data.freed)}：${fileListHtml(data.removed_names || [])}`,
      '清理完成', { type: 'success', confirmButtonText: '知道了', dangerouslyUseHTMLString: true,
        customStyle: { maxWidth: '560px' } })
    loadStorage()
  } finally {
    cleaning.value = false
  }
}

async function loadPush() {
  if (!isAdmin.value) return
  const data = await api.get('/settings/pushplus')
  Object.assign(pushConfig, data)
  // 已配置时输入框直接显示掩码；掩码回传后端视为未修改，清空保存即删除
  pushForm.token = data.token_mask || ''
  pushForm.my_token = data.my_token_mask || ''
}

async function savePush() {
  savingPush.value = true
  try {
    const data = await api.put('/settings/pushplus', pushForm)
    Object.assign(pushConfig, data)
    pushForm.token = data.token_mask || ''
    pushForm.my_token = data.my_token_mask || ''
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

onMounted(() => { load(); loadStorage(); loadPush(); loadSubjects(); loadOss() })
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
