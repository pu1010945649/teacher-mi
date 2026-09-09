<template>
  <router-view />
</template>

<script setup>
import { watch } from 'vue'
import { useAuthStore } from './store/auth'
import { syncRealtime } from './realtime'

const auth = useAuthStore()
// 登录/登出时建立或断开 SSE 实时刷新连接
watch(() => auth.token, (t) => syncRealtime(t), { immediate: true })
</script>

<style>
body {
  margin: 0;
  background: #f5f7fa;
}
</style>
