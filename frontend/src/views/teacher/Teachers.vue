<template>
  <el-card>
    <div class="toolbar">
      <h4 class="page-title">教师管理</h4>
      <div class="toolbar-ops">
        <el-button type="warning" @click="openAdopt">认领旧数据</el-button>
        <el-button type="primary" @click="openCreate">新增教师</el-button>
      </div>
    </div>

    <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px"
              title="教师账号由管理员统一创建；学生注册在「学生管理」中操作并关联教师。教师离职用「删除」，学生与学习数据会保留，可再划归新教师。消息推送功能在「后台设置」中。" />

    <el-table v-if="!isMobile" :data="list" v-loading="loading">
      <el-table-column prop="username" label="用户名" width="160" />
      <el-table-column prop="real_name" label="姓名" width="120" />
      <el-table-column prop="subject" label="任教科目" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.subject" size="small">{{ row.subject }}</el-tag>
          <span v-else style="color:#c0c4cc">未设置</span>
        </template>
      </el-table-column>
      <el-table-column label="AI 使用权限" width="140">
        <template #default="{ row }">
          <el-switch v-model="row.ai_enabled" @change="toggleAi(row)" />
        </template>
      </el-table-column>
      <el-table-column label="好友令牌" width="180">
        <template #default="{ row }">
          <span v-if="row.pushplus_token" class="token-text">{{ maskToken(row.pushplus_token) }}</span>
          <el-tag v-else size="small" type="info">未设置</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">{{ row.created_at?.slice(0, 16).replace('T', ' ') }}</template>
      </el-table-column>
      <el-table-column label="操作">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="success" @click="openTransfer(row)">移交数据</el-button>
          <el-popconfirm title="删除教师账号？其学生与教学数据将保留并托管，可再划归新教师。"
                         confirm-button-text="删除" cancel-button-text="取消" width="320"
                         @confirm="removeTeacher(row)">
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 手机端：卡片布局 -->
    <template v-else>
      <el-card v-for="t in list" :key="t.id" shadow="never" class="t-card">
        <div class="t-head">
          <b>{{ t.real_name || t.username }}</b>
          <el-switch v-model="t.ai_enabled" @change="toggleAi(t)" />
        </div>
        <p class="t-info">用户名：{{ t.username }}<template v-if="t.subject"> · 任教科目：{{ t.subject }}</template></p>
        <p class="t-info">好友令牌：{{ t.pushplus_token ? maskToken(t.pushplus_token) : '未设置' }}</p>
        <p class="t-info">创建时间：{{ t.created_at?.slice(0, 16).replace('T', ' ') }}</p>
        <div class="t-ops">
          <el-button size="small" type="primary" plain @click="openEdit(t)">编辑</el-button>
          <el-button size="small" type="success" plain @click="openTransfer(t)">移交数据</el-button>
          <el-button size="small" type="danger" plain @click="removeTeacher(t)">删除</el-button>
        </div>
      </el-card>
    </template>

    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑教师' : '新增教师'" width="420px">
      <el-form :model="dialog.form" label-width="90px">
        <el-form-item label="用户名">
          <el-input v-model="dialog.form.username" :disabled="dialog.isEdit"
                    placeholder="4-20 位，字母开头，仅字母/数字/下划线" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="dialog.form.real_name" placeholder="教师姓名" />
        </el-form-item>
        <el-form-item label="任教科目">
          <el-select v-model="dialog.form.subject" placeholder="选择任教科目（可清空）" clearable
                     style="width: 100%">
            <el-option v-for="s in subjectOptions" :key="s" :value="s" :label="s" />
          </el-select>
          <div class="hint" style="width: 100%; margin-left: 0">
            统一从预置科目中选择，学生绑定与数据划拨按科目自动匹配
          </div>
        </el-form-item>
        <el-form-item :label="dialog.isEdit ? '重置密码' : '初始密码'">
          <el-input v-model="dialog.form.password" type="password" show-password
                    :placeholder="dialog.isEdit ? '留空表示不修改' : '请输入初始密码'" />
        </el-form-item>
        <el-form-item label="好友令牌">
          <el-input v-model="dialog.form.pushplus_token" type="password" show-password
                    :placeholder="dialog.isEdit ? '留空表示不修改' : 'PushPlus 好友令牌（一对一推送中获取）'" />
        </el-form-item>
        <el-form-item label="AI 权限">
          <el-switch v-model="dialog.form.ai_enabled" />
          <span class="hint">关闭后该教师无法使用 AI 相关功能</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 认领数据：未归属学生按科目绑定教师 + 托管数据按科目拆分划拨 -->
    <el-dialog v-model="adopt.visible" title="认领旧数据（按科目分配）" :width="isMobile ? '94%' : '680px'">
      <template v-if="adopt.preview">
        <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px"
                  title="旧版单教师升级后，托管在管理员名下的数据可在此按科目拆分划拨：为每个学生绑定其授课教师（含科目），课程与课堂反馈按科目分给对应教师。" />

        <template v-if="adopt.preview.orphan_students.length">
          <h5 class="adopt-sec">一、未归属学生（{{ adopt.preview.orphan_students.length }} 名）：为其绑定教师与科目</h5>
          <div v-for="s in adopt.studentPlans" :key="s.student_id" class="adopt-student">
            <div class="adopt-student-head"><b>{{ s.name }}</b>
              <span v-if="s.class_name" class="hint">{{ s.class_name }}</span></div>
            <div v-for="(b, i) in s.bindings" :key="i" class="adopt-bind-row">
              <el-select v-model="b.teacher_id" placeholder="选择教师" size="small" style="width: 160px"
                         @change="tid => onAdoptTeacherChange(b, tid)">
                <el-option v-for="t in adopt.preview.teachers" :key="t.id" :value="t.id"
                           :label="t.subject ? `${t.name}（${t.subject}）` : t.name" />
              </el-select>
              <el-tag v-if="b.subject" size="small">{{ b.subject }}</el-tag>
              <el-button link type="danger" size="small" @click="s.bindings.splice(i, 1)">删除</el-button>
            </div>
            <el-button size="small" text type="primary" @click="s.bindings.push({ teacher_id: null, subject: '' })">
              + 添加绑定
            </el-button>
          </div>
        </template>

        <template v-if="adopt.preview.subject_groups.length">
          <h5 class="adopt-sec">二、托管课程数据按科目划拨</h5>
          <el-table :data="adopt.preview.subject_groups" border size="small">
            <el-table-column prop="subject" label="科目（课程名）" min-width="140" />
            <el-table-column prop="courses" label="课程" width="70" />
            <el-table-column prop="course_feedbacks" label="课堂反馈" width="90" />
            <el-table-column label="接收教师" width="180">
              <template #default="{ row }">
                <el-select v-model="adopt.subjectMap[row.subject]" placeholder="保留托管" clearable size="small">
                  <el-option v-for="t in adopt.preview.teachers" :key="t.id" :value="t.id"
                             :label="t.subject ? `${t.name}（${t.subject}）` : t.name" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
        </template>

        <template v-if="adoptOthersCount">
          <h5 class="adopt-sec">三、其余托管数据整体划拨</h5>
          <div class="adopt-legacy" style="margin-bottom: 8px">
            <span>作业 {{ adopt.preview.others.assignments }} 份</span>
            <span>作业批改 {{ adopt.preview.others.feedbacks }} 份</span>
            <span>AI 练习 {{ adopt.preview.others.worksheet_tasks }} 个</span>
            <span>周报 {{ adopt.preview.others.weekly_reports }} 份</span>
          </div>
          <el-select v-model="adopt.othersTeacherId" placeholder="选择接收教师（可留空保留托管）" clearable
                     size="small" style="width: 260px">
            <el-option v-for="t in adopt.preview.teachers" :key="t.id" :value="t.id" :label="t.name" />
          </el-select>
        </template>

        <el-alert v-if="!adopt.preview.orphan_students.length && !adopt.preview.subject_groups.length && !adoptOthersCount"
                  type="success" show-icon :closable="false" style="margin-top: 12px"
                  title="没有待认领的数据：无未归属学生，管理员名下也无托管教学数据。" />
      </template>
      <template #footer>
        <el-button @click="adopt.visible = false">取消</el-button>
        <el-button type="warning" :loading="adopt.doing" @click="doAdopt">确认认领</el-button>
      </template>
    </el-dialog>

    <!-- 换老师：把该教师的学生与教学数据整体移交给另一位教师 -->
    <el-dialog v-model="transfer.visible" title="移交数据（换老师）" width="480px">
      <template v-if="transfer.preview">
        <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px"
                  title="同一科目更换老师时使用：把该教师名下的学生和全部教学数据整体移交给新老师，学生的课程、作业与学习记录无缝衔接。" />
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="移交内容">
            <div class="adopt-legacy">
              <span>学生 {{ transfer.preview.students }} 名</span>
              <span>作业 {{ transfer.preview.assignments }} 份</span>
              <span>课程 {{ transfer.preview.courses }} 节</span>
              <span>课堂反馈 {{ transfer.preview.course_feedbacks }} 条</span>
              <span>作业批改 {{ transfer.preview.feedbacks }} 份</span>
              <span>AI 练习 {{ transfer.preview.worksheet_tasks }} 个</span>
              <span>周报 {{ transfer.preview.weekly_reports }} 份</span>
            </div>
          </el-descriptions-item>
        </el-descriptions>
        <el-form label-width="90px" style="margin-top: 12px">
          <el-form-item label="接收教师">
            <el-select v-model="transfer.targetId" placeholder="选择接收数据的教师" style="width: 100%">
              <el-option v-for="o in transfer.preview.targets" :key="o.id"
                         :label="o.name" :value="o.id" />
            </el-select>
          </el-form-item>
        </el-form>
        <el-alert v-if="!transfer.preview.targets.length" type="warning" show-icon
                  :closable="false" title="系统中没有其他教师账号，请先新增教师。" />
      </template>
      <template #footer>
        <el-button @click="transfer.visible = false">取消</el-button>
        <el-button type="success" :loading="transfer.doing" :disabled="!transfer.targetId"
                   @click="doTransfer">确认移交</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'
