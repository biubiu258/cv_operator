import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layout/MainLayout.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    children: [
      { path: '', name: 'dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '仪表盘' } },
      { path: 'profiles', name: 'profiles', component: () => import('@/views/Profiles.vue'), meta: { title: '用户管理' } },
      { path: 'profile/new', name: 'profile-new', component: () => import('@/views/ProfileEdit.vue'), meta: { title: '新建档案' } },
      { path: 'profile/:id', name: 'profile-edit', component: () => import('@/views/ProfileEdit.vue'), meta: { title: '编辑档案' } },
      { path: 'resumes', name: 'resumes', component: () => import('@/views/ResumeList.vue'), meta: { title: '简历任务' } },
      { path: 'resume/new', name: 'resume-new', component: () => import('@/views/ResumeNew.vue'), meta: { title: '新建定向简历' } },
      { path: 'resume/:id/edit', name: 'resume-edit', component: () => import('@/views/ResumeNew.vue'), meta: { title: '继续生成简历' } },
      { path: 'resume/:id', name: 'resume-detail', component: () => import('@/views/ResumeDetail.vue'), meta: { title: '简历详情' } },
      { path: 'se-records', name: 'se-records', component: () => import('@/views/SelfEvalRecords.vue'), meta: { title: '自我评价库' } },
      { path: 'llm', name: 'llm', component: () => import('@/views/LlmConfig.vue'), meta: { title: 'LLM 配置' } }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router