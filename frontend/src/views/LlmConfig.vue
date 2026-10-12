<template>
  <div>
    <div class="page-title">LLM 配置</div>
    <div class="page-sub">填写 OpenAI 兼容的服务地址与密钥，即可拉取可用模型列表</div>

    <div class="card-panel" style="max-width:640px">
      <div class="card-body">
        <el-form label-width="120px" label-position="left">
          <el-form-item label="Base URL">
            <el-input v-model="form.base_url" placeholder="如 https://api.deepseek.com" clearable />
            <div class="text-muted" style="font-size:12px">请填写到能直接拼接 /models、/chat/completions 的根地址</div>
          </el-form-item>

          <el-form-item label="API Key">
            <el-input v-model="form.api_key" type="password" show-password
              :placeholder="config.api_key_masked ? `已保存：${config.api_key_masked}` : '请输入 API Key'" />
          </el-form-item>

          <el-form-item label="模型">
            <div style="width:100%">
              <el-select v-model="form.model" filterable allow-create default-first-option
                placeholder="选择或手动输入模型" style="width:100%">
                <el-option v-for="m in models" :key="m" :label="m" :value="m" />
              </el-select>
              <el-button style="margin-top:8px" size="small" @click="pullModels" :loading="pulling">
                <el-icon><Refresh /></el-icon> 拉取模型列表
              </el-button>
            </div>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="save" :loading="saving">保存配置</el-button>
            <el-button @click="test" :loading="testing">测试连接</el-button>
          </el-form-item>
        </el-form>

        <el-alert v-if="testResult" :type="testResult.ok ? 'success' : 'error'" :closable="false"
          :title="testResult.message" style="margin-top:8px" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '@/api'

const form = reactive({ base_url: '', api_key: '', model: '' })
const config = reactive({ api_key_masked: '' })
const models = ref([])
const pulling = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null)

onMounted(async () => {
  const cfg = await http.get('/llm/config')
  form.base_url = cfg.base_url
  form.model = cfg.model
  config.api_key_masked = cfg.api_key_masked
})

async function pullModels() {
  if (!form.base_url || !form.api_key) {
    ElMessage.warning('请先填写 Base URL 与 API Key')
    return
  }
  pulling.value = true
  try {
    const res = await http.post('/llm/models', { base_url: form.base_url, api_key: form.api_key })
    models.value = res.models || []
    if (models.value.length) ElMessage.success(`拉取到 ${models.value.length} 个模型`)
    else ElMessage.warning('未获取到模型列表')
  } finally {
    pulling.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const res = await http.put('/llm/config', form)
    config.api_key_masked = res.api_key_masked
    ElMessage.success('配置已保存')
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  testResult.value = null
  try {
    await http.put('/llm/config', form)
    testResult.value = await http.post('/llm/test')
  } finally {
    testing.value = false
  }
}
</script>