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
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const config = reactive({ api_key_set: false })
const form = reactive({ base_url: '', api_key: '', model: '', enabled: false })
const saving = ref(false)
const testing = ref(false)
const testResult = ref('')
const testOk = ref(false)

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

onMounted(load)
</script>
