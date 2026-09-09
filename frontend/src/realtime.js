/**
 * 站内实时刷新（SSE）：
 * - 登录后建立一条长连接，接收服务端推送的数据变更事件
 * - 页面通过 useRealtime 订阅感兴趣的事件类型，收到事件后自动刷新页面数据
 * - 无需刷新整个网页
 */
import { ElMessage } from 'element-plus'

let source = null
let currentToken = ''

// type -> Set<fn>
const listeners = {}

/** 事件类型对应的提示文案（收到推送时轻提示，可传空字符串关闭） */
const DEFAULT_TIPS = {
  assignment: '作业有更新，已为你刷新',
  submission: '学生提交了新作业，已为你刷新',
  feedback: '收到老师新反馈，已为你刷新',
  worksheet: '老师给你布置了新的个性化练习，已为你刷新',
  course: '课程有更新，已为你刷新',
  student: '学生名单有更新，已为你刷新',
}

function dispatch(type) {
  ;(listeners[type] || []).forEach((fn) => {
    try { fn() } catch (e) { console.error('realtime handler error', e) }
  })
}

/** 建立或断开连接（token 变化时在 App.vue 调用） */
export function syncRealtime(token) {
  if (!token || token === currentToken) {
    if (!token && source) { source.close(); source = null; currentToken = '' }
    return
  }
  currentToken = token
  if (source) source.close()
  source = new EventSource(`/api/events?token=${encodeURIComponent(token)}`)
  source.onmessage = (e) => {
    try {
      const ev = JSON.parse(e.data)
      dispatch(ev.type)
      if (DEFAULT_TIPS[ev.type]) ElMessage({ message: DEFAULT_TIPS[ev.type], type: 'info', duration: 2000 })
    } catch { /* 忽略无法解析的消息 */ }
  }
  // EventSource 断线会自动重连；错误时静默即可
  source.onerror = () => {}
}

/**
 * 页面订阅：收到 types 中任一事件时执行 handler（自动防抖）
 * @param {string[]|string} types 关心的事件类型
 * @param {Function} handler 刷新函数（通常是页面的 load）
 * @param {number} wait 防抖毫秒数
 */
export function useRealtime(types, handler, wait = 600) {
  const typeList = Array.isArray(types) ? types : [types]
  let timer = null
  const wrapped = () => {
    clearTimeout(timer)
    timer = setTimeout(handler, wait)
  }
  typeList.forEach((t) => {
    ;(listeners[t] ||= new Set()).add(wrapped)
  })
  return () => typeList.forEach((t) => listeners[t]?.delete(wrapped))
}
