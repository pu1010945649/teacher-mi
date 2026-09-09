import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({ baseURL: '/api', timeout: 120000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (resp) => resp.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      if (!location.hash.includes('/login')) location.hash = '#/login'
    }
    ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    return Promise.reject(error)
  },
)

export default api

/** 文件下载/图片加载场景：img、a、window.open 无法携带请求头，改用 ?token= 查询参数鉴权 */
export function authUrl(path) {
  return `${path}?token=${localStorage.getItem('token') || ''}`
}
