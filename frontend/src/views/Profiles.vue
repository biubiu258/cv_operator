<template>
  <div>
    <div class="page-title">用户管理</div>
    <div class="page-sub">一次建档、长期复用，支持多用户切换</div>

    <div style="margin-bottom:16px">
      <el-button type="primary" @click="$router.push('/profile/new')"><el-icon><Plus /></el-icon> 新建用户</el-button>
    </div>

    <el-row :gutter="16">
      <el-col :span="8" v-for="u in store.list" :key="u.id">
        <div class="card-panel" style="margin-bottom:16px">
          <div class="card-body">
            <div style="display:flex;align-items:center;justify-content:space-between">
              <div style="font-size:18px;font-weight:600">{{ u.name }}</div>
              <el-tag v-if="u.is_active" type="success" effect="dark">当前</el-tag>
            </div>
            <div class="text-muted" style="margin:8px 0">{{ u.target_position || '意向岗位未填写' }}</div>
            <div class="text-muted" style="font-size:13px">{{ u.phone }} · {{ u.email }}</div>
            <div style="margin-top:14px">
              <el-button v-if="!u.is_active" size="small" type="primary" @click="activate(u.id)">切换到此用户</el-button>
              <el-tag v-else size="small" type="info">默认使用中</el-tag>
              <el-button size="small" @click="$router.push(`/profile/${u.id}`)">编辑</el-button>
              <el-button size="small" type="danger" plain @click="remove(u)">删除</el-button>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-empty v-if="store.list.length === 0" description="还没有用户档案，先新建一个" />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const store = useUserStore()

onMounted(async () => {
  await store.fetchList()
})

async function activate(id) {
  await store.activate(id)
  ElMessage.success('已切换当前用户')
}

async function remove(u) {
  try {
    await ElMessageBox.confirm(`确定删除用户「${u.name}」及其全部档案？`, '提示', { type: 'warning' })
  } catch (e) {
    return
  }
  await store.remove(u.id)
  ElMessage.success('已删除')
}
</script>