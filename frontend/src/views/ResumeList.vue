<template>
  <div>
    <div class="page-title">简历任务</div>
    <div class="page-sub">查看历史定向简历任务与生成结果</div>

    <div style="margin-bottom:16px">
      <el-button type="primary" @click="$router.push('/resume/new')"><el-icon><Plus /></el-icon> 新建定向简历</el-button>
    </div>

    <div class="card-panel">
      <div class="card-body">
        <el-table :data="list" v-loading="loading" @row-click="(r) => $router.push(`/resume/${r.id}`)" class="clickable">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="目标岗位" min-width="160">
            <template #default="{ row }">{{ row.target_position || row.jd_summary?.position || '未识别' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status !== 'generated'" size="small" type="warning" @click.stop="$router.push(`/resume/${row.id}/edit`)">继续</el-button>
              <el-button v-else size="small" @click.stop="$router.push(`/resume/${row.id}`)">查看</el-button>
              <el-button size="small" text @click.stop="$router.push(`/resume/${row.id}/review`)">回顾</el-button>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180" />
        </el-table>
        <el-empty v-if="!loading && list.length === 0" description="暂无简历任务" :image-size="70" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import http from '@/api'

const list = ref([])
const loading = ref(false)

const statusType = (s) => (s === 'generated' ? 'success' : s === 'draft' ? 'info' : 'warning')

onMounted(async () => {
  loading.value = true
  try {
    list.value = await http.get('/resumes')
  } catch (e) {
  } finally {
    loading.value = false
  }
})
</script>