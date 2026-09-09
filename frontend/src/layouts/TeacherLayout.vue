<template>
  <el-container class="layout">
    <!-- 桌面端侧边栏 -->
    <el-aside v-if="!isMobile" width="220px" class="aside">
      <div class="logo">Teacher-Mi 教师端</div>
      <el-menu :default-active="$route.path" router background-color="#001529" text-color="#bfcbd9"
               active-text-color="#409eff">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon><span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <el-icon v-if="isMobile" class="hamburger" @click="drawerVisible = true"><Menu /></el-icon>
        <span v-if="isMobile" class="header-title">Teacher-Mi 教师端</span>
        <span class="header-user">{{ auth.realName || auth.username }}</span>
        <el-button link type="primary" @click="pwdDialog.open()">修改密码</el-button>
        <el-button link type="danger" @click="onLogout">退出登录</el-button>
      </el-header>
      <el-main><router-view /></el-main>
    </el-container>

    <!-- 手机端抽屉菜单 -->
    <el-drawer v-model="drawerVisible" direction="ltr" size="200px" :with-header="false"
               body-class="drawer-body">
      <div class="logo drawer-logo">Teacher-Mi 教师端</div>
      <el-menu :default-active="$route.path" router background-color="#001529" text-color="#bfcbd9"
               active-text-color="#409eff" @select="drawerVisible = false">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon><span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>

    <ChangePassword ref="pwdDialog" />
    <TaskMonitor />
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'
import {
  Calendar, EditPen, Menu, Notebook, Setting, TrendCharts, User,
} from '@element-plus/icons-vue'
import { useIsMobile } from '../composables/useIsMobile'
import ChangePassword from '../components/ChangePassword.vue'
import TaskMonitor from '../components/TaskMonitor.vue'

const router = useRouter()
const auth = useAuthStore()
const { isMobile } = useIsMobile()
const drawerVisible = ref(false)
const pwdDialog = ref(null)

const menus = [
  { path: '/teacher/students', title: '学生管理', icon: User },
  { path: '/teacher/assignments', title: '作业管理', icon: Notebook },
  { path: '/teacher/grading', title: '批改与反馈', icon: EditPen },
  { path: '/teacher/schedule', title: '排课管理', icon: Calendar },
  { path: '/teacher/weekly-reports', title: '学习周报', icon: TrendCharts },
  { path: '/teacher/ai-settings', title: '设置', icon: Setting },
]

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
.header-title { font-weight: bold; margin-right: auto; }
.hamburger { font-size: 20px; cursor: pointer; margin-right: auto; }
</style>

<style>
.drawer-body { background: #001529 !important; padding: 0 !important; }

/* 手机端全局收紧留白 */
@media (max-width: 767px) {
  .el-main { padding: 10px !important; }
  .el-card__body { padding: 12px !important; }
  .el-dialog { margin-top: 8vh !important; }
  .el-message-box { width: 90% !important; }
}
</style>
