import { onBeforeUnmount, onMounted, ref } from 'vue'

/** 判断是否为手机等窄屏设备（< 768px），随窗口尺寸实时更新 */
export function useIsMobile() {
  const isMobile = ref(window.innerWidth < 768)
  const onResize = () => { isMobile.value = window.innerWidth < 768 }
  onMounted(() => window.addEventListener('resize', onResize))
  onBeforeUnmount(() => window.removeEventListener('resize', onResize))
  return { isMobile }
}
