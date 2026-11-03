<template>
  <div>
    <div class="page-title">自我评价库</div>
    <div class="page-sub">保存满意的自我评价，可复用、编辑或删除</div>

    <div class="card-panel" style="margin-bottom:16px">
      <div class="card-body">
        <el-space wrap>
          <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon> 新建评价</el-button>
          <el-button @click="load" :loading="loading"><el-icon><Refresh /></el-icon> 刷新</el-button>
        </el-space>
      </div>
    </div>

    <el-empty v-if="!loading && records.length === 0" description="暂无自我评价记录" />

    <div v-for="rec in records" :key="rec.id" class="card-panel" style="margin-bottom:14px">
      <div class="card-body">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
          <div style="white-space:pre-wrap;flex:1">{{ rec.content }}</div>
          <div style="flex-shrink:0">
            <el-space>
              <el-button size="small" @click="copyRecord(rec)"><el-icon><CopyDocument /></el-icon> 复制</el-button>
              <el-button size="small" type="primary" @click="openEdit(rec)"><el-icon><Edit /></el-icon> 编辑</el-button>
              <el-button size="small" type="danger" @click="removeRecord(rec)"><el-icon><Delete /></el-icon> 删除</el-button>
            </el-space>
          </div>
        </div>
        <div class="text-muted" style="font-size:12px;margin-top:10px">
          编号 #{{ rec.id }} · {{ rec.created_at ? new Date(rec.created_at).toLocaleString() : '' }}<span v-if="rec.resume_id"> · 关联简历 #{{ rec.resume_id }}</span>
        </div>
      </div>
    </div>

    <el-dialog v-model="dialog.visible" :title="dialog.editingId ? '编辑自我评价' : '新建自我评价'" width="560px">
      <el-input v-model="dialog.content" type="textarea" :rows="8" placeholder="输入自我评价内容…" />
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="dialog.saving" @click="saveDialog">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '@/api'

const records = ref([])
const loading = ref(false)
const dialog = reactive({ visible: false, editingId: null, content: '', saving: false })

async function load() {
  loading.value = true
  try {
    records.value = await http.get('/self-evaluation/records')
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dialog.editingId = null
  dialog.content = ''
  dialog.visible = true
}

function openEdit(rec) {
  dialog.editingId = rec.id
  dialog.content = rec.content
  dialog.visible = true
}

async function saveDialog() {
  dialog.saving = true
  try {
    if (dialog.editingId) {
      await http.put(`/self-evaluation/records/${dialog.editingId}`, { content: dialog.content })
      ElMessage.success('已更新')
    } else {
      await http.post('/self-evaluation/records', { content: dialog.content })
      ElMessage.success('已保存')
    }
    dialog.visible = false
    await load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    dialog.saving = false
  }
}

async function removeRecord(rec) {
  try {
    await ElMessageBox.confirm('确定删除这条自我评价记录？', '提示', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await http.delete(`/self-evaluation/records/${rec.id}`)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

async function copyRecord(rec) {
  try {
    await navigator.clipboard.writeText(rec.content)
    ElMessage.success('已复制到剪贴板')
  } catch (e) {
    ElMessage.error('复制失败，请手动选择文本')
  }
}

onMounted(load)
</script>