<template>
  <div>
    <div class="page-title">{{ isEdit ? '编辑档案' : '新建档案' }}</div>
    <div class="page-sub">分步填写，完善后供定向简历与自我评价复用</div>

    <el-tabs v-model="activeTab" class="card-panel" style="padding:0 20px 20px">
      <!-- 基本信息 -->
      <el-tab-pane label="基本信息" name="basic">
        <div class="card-panel" style="border:none;box-shadow:none;max-width:640px">
          <div class="card-body" style="padding-left:0">
            <el-form label-width="110px">
              <el-form-item label="姓名"><el-input v-model="basic.name" /></el-form-item>
              <el-form-item label="电话"><el-input v-model="basic.phone" /></el-form-item>
              <el-form-item label="邮箱"><el-input v-model="basic.email" /></el-form-item>
              <el-form-item label="所在地"><el-input v-model="basic.location" /></el-form-item>
              <el-form-item label="意向岗位"><el-input v-model="basic.target_position" placeholder="如 AI Agent 开发工程师" /></el-form-item>
              <el-form-item label="期望薪资"><el-input v-model="basic.expected_salary" placeholder="如：15K-20K 或 面议" /></el-form-item>
              <el-form-item label="毕业日期"><el-input v-model="basic.graduation_date" placeholder="如：2026.07（杜撰经历时间线参考，非必填）" /></el-form-item>
              <el-form-item label="个人头像">
                <div class="avatar-edit">
                  <img v-if="basic.avatar" class="avatar-preview" :src="fileUrl(basic.avatar)" alt="头像" />
                  <div v-else class="avatar-preview avatar-empty">无</div>
                  <template v-if="isEdit">
                    <el-upload :show-file-list="false" :http-request="doUploadAvatar" accept="image/*">
                      <el-button size="small" type="primary" plain :loading="uploadingAvatar">
                        {{ basic.avatar ? '更换头像' : '上传头像' }}
                      </el-button>
                    </el-upload>
                    <el-button v-if="basic.avatar" size="small" text type="danger" @click="removeAvatar">移除</el-button>
                  </template>
                  <span v-else class="text-muted" style="font-size:12px">创建档案后可上传头像</span>
                </div>
              </el-form-item>
              <el-form-item label="爱好"><el-input v-model="basic.hobbies" type="textarea" :rows="2" placeholder="如：跑步、摄影、开源参与、写作…（生成自我评价时可参考，非必填）" /></el-form-item>
              <el-form-item>
                <el-button type="primary" @click="saveBasic" :loading="savingBasic">
                  {{ isEdit ? '保存基本信息' : '创建档案' }}
                </el-button>
                <span v-if="created" class="text-muted" style="margin-left:12px">档案已创建，可继续填写下方模块</span>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </el-tab-pane>

      <!-- 子实体模块 -->
      <el-tab-pane v-for="e in ENTITIES" :key="e.key" :label="e.label" :name="e.key" :disabled="!isEdit">
        <div class="card-panel" style="border:none;box-shadow:none">
          <div style="margin-bottom:12px">
            <el-button type="primary" plain @click="openDialog(e)"><el-icon><Plus /></el-icon> 添加{{ e.singular }}</el-button>
          </div>
          <el-table :data="data[e.key]" v-loading="loading">
            <el-table-column :label="e.label" min-width="320">
              <template #default="{ row }">{{ e.display(row) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-button size="small" @click="openDialog(e, row)">编辑</el-button>
                <el-button size="small" type="danger" plain @click="del(e, row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && data[e.key].length === 0" description="暂无记录" :image-size="60" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 子实体编辑对话框 -->
    <el-dialog v-model="dialog.visible" :title="dialog.title" width="560px">
      <el-form label-width="100px">
        <el-form-item v-for="f in dialog.fields" :key="f.prop" :label="f.label">
          <el-input v-if="f.type === 'textarea'" v-model="dialog.form[f.prop]" type="textarea" :rows="3" />
          <div v-else-if="f.type === 'proficiency'" style="display:flex;gap:8px;width:100%">
            <el-select v-model="dialog.form[f.prop]" placeholder="请选择熟练度" style="width:200px">
              <el-option v-for="o in PROFICIENCY_OPTIONS" :key="o" :label="o" :value="o" />
            </el-select>
            <el-input v-if="dialog.form[f.prop] === '其他'" v-model="dialog.other[f.prop]" placeholder="手动填写熟练度描述" style="flex:1" />
          </div>
          <el-input v-else v-model="dialog.form[f.prop]" :placeholder="f.placeholder || ''" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" @click="saveDialog" :loading="dialog.saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { fileUrl } from '@/api'

