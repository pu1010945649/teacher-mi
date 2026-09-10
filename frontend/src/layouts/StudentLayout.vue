<template>
  <el-container class="layout">
    <!-- 桌面端侧边栏 -->
    <el-aside v-if="!isMobile" width="220px" class="aside">
      <div class="logo">Teacher-Mi 学生端</div>
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
        <span class="header-title">{{ isMobile ? 'Teacher-Mi 学生端' : '' }}</span>
        <span class="header-user">{{ auth.realName || auth.username }}</span>
        <el-button link type="primary" @click="pwdDialog.open()">修改密码</el-button>
        <el-button link type="danger" @click="onLogout">退出登录</el-button>
      </el-header>
      <el-main class="main">
        <AnnouncementBar />
        <router-view />
      </el-main>
    </el-container>

    <!-- 手机端抽屉菜单 -->
    <el-drawer v-model="drawerVisible" direction="ltr" size="200px" :with-header="false"
               body-class="drawer-body">
      <div class="logo drawer-logo">Teacher-Mi 学生端</div>
      <el-menu :default-active="$route.path" router background-color="#001529" text-color="#bfcbd9"
               active-text-color="#409eff" @select="drawerVisible = false">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon><span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, Calendar, Menu, Notebook } from '@element-plus/icons-vue'
import { useAuthStore } from '../store/auth'
import { useIsMobile } from '../composables/useIsMobile'
import AnnouncementBar from '../components/AnnouncementBar.vue'

const router = useRouter()
const auth = useAuthStore()
const { isMobile } = useIsMobile()
const drawerVisible = ref(false)

const menus = [
  { path: '/student/assignments', title: '我的作业', icon: Notebook },
  { path: '/student/schedule', title: '我的课表', icon: Calendar },
  { path: '/student/messages', title: '我的消息', icon: Bell },
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
.aside :deep(.el-menu) { border-right: none; }
.header {
  background: #fff;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}
.header-title { font-weight: bold; }
.header-user { margin-left: auto; }
.hamburger { font-size: 20px; cursor: pointer; }
.main { padding: var(--el-main-padding); }
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
