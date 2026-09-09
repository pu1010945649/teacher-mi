<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2 class="title">Teacher-Mi 智能教学助手</h2>
      <el-form :model="form" @keyup.enter="onLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large">
            <template #prefix><el-icon><User /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" size="large" show-password>
            <template #prefix><el-icon><Lock /></el-icon></template>
          </el-input>
        </el-form-item>
        <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="onLogin">
          登 录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../store/auth'
import { encryptSensitive } from '../api'

const router = useRouter()
const auth = useAuthStore()
const form = ref({ username: '', password: '' })
const loading = ref(false)

async function onLogin() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const encrypted = await encryptSensitive(form.value.password)
    await auth.login(form.value.username, encrypted)
    router.push(auth.isTeacher ? '/teacher' : '/student')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  padding: 0 16px;
}
.login-card {
  width: 380px;
  max-width: 100%;
  padding: 12px 8px;
}
.title {
  text-align: center;
  margin-bottom: 28px;
}
.login-btn {
  width: 100%;
}
</style>
