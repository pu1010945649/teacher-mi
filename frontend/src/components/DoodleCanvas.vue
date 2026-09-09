<template>
  <div class="doodle-wrap">
    <div class="toolbar">
      <el-radio-group v-model="tool" size="small">
        <el-radio-button value="pen">画笔</el-radio-button>
        <el-radio-button value="eraser">橡皮</el-radio-button>
      </el-radio-group>
      <el-color-picker v-model="color" size="small" :predefine="['#e63946', '#1d3557', '#f4a261', '#2a9d8f', '#000000']" />
      <el-slider v-model="lineWidth" :min="1" :max="12" size="small" style="width: 100px" />
      <el-button size="small" @click="undo">撤销</el-button>
      <el-button size="small" @click="clearAll">清空</el-button>
      <span v-if="pdfInfo" class="page-nav">
        <el-button size="small" :disabled="page <= 1" @click="goPage(page - 1)">上一页</el-button>
        {{ page }} / {{ pdfInfo.numPages }}
        <el-button size="small" :disabled="page >= pdfInfo.numPages" @click="goPage(page + 1)">下一页</el-button>
      </span>
    </div>
    <div class="canvas-box" v-loading="loading">
      <canvas ref="canvasRef" @pointerdown="down" @pointermove="move"
              @pointerup="up" @pointerleave="up" />
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as pdfjsLib from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker

const props = defineProps({ src: String, name: String })
const emit = defineEmits(['export'])

const canvasRef = ref(null)
const tool = ref('pen')
const color = ref('#e63946')
const lineWidth = ref(3)
const loading = ref(false)
const page = ref(1)
const pdfInfo = ref(null)

let ctx = null
let drawing = false
let history = []
let pdfDoc = null
let pageImgCache = {}

function setupCanvas(img) {
  const canvas = canvasRef.value
  const maxW = canvas.parentElement.clientWidth - 4
  const scale = Math.min(1, maxW / img.width)
  canvas.width = Math.round(img.width * scale)
  canvas.height = Math.round(img.height * scale)
  ctx = canvas.getContext('2d')
  redraw(img)
}

function redraw(img) {
  ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
  ctx.drawImage(img, 0, 0, canvasRef.value.width, canvasRef.value.height)
}

function snapshot() {
  history.push(ctx.getImageData(0, 0, canvasRef.value.width, canvasRef.value.height))
  if (history.length > 30) history.shift()
}

function pos(e) {
  const rect = canvasRef.value.getBoundingClientRect()
  const scaleX = canvasRef.value.width / rect.width
  const scaleY = canvasRef.value.height / rect.height
  return [(e.clientX - rect.left) * scaleX, (e.clientY - rect.top) * scaleY]
}

function down(e) {
  drawing = true
  snapshot()
  ctx.beginPath()
  ctx.moveTo(...pos(e))
  canvasRef.value.setPointerCapture(e.pointerId)
}

function move(e) {
  if (!drawing) return
  const [x, y] = pos(e)
  ctx.globalCompositeOperation = tool.value === 'eraser' ? 'destination-out' : 'source-over'
  ctx.strokeStyle = color.value
  ctx.lineWidth = tool.value === 'eraser' ? lineWidth.value * 4 : lineWidth.value
  ctx.lineCap = ctx.lineJoin = 'round'
  ctx.lineTo(x, y)
  ctx.stroke()
}

function up() {
  drawing = false
  ctx.globalCompositeOperation = 'source-over'
}

function undo() {
  if (!history.length) return
  ctx.putImageData(history.pop(), 0, 0)
}

function clearAll() {
  snapshot()
  redraw(currentBase)
}

async function loadPdf() {
  pdfDoc = await pdfjsLib.getDocument(props.src).promise
  pdfInfo.value = { numPages: pdfDoc.numPages }
  page.value = 1
  pageImgCache = {}
  await renderPage(1)
}

async function renderPage(n) {
  const p = await pdfDoc.getPage(n)
  const vp = p.getViewport({ scale: 2 })
  const off = document.createElement('canvas')
  off.width = vp.width
  off.height = vp.height
  await p.render({ canvasContext: off.getContext('2d'), viewport: vp }).promise
  pageImgCache[n] = off
  currentBase = off
  setupCanvas(off)
}

async function goPage(n) {
  loading.value = true
  page.value = n
  try {
    if (pageImgCache[n]) {
      currentBase = pageImgCache[n]
      setupCanvas(pageImgCache[n])
    } else {
      await renderPage(n)
    }
  } finally {
    loading.value = false
  }
}

let currentBase = null

async function init() {
  loading.value = true
  history = []
  pdfInfo.value = null
  try {
    if (/\.pdf$/i.test(props.name || '')) {
      await loadPdf()
    } else {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.src = props.src
      await new Promise((ok, err) => { img.onload = ok; img.onerror = err })
      currentBase = img
      setupCanvas(img)
    }
  } catch {
    ElMessage.error('文件加载失败')
  } finally {
    loading.value = false
  }
}

/** 导出当前涂鸦结果为 PNG File（供上传） */
async function exportFile(originName) {
  if (!canvasRef.value) return null
  const blob = await new Promise(ok => canvasRef.value.toBlob(ok, 'image/png'))
  const base = (originName || 'annotated').replace(/\.[^.]+$/, '')
  return new File([blob], `${base}_批注.png`, { type: 'image/png' })
}

defineExpose({ exportFile })
onMounted(init)
onBeforeUnmount(() => { pdfDoc?.destroy() })
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.page-nav { font-size: 13px; color: #666; }
.canvas-box {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  overflow: auto;
  max-height: 60vh;
  background: #fafafa;
  text-align: center;
}
canvas { max-width: 100%; touch-action: none; cursor: crosshair; }
</style>
