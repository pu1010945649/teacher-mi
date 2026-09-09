<template>
  <el-dialog v-model="visible" title="修改密码" :width="isMobile ? '94%' : '420px'"
             @closed="reset">
    <el-form :model="form" label-width="90px">
      <el-form-item label="原密码">
        <el-input v-model="form.oldPassword" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="form.newPassword" type="password" show-password placeholder="至少 6 位" />
      </el-form-item>
      <el-form-item label="确认新密码">
        <el-input v-model="form.confirm" type="password" show-password />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">确定修改</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { encryptSensitive } from '../api'
import { useIsMobile } from '../composables/useIsMobile'

const router = useRouter()
const { isMobile } = useIsMobile()
const visible = ref(false)
const saving = ref(false)
const form = reactive({ oldPassword: '', newPassword: '', confirm: '' })

function open() {
  reset()
  visible.value = true
}

function reset() {
  form.oldPassword = form.newPassword = form.confirm = ''
}

async function save() {
  if (!form.oldPassword || !form.newPassword) {
    ElMessage.warning('请填写原密码和新密码')
    return
  }
  if (form.newPassword.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (form.newPassword !== form.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  saving.value = true
  try {
    await api.post('/auth/change-password', {
      old_password: await encryptSensitive(form.oldPassword),
      new_password: await encryptSensitive(form.newPassword),
    })
    ElMessage.success('密码修改成功，请重新登录')
    visible.value = false
    setTimeout(() => router.push('/login'), 800)
  } finally {
    saving.value = false
  }
}

defineExpose({ open })
</script>
