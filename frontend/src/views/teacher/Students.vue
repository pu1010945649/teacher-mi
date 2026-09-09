<template>
  <el-card>
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索姓名/账号/学号/班级" clearable
                :style="{ width: isMobile ? '100%' : '260px' }"
                @keyup.enter="load" @clear="load" />
      <el-button type="primary" @click="load">搜索</el-button>
      <el-button type="success" @click="openDialog()">新增学生</el-button>
    </div>
    <!-- 手机端卡片列表 -->
    <template v-if="isMobile">
      <el-empty v-if="!list.length" description="暂无学生" />
      <el-card v-for="row in list" :key="row.id" class="m-card" shadow="never">
        <div class="m-head">
          <b>{{ row.real_name || row.username }}</b>
          <el-tag v-if="row.class_name" size="small" type="info">{{ row.class_name }}</el-tag>
        </div>
        <p class="m-meta">账号：{{ row.username }}<template v-if="row.student_no"> · 学号：{{ row.student_no }}</template></p>
        <div class="m-ops">
          <el-button size="small" type="primary" plain @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确定删除该学生及其所有记录？" @confirm="remove(row)">
            <template #reference>
              <el-button size="small" type="danger" plain>删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </el-card>
    </template>
    <!-- 桌面端表格 -->
    <el-table v-else :data="list" border stripe>
      <el-table-column prop="username" label="登录账号" width="140" />
      <el-table-column prop="real_name" label="姓名" width="120" />
      <el-table-column prop="student_no" label="学号" width="140" />
      <el-table-column prop="class_name" label="班级" width="140" />
      <el-table-column prop="created_at" label="创建时间" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确定删除该学生及其所有记录？" @confirm="remove(row)">
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑学生' : '新增学生'"
               :width="isMobile ? '92%' : '440px'">
      <el-form :model="dialog.form" label-width="80px">
        <el-form-item label="登录账号">
          <el-input v-model="dialog.form.username" :disabled="dialog.isEdit" />
        </el-form-item>
        <el-form-item :label="dialog.isEdit ? '重置密码' : '初始密码'">
          <el-input v-model="dialog.form.password" :placeholder="dialog.isEdit ? '留空则不修改' : ''" />
        </el-form-item>
        <el-form-item label="姓名"><el-input v-model="dialog.form.real_name" /></el-form-item>
        <el-form-item label="学号"><el-input v-model="dialog.form.student_no" /></el-form-item>
        <el-form-item label="班级"><el-input v-model="dialog.form.class_name" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'
import { useRealtime } from '../../realtime'
import { useIsMobile } from '../../composables/useIsMobile'

const { isMobile } = useIsMobile()
const list = ref([])
const keyword = ref('')
const dialog = reactive({
  visible: false, isEdit: false, id: 0,
  form: { username: '', password: '', real_name: '', student_no: '', class_name: '' },
})

async function load() {
  const data = await api.get('/students', { params: { keyword: keyword.value } })
  list.value = data
}

function openDialog(row) {
  dialog.isEdit = !!row
  dialog.id = row?.id || 0
  dialog.form = row
    ? { ...row, password: '' }
    : { username: '', password: '', real_name: '', student_no: '', class_name: '' }
  dialog.visible = true
}

async function save() {
  if (dialog.isEdit) {
    await api.put(`/students/${dialog.id}`, dialog.form)
    ElMessage.success('已保存')
  } else {
    if (!dialog.form.username || !dialog.form.password) {
      ElMessage.warning('请填写账号和初始密码')
      return
    }
    await api.post('/students', dialog.form)
    ElMessage.success('已创建')
  }
  dialog.visible = false
  load()
}

async function remove(row) {
  await api.delete(`/students/${row.id}`)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
// 学生增删改（多端同步）→ 自动刷新
useRealtime('student', load)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.m-card { margin-bottom: 12px; }
.m-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.m-meta { color: #999; font-size: 12px; margin: 6px 0 0; }
.m-ops { display: flex; gap: 8px; margin-top: 8px; }
</style>
