<template>
  <el-alert v-if="content && visible" class="ann-bar" type="warning" show-icon :closable="true"
            :title="content" @close="onClose" />
</template>

<script setup>
// 管理员公告展示栏：教师端/学生端顶部共用；用户可手动关闭（按公告 id 记忆，本轮登录不再弹出）
import { onMounted, ref } from 'vue'
import api from '../api'

const content = ref('')
const visible = ref(true)

function dismissKey(id) {
  return `announcement_dismissed_${id}`
}

function onClose() {
  visible.value = false
  if (annId.value) localStorage.setItem(dismissKey(annId.value), '1')
}

const annId = ref(0)

onMounted(async () => {
  try {
    const a = await api.get('/announcements/active')
    if (!a?.content) return
    annId.value = a.id
    if (localStorage.getItem(dismissKey(a.id)) === '1') return
    content.value = a.content
  } catch {
    /* 未登录或接口异常时静默隐藏 */
  }
})
</script>

<style scoped>
.ann-bar { margin-bottom: 12px; }
</style>