import { useIsMobile } from '../../composables/useIsMobile'

const { isMobile } = useIsMobile()
const list = ref([])
const loading = ref(false)
const saving = ref(false)
const subjectOptions = ref([])
const dialog = reactive({
  visible: false, isEdit: false, id: 0,
  form: { username: '', real_name: '', password: '', ai_enabled: true, pushplus_token: '' },
})
const adopt = reactive({ visible: false, preview: null, doing: false,
  studentPlans: [], subjectMap: {}, othersTeacherId: null })
const transfer = reactive({ visible: false, id: 0, preview: null, targetId: null, doing: false })

function maskToken(token) {
  return token.length > 10 ? `${token.slice(0, 6)}****${token.slice(-4)}` : '****'
}

async function load() {
  loading.value = true
  try {
    list.value = await api.get('/teachers')
    try {
      subjectOptions.value = await api.get('/settings/subjects')
    } catch { /* 非管理员忽略 */ }
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(dialog, { visible: true, isEdit: false, id: 0,
    form: { username: '', real_name: '', subject: '', password: '', ai_enabled: true, pushplus_token: '' } })
}

function openEdit(row) {
  Object.assign(dialog, { visible: true, isEdit: true, id: row.id,
    form: { username: row.username, real_name: row.real_name, subject: row.subject || '',
            password: '', ai_enabled: row.ai_enabled, pushplus_token: '' } })
}

async function save() {
  const f = dialog.form
  if (!f.username.trim()) return ElMessage.warning('请填写用户名')
  if (!dialog.isEdit && !/^[A-Za-z][A-Za-z0-9_]{3,19}$/.test(f.username.trim())) {
    return ElMessage.warning('用户名需 4-20 位，以字母开头，仅含字母、数字、下划线')
  }
  if (!dialog.isEdit && !f.password) return ElMessage.warning('请填写初始密码')
  saving.value = true
  try {
    if (dialog.isEdit) {
      await api.put(`/teachers/${dialog.id}`, f)
    } else {
      await api.post('/teachers', f)
    }
    ElMessage.success('已保存')
    dialog.visible = false
    load()
  } finally {
    saving.value = false
  }
}

async function toggleAi(row) {
  try {
    await api.put(`/teachers/${row.id}`, {
      real_name: row.real_name, subject: row.subject || '', password: '',
      ai_enabled: row.ai_enabled, pushplus_token: '' })
    ElMessage.success(row.ai_enabled ? '已开放 AI 使用权限' : '已关闭 AI 使用权限')
  } catch {
    row.ai_enabled = !row.ai_enabled
  }
}

function onAdoptTeacherChange(binding, teacherId) {
  const t = (adopt.preview?.teachers || []).find(t => t.id === teacherId)
  binding.subject = t?.subject || ''
}

const adoptOthersCount = computed(() => {
  if (!adopt.preview) return 0
  const o = adopt.preview.others
  return o.assignments + o.feedbacks + o.worksheet_tasks + o.weekly_reports
})

async function openAdopt() {
  adopt.preview = null
  adopt.studentPlans = []
  adopt.subjectMap = {}
  adopt.othersTeacherId = null
  adopt.visible = true
  try {
    const preview = await api.get('/teachers/adopt-preview')
    adopt.preview = preview
    // 未归属学生默认生成一条空绑定，便于快速填写
    adopt.studentPlans = preview.orphan_students.map(s => ({
      student_id: s.id, name: s.name, class_name: s.class_name,
      bindings: [{ teacher_id: null, subject: '' }],
    }))
  } catch {
    adopt.visible = false
  }
}

async function doAdopt() {
  adopt.doing = true
  try {
    const res = await api.post('/teachers/adopt', {
      students: adopt.studentPlans.map(s => ({
        student_id: s.student_id,
        bindings: s.bindings.filter(b => b.teacher_id),
      })),
      subjects: Object.entries(adopt.subjectMap)
        .filter(([, tid]) => tid)
        .map(([subject, teacher_id]) => ({ subject, teacher_id })),
      others_teacher_id: adopt.othersTeacherId || null,
    })
    const m = res.moved
    ElMessage.success(`认领完成：学生 ${m.students} 名、课程 ${m.courses} 节、课堂反馈 ${m.course_feedbacks} 条、作业 ${m.assignments} 份、批改 ${m.feedbacks} 份等已划归`)
    adopt.visible = false
    load()
  } finally {
    adopt.doing = false
  }
}

async function removeTeacher(row) {
  try {
    const res = await api.delete(`/teachers/${row.id}`)
    const m = res.moved
    ElMessage.success(`已删除教师「${row.real_name || row.username}」：学生 ${m.students} 名解除归属（数据保留），教学数据已托管`)
    load()
  } catch {
    /* 错误提示由拦截器统一处理 */
  }
}

async function openTransfer(row) {
  transfer.id = row.id
  transfer.preview = null
  transfer.targetId = null
  transfer.visible = true
  try {
    transfer.preview = await api.get(`/teachers/${row.id}/transfer-preview`)
  } catch {
    transfer.visible = false
  }
}

async function doTransfer() {
  if (!transfer.targetId) return ElMessage.warning('请选择接收教师')
  transfer.doing = true
  try {
    const res = await api.post(`/teachers/${transfer.id}/transfer`, { target_id: transfer.targetId })
    const m = res.moved
    ElMessage.success(`已移交给「${res.target_name}」：学生 ${m.students} 名、作业 ${m.assignments} 份、课程 ${m.courses} 节等`)
    transfer.visible = false
    load()
  } finally {
    transfer.doing = false
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.toolbar-ops { display: flex; gap: 10px; }
.page-title { margin: 0; }
.hint { margin-left: 10px; color: #909399; font-size: 12px; }
.t-card { margin-bottom: 10px; }
.t-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.t-info { margin: 2px 0; font-size: 13px; color: #606266; }
.t-ops { display: flex; gap: 8px; margin-top: 8px; }
.token-text { font-family: monospace; }
.adopt-legacy { display: flex; flex-wrap: wrap; gap: 4px 14px; }
.adopt-sec { margin: 12px 0 8px; }
.adopt-student { border: 1px solid #ebeef5; border-radius: 6px; padding: 8px 10px; margin-bottom: 8px; }
.adopt-student-head { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.adopt-bind-row { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; }
</style>
