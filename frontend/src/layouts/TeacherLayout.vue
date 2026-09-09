<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">Teacher-Mi 教师端</div>
      <el-menu :default-active="$route.path" router background-color="#001529" text-color="#bfcbd9"
               active-text-color="#409eff">
        <el-menu-item index="/teacher/students">
          <el-icon><User /></el-icon><span>学生管理</span>
        </el-menu-item>
        <el-menu-item index="/teacher/assignments">
          <el-icon><Notebook /></el-icon><span>作业管理</span>
        </el-menu-item>
        <el-menu-item index="/teacher/grading">
          <el-icon><EditPen /></el-icon><span>批改与反馈</span>
        </el-menu-item>
        <el-menu-item index="/teacher/worksheets">
          <el-icon><MagicStick /></el-icon><span>个性化练习</span>
        </el-menu-item>
        <el-menu-item index="/teacher/schedule">
          <el-icon><Calendar /></el-icon><span>排课管理</span>
        </el-menu-item>
        <el-menu-item index="/teacher/ai-settings">
          <el-icon><Setting /></el-icon><span>AI 设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span>{{ auth.realName || auth.username }}</span>
        <el-button link type="primary" @click="pwdDialog.open()">修改密码</el-button>
        <el-button link type="danger" @click="onLogout">退出登录</el-button>
      </el-header>
      <el-main><router-view /></el-main>
    </el-container>

    <ChangePassword ref="pwdDialog" />
    <TaskMonitor />
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'
import { Calendar } from '@element-plus/icons-vue'
import ChangePassword from '../components/ChangePassword.vue'
import TaskMonitor from '../components/TaskMonitor.vue'

const router = useRouter()
const auth = useAuthStore()
const pwdDialog = ref(null)

function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #001529; }
.logo {
  color: #fff;
  text-align: center;
  line-height: 60px;
  font-weight: bold;
}
.aside .el-menu { border-right: none; }
.header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}
</style>
