<template>
  <el-card style="max-width: 640px">
    <template #header>AI 模型配置（OpenAI 兼容接口）</template>
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

  <el-card style="max-width: 640px; margin-top: 16px">
    <template #header>存储管理</template>
    <el-descriptions :column="1" border size="small">
      <el-descriptions-item label="总占用">{{ fmtSize(storage.total_size) }}（{{ storage.total_count }} 个文件）</el-descriptions-item>
      <el-descriptions-item v-for="(c, label) in storage.categories" :key="label" :label="label">
        {{ c.count ? `${c.count} 个 · ${fmtSize(c.size)}` : '无' }}
      </el-descriptions-item>
      <el-descriptions-item label="未引用文件">
        <span :class="storage.orphans.length ? 'warn-text' : ''">
          {{ storage.orphans.length ? `${storage.orphans.length} 个 · ${fmtSize(storage.orphan_size)}` : '无，很干净' }}
        </span>
      </el-descriptions-item>
    </el-descriptions>
    <el-alert v-if="storage.missing_count" type="warning" show-icon :closable="false" style="margin-top: 10px"
              :title="`有 ${storage.missing_count} 条记录引用的文件已丢失（可能被手动删除），不影响其他功能`" />
    <el-alert v-else type="info" show-icon :closable="false" style="margin-top: 10px"
              title="清理仅删除数据库中没有任何记录引用的孤儿文件（如编辑/删除练习后遗留的旧 PDF），正常业务文件不受影响" />
    <div style="margin-top: 12px">
      <el-button :loading="loadingStorage" @click="loadStorage">刷新统计</el-button>
      <el-button type="danger" :loading="cleaning" :disabled="!storage.orphans.length" @click="cleanup">
        清理未引用文件
      </el-button>
    </div>
  </el-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const config = reactive({ api_key_set: false })
const form = reactive({ base_url: '', api_key: '', model: '', enabled: false })
const saving = ref(false)
const testing = ref(false)
const testResult = ref('')
const testOk = ref(false)

const storage = reactive({ total_size: 0, total_count: 0, categories: {}, orphans: [], orphan_size: 0, missing_count: 0 })
const loadingStorage = ref(false)
const cleaning = ref(false)

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

onMounted(() => { load(); loadStorage() })
</script>

<style scoped>
.warn-text { color: var(--el-color-danger); }
</style>
