<template>
  <div>
    <div class="page-title">仪表盘</div>
    <div class="page-sub">AI 定向简历生成工作台</div>

    <el-row :gutter="16">
      <el-col :span="8">
        <div class="card-panel" style="height:160px">
          <div class="card-head">当前用户</div>
          <div class="card-body">
            <template v-if="store.active">
              <div style="font-size:22px;font-weight:700">{{ store.active.name }}</div>
              <div class="text-muted" style="margin-top:8px">意向岗位：{{ store.active.target_position || '未填写' }}</div>
              <div class="text-muted" style="margin-top:4px;font-size:13px">{{ store.active.location }}</div>
            </template>
            <el-empty v-else description="尚未建档" :image-size="60" />
          </div>
        </div>
      </el-col>

      <el-col :span="16">
        <div class="card-panel" style="height:160px">
          <div class="card-head">快速开始</div>
          <div class="card-body">
            <el-space wrap :size="12">
              <el-button type="primary" @click="$router.push('/profile/new')"><el-icon><User /></el-icon> 新建档案</el-button>
              <el-button type="primary" plain @click="$router.push('/resume/new')"><el-icon><EditPen /></el-icon> 新建定向简历</el-button>
              <el-button @click="$router.push('/profiles')"><el-icon><Switch /></el-icon> 切换用户</el-button>
              <el-button @click="$router.push('/llm')"><el-icon><Setting /></el-icon> LLM 配置</el-button>
            </el-space>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="card-panel" style="margin-top:16px">
      <div class="card-head">最近简历任务</div>
      <div class="card-body">
        <el-table :data="resumes" v-loading="loading" @row-click="(r) => $router.push(`/resume/${r.id}`)" class="clickable">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="目标岗位">
            <template #default="{ row }">{{ row.target_position || row.jd_summary?.position || '未识别' }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="180" />
        </el-table>
        <el-empty v-if="!loading && resumes.length === 0" description="暂无简历任务" :image-size="70" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import http from '@/api'
import { useUserStore } from '@/stores/user'

const store = useUserStore()
const resumes = ref([])
const loading = ref(false)

const statusType = (s) => {
  if (s === 'generated') return 'success'
  if (s === 'draft') return 'info'
  return 'warning'
}

onMounted(async () => {
  loading.value = true
  try {
    resumes.value = await http.get('/resumes')
  } catch (e) {
  } finally {
    loading.value = false
  }
})
</script>