const route = useRoute()
const router = useRouter()

const userId = computed(() => (route.params.id ? Number(route.params.id) : null))
const isEdit = computed(() => !!userId.value)

const basic = reactive({ name: '', phone: '', email: '', location: '', target_position: '', expected_salary: '', graduation_date: '', avatar: '', hobbies: '' })
const data = reactive({ educations: [], skills: [], projects: [], internships: [], certificates: [] })
const activeTab = ref('basic')
const loading = ref(false)
const savingBasic = ref(false)
const created = ref(false)
const uploadingAvatar = ref(false)

// 头像上传/移除：走独立接口，保存文件到后端 uploads/avatars
async function doUploadAvatar({ file }) {
  uploadingAvatar.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await http.post(`/users/${userId.value}/avatar`, fd)
    basic.avatar = res.avatar || ''
    ElMessage.success('头像已上传')
  } catch (e) {
    ElMessage.error(e.message || '头像上传失败')
  } finally {
    uploadingAvatar.value = false
  }
}

async function removeAvatar() {
  try {
    const res = await http.delete(`/users/${userId.value}/avatar`)
    basic.avatar = res.avatar || ''
    ElMessage.success('头像已移除')
  } catch (e) {
    ElMessage.error(e.message || '移除失败')
  }
}

const PROFICIENCY_OPTIONS = ['熟练', '熟悉', '掌握', '了解', '其他']

const ENTITIES = [
  {
    key: 'educations', label: '教育背景', singular: '教育经历',
    fields: [
      { prop: 'school', label: '学校' }, { prop: 'major', label: '专业' },
      { prop: 'degree', label: '学历' }, { prop: 'start_date', label: '开始时间', placeholder: '2023.09' },
      { prop: 'end_date', label: '结束时间', placeholder: '2027.06' },
      { prop: 'courses', label: '主修课程', type: 'textarea' }, { prop: 'gpa', label: 'GPA' }, { prop: 'rank', label: '排名' }
    ],
    display: (r) => `${r.school} | ${r.major} | ${r.degree}（${r.start_date} - ${r.end_date}）`
  },
  {
    key: 'skills', label: '专业技能', singular: '技能',
    fields: [
      { prop: 'category', label: '分类', placeholder: '语言/数据库/AI工程/工具/前端/后端' },
      { prop: 'name', label: '技能名' }, { prop: 'proficiency', label: '熟练度', type: 'proficiency' }
    ],
    display: (r) => `${r.category} · ${r.name}（${r.proficiency}）`
  },
  {
    key: 'projects', label: '项目经历', singular: '项目',
    fields: [
      { prop: 'title', label: '项目标题' }, { prop: 'role', label: '角色' },
      { prop: 'tech_stack', label: '技术栈' }, { prop: 'start_date', label: '开始时间' },
      { prop: 'end_date', label: '结束时间' }, { prop: 'description', label: '项目描述', type: 'textarea' },
      { prop: 'result', label: '量化成果', type: 'textarea' }
    ],
    display: (r) => `${r.title}（${r.start_date} - ${r.end_date}）`
  },
  {
    key: 'internships', label: '实习经历', singular: '实习',
    fields: [
      { prop: 'company', label: '公司' }, { prop: 'position', label: '职位' },
      { prop: 'start_date', label: '开始时间' }, { prop: 'end_date', label: '结束时间' },
      { prop: 'description', label: '工作内容', type: 'textarea' }, { prop: 'achievement', label: '业绩成果', type: 'textarea' }
    ],
    display: (r) => `${r.company} | ${r.position}（${r.start_date} - ${r.end_date}）`
  },
  {
    key: 'certificates', label: '证书/获奖', singular: '证书',
    fields: [
      { prop: 'name', label: '名称' }, { prop: 'date', label: '时间' }, { prop: 'description', label: '说明', type: 'textarea' }
    ],
    display: (r) => `${r.name}${r.date ? '（' + r.date + '）' : ''}`
  }
]

