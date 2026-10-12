<template>
  <el-container class="app-layout">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon><Document /></el-icon>
        <span>AI 简历生成器</span>
      </div>
      <el-menu :default-active="$route.path" router>
        <el-menu-item index="/"><el-icon><HomeFilled /></el-icon>仪表盘</el-menu-item>
        <el-menu-item index="/profiles"><el-icon><User /></el-icon>用户管理</el-menu-item>
        <el-menu-item index="/resume/new"><el-icon><EditPen /></el-icon>新建定向简历</el-menu-item>
        <el-menu-item index="/resumes"><el-icon><Files /></el-icon>简历任务</el-menu-item>
        <el-menu-item index="/llm"><el-icon><Setting /></el-icon>LLM 配置</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div style="font-size:16px;font-weight:600">{{ $route.meta.title }}</div>
        <div>
          <span v-if="store.active" class="text-muted" style="margin-right:8px">当前用户</span>
          <el-tag v-if="store.active" effect="dark">{{ store.active.name || '未命名' }}</el-tag>
          <el-tag v-else type="info">未建档</el-tag>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { onMounted } from 'vue'
import { useUserStore } from '@/stores/user'

const store = useUserStore()

onMounted(async () => {
  try {
    await store.fetchActive()
  } catch (e) {
    store.active = null
  }
})
</script>