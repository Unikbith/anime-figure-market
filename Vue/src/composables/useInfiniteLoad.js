import { ref, onMounted, onUnmounted, nextTick } from 'vue'

/**
 * 无限滚动加载（虚拟列表）可复用组合式函数
 *
 * 用法：
 *   const { list, loading, loadingMore, hasMore, sentinelRef, load } = useInfiniteLoad(
 *     (page, size) => request.get('/api/goods/list', { params: { page, size, ...extra } }),
 *     res => res.data.data,            // 从响应取列表
 *     res => res.data.pagination.total // 从响应取总数（可选）
 *   )
 *
 * @param {Function} fetcher (page, size) => Promise<响应>
 * @param {Function} pickList 从响应中取出列表数组
 * @param {Function} [pickTotal] 从响应中取出总数
 * @param {number} [size=20] 每页条数
 */
export function useInfiniteLoad(fetcher, pickList, pickTotal, size = 20) {
  const list = ref([])
  const loading = ref(false)       // 首屏加载
  const loadingMore = ref(false)   // 触底追加中
  const hasMore = ref(true)
  const total = ref(0)
  const page = ref(1)
  const sentinelRef = ref(null)
  let observer = null

  const load = async (reset = false) => {
    if (reset) {
      page.value = 1
      list.value = []
      total.value = 0
      hasMore.value = true
      loading.value = true
    } else {
      if (loadingMore.value || !hasMore.value || loading.value) return
      loadingMore.value = true
    }
    try {
      const res = await fetcher(page.value, size)
      const items = pickList(res) || []
      list.value.push(...items)
      total.value = pickTotal ? pickTotal(res) : list.value.length
      hasMore.value = list.value.length < total.value && items.length > 0
      page.value += 1
    } catch (err) {
      console.error('加载失败:', err)
    } finally {
      loading.value = false
      loadingMore.value = false
    }
  }

  const setupObserver = async () => {
    await nextTick()
    observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasMore.value && !loading.value && !loadingMore.value) {
        load(false)
      }
    }, { rootMargin: '200px' })
    if (sentinelRef.value) observer.observe(sentinelRef.value)
  }

  onMounted(async () => {
    await load(true)
    await setupObserver()
  })

  onUnmounted(() => { if (observer) observer.disconnect() })

  return { list, loading, loadingMore, hasMore, total, sentinelRef, load }
}
