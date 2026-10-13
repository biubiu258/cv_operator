import axios from 'axios'

// 后端服务地址（前端直连；后端已开启 CORS）
export const API_BASE = 'http://127.0.0.1:8000'

// WebSocket 服务地址（进度推送）
export const WS_BASE = API_BASE.replace(/^http/, 'ws')

const http = axios.create({
  baseURL: API_BASE,
  timeout: 240000
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const detail = err.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : (err.message || '请求失败')
    return Promise.reject(new Error(msg))
  }
)

export const downloadUrl = (resumeId, format = 'docx') =>
  `${API_BASE}/resumes/${resumeId}/download?format=${format}`

export default http