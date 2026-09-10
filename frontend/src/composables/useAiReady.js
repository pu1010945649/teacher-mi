import api from '../api'
import { ElMessage } from 'element-plus'

export const AI_UNREADY_TIP =
  'AI 功能不可用：请先在「设置」打开「启用 AI 功能」，并配置自己的模型或联系管理员开放默认模型'

/**
 * 教师 AI 功能统一前置校验（所有 AI 调用点必须使用，禁止各自实现）。
 * 后端 /ai/config 的 ai_allowed 统一判定：总开关已开，且自己的模型可用 或 管理员已开放并启用默认模型。
 * 返回 true 表示可调用；false 时已弹出统一提示。
 */
export async function ensureAiReady() {
  try {
    const cfg = await api.get('/ai/config')
    if (cfg.ai_allowed) return true
  } catch {
    return false // 请求失败已由拦截器提示
  }
  ElMessage.warning(AI_UNREADY_TIP)
  return false
}
