<template>
  <el-card>
    <el-empty v-if="!list.length" description="老师还没有为你生成练习" />

    <!-- 手机端卡片列表 -->
    <template v-else-if="isMobile">
      <el-card v-for="row in list" :key="row.id" class="m-card" shadow="never">
        <div class="m-head"><b>{{ row.title }}</b></div>
        <p class="m-preview">{{ row.content }}</p>
        <p class="m-meta">{{ row.created_at?.replace('T', ' ') }}</p>
        <el-button size="small" @click="preview(row)">预览</el-button>
        <el-button type="primary" size="small" @click="download(row)">下载 PDF</el-button>
      </el-card>
    </template>

    <!-- 桌面端表格 -->
    <el-table v-else :data="list" border stripe>
      <el-table-column prop="title" label="练习标题" width="220" />
      <el-table-column prop="content" label="内容预览" show-overflow-tooltip />
      <el-table-column prop="created_at" label="生成时间" width="170">
        <template #default="{ row }">{{ row.created_at?.replace('T', ' ') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="preview(row)">预览</el-button>
          <el-button link type="primary" @click="download(row)">下载 PDF</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="previewRow.title" :width="isMobile ? '94%' : '680px'">
      <pre class="ws-content">{{ previewRow.content }}</pre>
      <template #footer>
        <el-button type="primary" @click="download(previewRow)">下载 PDF</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api, { authUrl } from '../../api'
import { useIsMobile } from '../../composables/useIsMobile'

const { isMobile } = useIsMobile()
const list = ref([])
const dialogVisible = ref(false)
const previewRow = ref({})

async function load() {
  list.value = await api.get('/worksheets/my')
}

function preview(row) {
  previewRow.value = row
  dialogVisible.value = true
}

function download(row) {
  window.open(authUrl(`/api/worksheets/${row.id}/pdf`))
}

onMounted(load)
</script>

<style scoped>
.m-card { margin-bottom: 12px; }
.m-head { margin-bottom: 6px; }
.m-preview {
  color: #555;
  margin: 6px 0;
  white-space: pre-wrap;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.m-meta { color: #999; font-size: 12px; margin: 4px 0 10px; }
.ws-content {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 6px;
  white-space: pre-wrap;
  max-height: 50vh;
  overflow: auto;
}
</style>
