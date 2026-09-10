<template>
  <el-card>
    <div class="toolbar">
      <h4 class="page-title">登录日志</h4>
      <el-button :loading="loading" @click="load(page)">刷新</el-button>
    </div>
    <el-table :data="logs" size="small" v-loading="loading">
      <el-table-column label="登录时间" width="170">
        <template #default="{ row }">{{ row.created_at.slice(0, 19).replace('T', ' ') }}</template>
      </el-table-column>
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column label="角色" width="90">
        <template #default="{ row }">{{ { admin: '管理员', teacher: '教师', student: '学生' }[row.role] || '-' }}</template>
      </el-table-column>
      <el-table-column prop="ip" label="IP 地址" min-width="140" />
      <el-table-column label="结果" width="90">
        <template #default="{ row }">
          <el-tag :type="row.success ? 'success' : 'danger'" size="small">
            {{ row.success ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
    <div style="margin-top: 12px; display: flex; justify-content: flex-end">
      <el-pagination layout="total, prev, pager, next" :total="total"
                     :page-size="size" :current-page="page"
                     @current-change="(p) => load(p)" />
    </div>
  </el-card>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../../api'

const logs = ref([])
const total = ref(0)
const page = ref(1)
const size = 20
const loading = ref(false)

async function load(p = 1) {
  loading.value = true
  try {
    page.value = p
    const data = await api.get(`/settings/login-logs?page=${p}&size=${size}`)
    logs.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(() => load())
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.page-title { margin: 0; }
</style>
