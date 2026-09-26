// 图片加载失败时的统一兜底处理
// 注意：兜底图必须引用**源码内的资源**（交给 Vite 处理成正确 URL）。
// <img> 解不出图 → 再次触发 error → 又换成同一个坏地址 → 无限循环，
// 表现为首页疯狂闪屏 + 满屏 404。
import fallbackImg from '@/assets/images/picture.png'

export { fallbackImg }

/**
 * <img @error="handleImgError"> 的处理器
 * 同一个元素只兜底一次，避免兜底图也失败时陷入死循环
 */
export function handleImgError(e) {
  const img = e.target
  if (img.dataset.fallbackApplied === '1') return
  img.dataset.fallbackApplied = '1'
  img.src = fallbackImg
}