const dialog = reactive({ visible: false, title: '', key: '', editingId: null, fields: [], form: {}, other: {}, saving: false })

onMounted(async () => {
  if (isEdit.value) {
    await load()
  }
})

async function load() {
  loading.value = true
  try {
    const u = await http.get(`/users/${userId.value}`)
    Object.assign(basic, {
      name: u.name, phone: u.phone, email: u.email,
      location: u.location, target_position: u.target_position,
      expected_salary: u.expected_salary || '', graduation_date: u.graduation_date || '',
      avatar: u.avatar || '', hobbies: u.hobbies || ''
    })
    ENTITIES.forEach((e) => { data[e.key] = u[e.key] || [] })
    created.value = true
  } finally {
    loading.value = false
  }
}

async function saveBasic() {
  savingBasic.value = true
  try {
    if (isEdit.value) {
      await http.put(`/users/${userId.value}`, basic)
      ElMessage.success('基本信息已保存')
    } else {
      const u = await http.post('/users', basic)
      created.value = true
      ElMessage.success('档案已创建')
      router.replace(`/profile/${u.id}`)
    }
  } finally {
    savingBasic.value = false
  }
}

function openDialog(entity, row = null) {
  dialog.key = entity.key
  dialog.fields = entity.fields
  dialog.editingId = row ? row.id : null
  dialog.title = row ? `编辑${entity.singular}` : `添加${entity.singular}`
  const form = {}
  const other = {}
  entity.fields.forEach((f) => {
    let val = row ? (row[f.prop] || '') : ''
    if (f.type === 'proficiency') {
      if (val && !PROFICIENCY_OPTIONS.includes(val)) {
        other[f.prop] = val
        val = '其他'
      }
    }
    form[f.prop] = val
  })
  dialog.form = form
  dialog.other = other
  dialog.visible = true
}

async function saveDialog() {
  dialog.saving = true
  try {
    const form = { ...dialog.form }
    if (form.proficiency === '其他') {
      form.proficiency = dialog.other.proficiency || '其他'
    }
    if (dialog.editingId) {
      await http.put(`/${dialog.key}/${dialog.editingId}`, form)
      ElMessage.success('已更新')
    } else {
      await http.post(`/users/${userId.value}/${dialog.key}`, form)
      ElMessage.success('已添加')
    }
    dialog.visible = false
    await load()
  } finally {
    dialog.saving = false
  }
}

async function del(entity, row) {
  try {
    await ElMessageBox.confirm('确定删除该条记录？', '提示', { type: 'warning' })
  } catch (e) {
    return
  }
  await http.delete(`/${entity.key}/${row.id}`)
  ElMessage.success('已删除')
  await load()
}
</script>

<style scoped>
.avatar-edit { display: flex; align-items: center; gap: 10px; }
.avatar-preview {
  width: 64px; height: 64px;
  object-fit: cover; border-radius: 6px;
  border: 1px solid #dcdfe6; background: #f5f7fa;
}
.avatar-empty {
  display: grid; place-items: center;
  color: #a8abb2; font-size: 13px;
}
</style>