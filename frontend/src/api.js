import axios from 'axios'
import JSEncrypt from 'jsencrypt'
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

/** ---------- 登录敏感信息传输加密（RSA） ---------- */
let cachedPublicKey = ''
const encryptor = new JSEncrypt()

async function getPublicKey() {
  if (!cachedPublicKey) {
    // 公钥接口不需要鉴权，用独立请求避免拦截器报错
    const resp = await axios.get('/api/auth/public-key')
    cachedPublicKey = resp.data
    encryptor.setPublicKey(cachedPublicKey)
  }
  return cachedPublicKey
}

/** 将明文加密为传输密文（含时间戳防重放），登录/改密时使用 */
export async function encryptSensitive(plain) {
  await getPublicKey()
  const payload = JSON.stringify({ p: plain, t: Date.now() })
  const encrypted = encryptor.encrypt(payload)
  if (!encrypted) throw new Error('加密失败，请刷新页面重试')
  return encrypted
}
