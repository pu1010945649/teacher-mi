<template>
  <el-card>
    <el-empty v-if="!list.length" description="暂无批改反馈" />
    <el-timeline v-else>
      <el-timeline-item v-for="item in list" :key="item.id" :timestamp="item.feedback?.created_at?.replace('T', ' ')"
                        placement="top">
        <el-card>
          <h3 style="margin-top: 0">{{ item.assignment_title }}</h3>
          <p>
            <b>得分：</b>
            <el-tag type="success" size="large">{{ item.feedback?.score ?? '-' }}</el-tag>
          </p>
          <p><b>老师评语：</b></p>
          <div class="fb-content">{{ item.feedback?.content || '（无文字评语）' }}</div>
          <template v-if="item.feedback?.annotation">
            <p><b>在线批注：</b></p>
            <div class="fb-content annotation">{{ item.feedback.annotation }}</div>
          </template>
          <p v-if="item.feedback?.has_annotated_file" style="margin-top: 8px">
            <b>批注文件：</b>
            <el-link v-if="isImage(item.feedback.filename)" type="primary" @click="viewImage(item)">
              在线查看
            </el-link>
            <el-link type="primary" style="margin-left: 8px" @click="downloadAnnotated(item)">
              下载 {{ item.feedback.filename }}
            </el-link>
          </p>
          <el-tag v-if="item.feedback?.ai_assisted" type="info" size="small" style="margin-top: 8px">
            本反馈由 AI 辅助生成
          </el-tag>
        </el-card>
      </el-timeline-item>
    </el-timeline>
  </el-card>

  <!-- 批注图片在线查看 -->
  <el-dialog v-model="viewer.visible" title="老师批注" :width="isMobile ? '98%' : '820px'" top="4vh">
    <div class="viewer-box">
      <img :src="viewer.src" alt="批注图片" />
    </div>
    <template #footer>
      <el-button @click="downloadAnnotated(viewer.item)">下载图片</el-button>
      <el-button type="primary" @click="viewer.visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api, { authUrl } from '../../api'
import { useIsMobile } from '../../composables/useIsMobile'

const { isMobile } = useIsMobile()
const list = ref([])
const viewer = reactive({ visible: false, src: '', item: null })

const IMG_EXT = /\.(png|jpe?g|gif|bmp|webp)$/i
function isImage(name) {
  return IMG_EXT.test(name || '')
}

function viewImage(item) {
  viewer.item = item
  viewer.src = authUrl(`/api/feedback/submission/${item.id}/annotated-file`)
  viewer.visible = true
}

function downloadAnnotated(item) {
  const a = document.createElement('a')
  a.href = authUrl(`/api/feedback/submission/${item.id}/annotated-file`)
  a.download = item.feedback.filename
  a.click()
}

onMounted(async () => {
  list.value = await api.get('/feedback/my')
})
</script>

<style scoped>
.fb-content {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 6px;
  white-space: pre-wrap;
}
.annotation { border-left: 3px solid #e6a23c; }
.viewer-box {
  text-align: center;
  max-height: 70vh;
  overflow: auto;
}
.viewer-box img {
  max-width: 100%;
  border-radius: 6px;
}
</style>
