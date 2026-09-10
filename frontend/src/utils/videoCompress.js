/**
 * 浏览器端视频压缩：播放原视频 → canvas 重绘降分辨率 → MediaRecorder 限码率重编码
 * 输出 webm（Chrome/Edge/Firefox）或 mp4（Safari），无需任何第三方依赖。
 * 压缩在用户浏览器完成，上传到后台的就是压缩后的文件。
 */

const TARGET_HEIGHT = 720   // 最长边压到 720p
const VIDEO_BITRATE = 1_000_000  // 视频码率 1Mbps（讲解视频足够清晰）
const AUDIO_BITRATE = 96_000     // 音频码率 96kbps
const FPS = 24

function pickMime() {
  const candidates = [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
    'video/mp4',  // Safari
  ]
  return candidates.find(t => window.MediaRecorder?.isTypeSupported?.(t)) || ''
}

export function isCompressSupported() {
  return typeof window.MediaRecorder === 'function'
    && typeof HTMLCanvasElement.prototype.captureStream === 'function'
    && !!pickMime()
}

/**
 * 压缩视频文件
 * @param {File} file 原视频
 * @param {(percent: number) => void} onProgress 进度回调 0-100
 * @returns {Promise<File>} 压缩后的文件
 */
export async function compressVideo(file, onProgress = () => {}) {
  if (!isCompressSupported()) throw new Error('当前浏览器不支持在线压缩')
  const mime = pickMime()
  if (!mime) throw new Error('当前浏览器不支持的视频编码格式')

  const url = URL.createObjectURL(file)
  const video = document.createElement('video')
  video.src = url
  video.muted = false
  video.volume = 0  // 静音播放避免外放，音频走 WebAudio 通道
  video.playsInline = true
  video.preload = 'auto'

  await new Promise((resolve, reject) => {
    video.onloadedmetadata = resolve
    video.onerror = () => reject(new Error('视频读取失败'))
  })

  // 目标分辨率：长边压到 720 以内，等比缩放
  let w = video.videoWidth
  let h = video.videoHeight
  if (!w || !h) throw new Error('无法读取视频尺寸')
  const long = Math.max(w, h)
  const ratio = Math.min(1, TARGET_HEIGHT / long)
  w = Math.round(w * ratio / 2) * 2  // 编码器要求偶数尺寸
  h = Math.round(h * ratio / 2) * 2

  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')

  // 音频：从视频元素提取，接进录制的流
  const audioCtx = new AudioContext()
  const dest = audioCtx.createMediaStreamDestination()
  let audioSource = null
  try {
    audioSource = audioCtx.createMediaElementSource(video)
    audioSource.connect(dest)
  } catch { /* 无音轨时继续 */ }

  const canvasStream = canvas.captureStream(FPS)
  const stream = new MediaStream([
    ...canvasStream.getVideoTracks(),
    ...dest.stream.getAudioTracks(),
  ])

  const chunks = []
  const recorder = new MediaRecorder(stream, {
    mimeType: mime,
    videoBitsPerSecond: VIDEO_BITRATE,
    audioBitsPerSecond: AUDIO_BITRATE,
  })
  recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data) }

  const done = new Promise((resolve, reject) => {
    recorder.onstop = resolve
    recorder.onerror = () => reject(new Error('录制失败'))
  })

  const duration = video.duration || 0
  let lastPct = 0
  const draw = () => {
    if (video.ended || video.paused) return
    ctx.drawImage(video, 0, 0, w, h)
    if (duration > 0) {
      const pct = Math.min(99, Math.round(video.currentTime / duration * 100))
      if (pct > lastPct) { lastPct = pct; onProgress(pct) }
    }
    requestAnimationFrame(draw)
  }

  recorder.start(1000)
  await video.play()
  draw()
  await new Promise(resolve => { video.onended = resolve })
  recorder.stop()
  await done
  audioCtx.close()
  URL.revokeObjectURL(url)

  const ext = mime.includes('mp4') ? 'mp4' : 'webm'
  const blob = new Blob(chunks, { type: mime.split(';')[0] })
  const name = file.name.replace(/\.[^.]+$/, '') + `_compressed.${ext}`
  const out = new File([blob], name, { type: blob.type })
  onProgress(100)
  return out
}

/** 是否需要压缩：大于该阈值（字节）才压缩，小文件直接传 */
const SKIP_THRESHOLD = 15 * 1024 * 1024
export function shouldCompress(file) {
  return file.size > SKIP_THRESHOLD
}
