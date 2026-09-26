<template>
  <div class="detail-page">

    <div v-if="!loading && goodsInfo.status === '下架'" class="off-shelf-banner">
      <span class="off-shelf-text">该商品已下架，暂时无法购买</span>
      <button class="back-link" @click="router.push('/')">返回首页</button>
    </div>
    <div class="container">

      
      <div class="back-nav" v-if="!loading">
        <button class="back-page-btn" @click="router.back()">‹ 返回上一页</button>
      </div>

      <LoadingState v-if="loading" message="正在加载商品详情..." />

      
      <div v-else class="main-content">
        
        <div class="image-section">
          <div class="main-img-wrap">
            <img :src="currentImg" :alt="goodsInfo.name" class="main-img" @error="handleImgError">
          </div>
          <div class="thumb-list" v-if="goodsInfo.images?.length > 1">
            <button class="arrow-btn prev" @click="prevImg" v-if="showPrevArrow">‹</button>
            <div class="thumb-scroll">
              <div 
                v-for="(img, index) in goodsInfo.images" 
                :key="index"
                class="thumb-item"
                :class="{ active: currentIndex === index }"
                @click="switchImg(index)"
              >
                <img :src="img" :alt="`缩略图${index+1}`" class="thumb-img" @error="handleImgError">
              </div>
            </div>
            <button class="arrow-btn next" @click="nextImg" v-if="showNextArrow">›</button>
          </div>
        </div>

        
        <div class="info-section">
          <h1 class="goods-title">{{ goodsInfo.name }}</h1>
          
          <div class="tags-row" v-if="tags.length">
            <span v-for="t in tags" :key="t" class="tag-pill">{{ t }}</span>
          </div>
          <div class="price-band">
            <div class="price-wrap">
              <span class="price-symbol">¥</span>
              <span class="price-num">{{ goodsInfo.price }}</span>
            </div>
            <span class="sales-info">已售 {{ goodsInfo.sales || 0 }}</span>
          </div>

          <div class="service-row">
            <span class="service-label">服务</span>
            <div class="service-list">
              <span v-for="s in serviceList" :key="s">{{ s }}</span>
            </div>
          </div>

          <div class="merchant-row">
            <img 
              :src="merchantAvatar" 
              :alt="goodsInfo.merchant_name" 
              class="merchant-avatar" 
              @error="handleMerchantAvatarError"
            >
            <span class="merchant-name">{{ goodsInfo.merchant_name || '官方店铺' }}</span>
          </div>

          
          <div class="buy-wrap" v-if="!isMerchant && !isAdmin">
            <div class="stock-info">
              <span>库存：{{ goodsInfo.stock }}件</span>
              <span v-if="goodsInfo.category">分类：{{ goodsInfo.category }}</span>
            </div>
            <div class="btn-group">
              <button 
                class="add-cart-btn" 
                @click="addToCart"
                :disabled="goodsInfo.stock <= 0 || goodsInfo.status === '下架'"
              >
                {{ goodsInfo.status === '下架' ? '已下架' : (goodsInfo.stock <= 0 ? '已售罄' : '加入购物车') }}
              </button>
              
              <button 
                class="collect-btn" 
                @click="toggleCollect"
                :disabled="collectLoading || goodsInfo.status === '下架'"
                :class="{ collected: isCollected }"
              >
                {{ collectLoading ? '处理中...' : (isCollected ? '已收藏' : '收藏') }}
              </button>
            </div>
          </div>

          
          <div class="base-info-list">
            <div class="info-item" v-if="goodsInfo.ip">
              <span class="info-label">所属IP</span>
              <span class="info-value">{{ goodsInfo.ip }}</span>
            </div>
            <div class="info-item" v-if="goodsInfo.character">
              <span class="info-label">角色名称</span>
              <span class="info-value">{{ goodsInfo.character }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">上架时间</span>
              <span class="info-value">{{ goodsInfo.created_at }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!loading" class="detail-bottom">
        <div class="detail-tabs">
          <button class="d-tab" :class="{ active: activeTab === 'detail' }" @click="activeTab = 'detail'">商品详情</button>
          <button class="d-tab" :class="{ active: activeTab === 'specs' }" @click="activeTab = 'specs'">规格参数</button>
          <button class="d-tab" :class="{ active: activeTab === 'comments' }" @click="activeTab = 'comments'">用户评论</button>
        </div>

        <div v-show="activeTab === 'detail'" class="tab-panel">
          <div class="detail-table-card">
            <div class="detail-table">
              <div class="table-row">
                <div class="table-cell">
                  <span class="cell-label">商品状态</span>
                  <span class="cell-value">{{ goodsInfo.status || '暂无' }}</span>
                </div>
                <div class="table-cell">
                  <span class="cell-label">品牌</span>
                  <span class="cell-value">{{ goodsInfo.brand || '暂无' }}</span>
                </div>
              </div>
              <div class="table-row">
                <div class="table-cell" v-if="goodsInfo.category">
                  <span class="cell-label">分类</span>
                  <span class="cell-value">{{ goodsInfo.category }}</span>
                </div>
                <div class="table-cell">
                  <span class="cell-label">库存</span>
                  <span class="cell-value">{{ goodsInfo.stock }} 件</span>
                </div>
              </div>
              <div class="table-row" v-if="goodsInfo.description">
                <div class="table-cell full-width">
                  <span class="cell-label">商品简介</span>
                  <span class="cell-value desc-text">{{ goodsInfo.description }}</span>
                </div>
              </div>
            </div>
          </div>

          
          <div class="img-card" v-if="restImages.length > 0">
            <h3 class="card-title">商品展示</h3>
            <div class="img-grid">
              <div
                v-for="(img, index) in restImages"
                :key="index"
                class="img-item"
              >
                <img
                  :src="img"
                  :alt="`商品图${index+1}`"
                  class="detail-img"
                  @error="handleImgError"
                >
              </div>
            </div>
          </div>
        </div>

        <div v-show="activeTab === 'specs'" class="tab-panel">
          <div class="detail-table-card">
            <div class="specs-table" v-if="specEntries.length">
              <div class="spec-row" v-for="[k, v] in specEntries" :key="k">
                <span class="spec-key">{{ k }}</span>
                <span class="spec-val">{{ v }}</span>
              </div>
            </div>
            <div v-else class="empty-state"><p>暂无规格参数</p></div>
          </div>
        </div>

        <div v-show="activeTab === 'comments'" class="tab-panel">
          <CommentSection :goods-id="goodsInfo.id" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request, { publicApi } from '@/api/request'
import { showAlert } from '@/utils/modal'
import LoadingState from '@/components/LoadingState.vue'
import CommentSection from '@/components/CommentSection.vue'

import DEFAULT_PLACEHOLDER from '@/assets/images/picture.png'

const route = useRoute()
const router = useRouter()

const userRole = computed(() => {
  const token = sessionStorage.getItem('adminToken') || sessionStorage.getItem('token')
  if (!token) return ''
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.role || ''
  } catch (e) {
    return ''
  }
})
const isMerchant = computed(() => userRole.value === 'merchant')
const isAdmin = computed(() => userRole.value === 'admin')
const isLoggedIn = computed(() => !!sessionStorage.getItem('token'))

const loading = ref(true)
const currentIndex = ref(0)
const isCollected = ref(false)
const collectLoading = ref(false)

const goodsInfo = ref({
  id: 0,
  name: '',
  price: 0,
  stock: 0,
  images: [],
  description: '',
  category: '',
  status: '',
  brand: '',
  ip: '',
  character: '',
  specs: {},
  tags: [],
  sales: 0,
  services: [],
  merchant_name: '',
  merchant_avatar: '',
  created_at: ''
})

const activeTab = ref('detail')
const tags = computed(() => goodsInfo.value.tags || [])
const specEntries = computed(() => Object.entries(goodsInfo.value.specs || {}))
// 服务承诺来自商品数据（商家发布时填写），未填写时给行业默认兜底
const serviceList = computed(() =>
  (goodsInfo.value.services && goodsInfo.value.services.length)
    ? goodsInfo.value.services
    : ['专业包装', '支持7天无理由', '48h内发货']
)

const currentImg = computed(() => {
  return goodsInfo.value.images?.[currentIndex.value] || DEFAULT_PLACEHOLDER
})

const restImages = computed(() => {
  if (!goodsInfo.value.images || goodsInfo.value.images.length <= 1) return []
  return goodsInfo.value.images.slice(1)
})

const showPrevArrow = computed(() => currentIndex.value > 0)
const showNextArrow = computed(() => currentIndex.value < goodsInfo.value.images?.length - 1)

const merchantAvatar = computed(() => {
  return goodsInfo.value.merchant_avatar || DEFAULT_PLACEHOLDER
})

const getGoodsDetail = async () => {
  const goodsId = route.params.id
  if (!goodsId) {
    await showAlert('商品参数错误', '', 'error')
    router.back()
    return
  }

  try {
    const res = await publicApi.get(`/api/goods/detail/${goodsId}`)
    if (res.data.code === 200) {
      goodsInfo.value = res.data.data
      checkIsCollected()
      // 记录用户浏览行为（用于猜你喜欢推荐）
      recordBrowseBehavior(goodsId)
      // 未登录/登录过期时静默失败即可
      if (sessionStorage.getItem('token')) {
        request.post('/api/user/history/add', { goods_id: Number(goodsId) }).catch(() => {})
      }
    } else {
      await showAlert(res.data.msg || '商品不存在', '', 'error')
      router.back()
    }
  } catch (err) {
    console.error('获取商品详情失败:', err)
    await showAlert('商品加载失败，请检查后端服务是否启动', '', 'error')
    router.back()
  } finally {
    loading.value = false
  }
}

const recordBrowseBehavior = async (goodsId) => {
  const token = sessionStorage.getItem('token')
  if (!token) return // 未登录不记录
  
  try {
    await request.post('/api/user/behavior', {
      goods_id: parseInt(goodsId),
      type: 'view'
    })
  } catch (err) {
    console.error('记录浏览行为失败:', err)
  }
}

const checkIsCollected = async () => {
  if (!isLoggedIn.value) return
  try {
    const res = await request.get('/api/collect/check', {
      params: { goods_id: goodsInfo.value.id }
    })
    if (res.data.code === 200) {
      isCollected.value = res.data.data.is_collected
    }
  } catch (err) {
    console.error('检查收藏状态失败:', err)
  }
}

const toggleCollect = async () => {
  if (!isLoggedIn.value) {
    await showAlert('请先登录')
    router.push('/login')
    return
  }
  collectLoading.value = true
  try {
    if (isCollected.value) {
      await request.post('/api/collect/delete', { goods_id: goodsInfo.value.id })
      isCollected.value = false
      await showAlert('已取消收藏')
    } else {
      await request.post('/api/collect/add', { goods_id: goodsInfo.value.id })
      isCollected.value = true
      await showAlert('收藏成功', '', 'success')
      await request.post('/api/user/behavior', { goods_id: goodsInfo.value.id, type: 'collect' }).catch(() => {})
    }
  } catch (err) {
    console.error('收藏操作失败:', err)
    await showAlert('操作失败，请重试', '', 'error')
  } finally {
    collectLoading.value = false
  }
}

const switchImg = (index) => {
  currentIndex.value = index
}

const prevImg = () => {
  if (currentIndex.value > 0) currentIndex.value--
}
const nextImg = () => {
  if (currentIndex.value < goodsInfo.value.images.length - 1) currentIndex.value++
}

const addToCart = async () => {
  const token = sessionStorage.getItem('token')
  if (!token) {
    await showAlert('请先登录')
    router.push('/login')
    return
  }

  try {
    const res = await request.post('/api/cart/add', {
      goods_id: goodsInfo.value.id
    })
    
    if (res.data.code === 200) {
      await showAlert(`已将「${goodsInfo.value.name}」加入购物车`, '', 'success')
    } else {
      await showAlert(res.data.msg, '', 'error')
    }
  } catch (err) {
    console.error(err)
    await showAlert('加入购物车失败，请重试', '', 'error')
  }
}

const handleImgError = (e) => {
  e.target.src = DEFAULT_PLACEHOLDER
}
const handleMerchantAvatarError = (e) => {
  e.target.src = DEFAULT_PLACEHOLDER
}

onMounted(() => {
  getGoodsDetail()
})
</script>

<style scoped>

.detail-page {
  min-height: 100vh;
  padding: 80px 20px 40px;
  box-sizing: border-box;
  background: #f4f4f4;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
}

.main-content {
  display: flex;
  gap: 40px;
  background: #fff;
  padding: 30px;
  border-radius: 12px;
  margin-bottom: 20px;
}

.image-section {
  flex: 1;
  max-width: 560px;
}

.main-img-wrap {
  width: 100%;
  height: 560px;
  border-radius: 8px;
  overflow: hidden;
  background: #f9f9f9;
  margin-bottom: 16px;
}

.main-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.thumb-list {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
}

.thumb-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  scroll-behavior: smooth;
  padding: 4px 0;
  width: 100%;
}

.thumb-scroll::-webkit-scrollbar {
  display: none;
}

.thumb-item {
  flex-shrink: 0;
  width: 80px;
  height: 80px;
  border-radius: 6px;
  overflow: hidden;
  border: 2px solid transparent;
  cursor: pointer;
  transition: border-color 0.2s;
}

.thumb-item.active {
  border-color: #fb7299;
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.arrow-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(0,0,0,0.5);
  color: #fff;
  border: none;
  font-size: 16px;
  line-height: 24px;
  text-align: center;
  cursor: pointer;
  z-index: 1;
}

.arrow-btn.prev {
  left: -12px;
}

.arrow-btn.next {
  right: -12px;
}

.info-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.tags-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 0 0 10px;
}
.tag-pill {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 20px;
  background: var(--brand-soft, rgba(251, 114, 153, 0.12));
  color: var(--brand, #fb7299);
  font-weight: 500;
}

.price-band {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(90deg, rgba(251, 114, 153, 0.08), rgba(251, 114, 153, 0.02));
  border-radius: 10px;
  padding: 14px 18px;
  margin-bottom: 16px;
}
.sales-info {
  font-size: 13px;
  color: var(--text-muted, #8c8c8c);
}

.tags-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 0 0 10px;
}
.tag-pill {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 20px;
  background: var(--brand-soft, rgba(251, 114, 153, 0.12));
  color: var(--brand, #fb7299);
  font-weight: 500;
}

.price-band {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(90deg, rgba(251, 114, 153, 0.08), rgba(251, 114, 153, 0.02));
  border-radius: 10px;
  padding: 14px 18px;
  margin-bottom: 16px;
}
.sales-info {
  font-size: 13px;
  color: var(--text-muted, #8c8c8c);
}

.goods-title {
  font-size: 22px;
  font-weight: 600;
  color: #212121;
  margin: 0;
  line-height: 1.4;
}

.price-wrap {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 16px;
  background: #fff5f5;
  border-radius: 8px;
}

.price-symbol {
  font-size: 18px;
  color: #ff4400;
}

.price-num {
  font-size: 36px;
  font-weight: 700;
  color: #ff4400;
}

.service-row {
  display: flex;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid #eee;
}

.service-label {
  font-size: 14px;
  color: #999;
  flex-shrink: 0;
}

.service-list {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.service-list span {
  font-size: 14px;
  color: #666;
}

.merchant-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #eee;
}

.merchant-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  background: #fb7299;
  flex-shrink: 0;
}

.merchant-name {
  font-size: 16px;
  font-weight: 500;
  color: #333;
}

.buy-wrap {
  margin-top: auto;
  padding: 20px;
  background: #f9f9f9;
  border-radius: 8px;
}

.stock-info {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  font-size: 14px;
  color: #666;
}

.btn-group {
  display: flex;
  gap: 16px;
}

.add-cart-btn {
  flex: 1;
  height: 48px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
  color: #fb7299;
  border: 1px solid #fb7299;
}

.add-cart-btn:hover {
  background: var(--brand-soft);
}

.add-cart-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.collect-btn {
  flex: 1;
  height: 48px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
  color: #ff9800;
  border: 1px solid #ff9800;
}
.collect-btn.collected {
  background: #ff9800;
  color: #fff;
  border: 1px solid #ff9800;
}
.collect-btn:hover:not(:disabled) {
  opacity: 0.9;
}
.collect-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.base-info-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 12px;
}

.info-item {
  display: flex;
  gap: 16px;
  font-size: 14px;
}

.info-label {
  color: #999;
  width: 80px;
  flex-shrink: 0;
}

.info-value {
  color: #333;
}

.detail-bottom {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 0 0 16px;
}

.img-card {
  padding: 24px 30px;
}

.detail-table-card {
  padding: 24px 30px;
  border-bottom: 1px solid #eee;
}

.detail-table {
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #e8e8e8;
}

.table-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid #e8e8e8;
}

.table-row:last-child {
  border-bottom: none;
}

.table-cell {
  padding: 16px 20px;
  background: #fafafa;
  display: flex;
  align-items: center;
  gap: 12px;
}

.table-cell.full-width {
  grid-column: 1 / -1;
  align-items: flex-start;
}

.cell-label {
  font-size: 14px;
  color: #999;
  flex-shrink: 0;
  width: 70px;
}

.cell-value {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  line-height: 1.6;
}

.desc-text {
  white-space: pre-line;
  font-weight: 400;
  color: #555;
  line-height: 1.9;
}

.img-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  justify-content: center;
}

.img-item {
  background: #ffffff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  transition: transform 0.2s;
}

.img-item:hover {
  transform: translateY(-2px);
}

.detail-img {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  background: #f9f9f9;
}

.off-shelf-banner {
  max-width: 1200px;
  margin: 0 auto 12px;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 8px;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.off-shelf-text {
  font-size: 15px;
  color: #cf1322;
  font-weight: 500;
}
.back-link {
  background: #fb7299;
  color: #fff;
  border: none;
  padding: 6px 16px;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
}
.back-link:hover {
  background: var(--brand-hover);
}

@media (max-width: 1024px) {
  .main-content {
    flex-direction: column;
  }
  .image-section {
    max-width: 100%;
  }
  .main-img-wrap {
    height: auto;
    aspect-ratio: 1/1;
  }
  .table-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .detail-page {
    padding: 10px 0;
  }
  .container {
    padding: 0 12px;
  }
  .main-content {
    flex-direction: column !important;
    padding: 16px;
    gap: 16px !important;
  }
  .image-section {
    width: 100% !important;
    max-width: 100% !important;
  }
  .main-img-wrap {
    max-height: 300px;
  }
  .info-section {
    width: 100% !important;
    max-width: 100% !important;
  }
  .goods-title {
    font-size: 18px !important;
  }
  .price-num {
    font-size: 28px !important;
  }
  .service-row, .merchant-row {
    flex-direction: column;
    gap: 8px;
  }
  .btn-group {
    flex-direction: column;
    gap: 10px;
  }
  .btn-group button {
    width: 100%;
  }
  .img-grid {
    flex-direction: column;
  }
  .img-item {
    width: 100%;
    box-sizing: border-box;
  }
  .detail-table-card, .img-card {
    padding: 12px;
  }
  .table-cell {
    padding: 12px 16px;
  }
}

.detail-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 16px;
  background: #fff;
  padding: 6px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  width: fit-content;
}
.d-tab {
  padding: 9px 22px;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-size: 14px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}
.d-tab:hover { color: var(--brand); }
.d-tab.active {
  background: var(--brand);
  color: #fff;
  font-weight: 500;
}
.tab-panel { animation: slide-in-up 280ms var(--ease-out) both; }

.specs-table { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
.spec-row {
  display: flex;
  padding: 13px 16px;
  border-bottom: 1px solid #f5f5f5;
  font-size: 14px;
}
.spec-row:nth-child(odd) { border-right: 1px solid #f5f5f5; }
.spec-key { color: #999; width: 90px; flex-shrink: 0; }
.spec-val { color: #333; font-weight: 500; }

@media (max-width: 768px) {
  .specs-table { grid-template-columns: 1fr; }
  .spec-row:nth-child(odd) { border-right: none; }
}

.detail-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 16px;
  background: #fff;
  padding: 6px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  width: fit-content;
}
.d-tab {
  padding: 9px 22px;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-size: 14px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}
.d-tab:hover { color: var(--brand); }
.d-tab.active {
  background: var(--brand);
  color: #fff;
  font-weight: 500;
}
.tab-panel { animation: slide-in-up 280ms var(--ease-out) both; }

.specs-table { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
.spec-row {
  display: flex;
  padding: 13px 16px;
  border-bottom: 1px solid #f5f5f5;
  font-size: 14px;
}
.spec-row:nth-child(odd) { border-right: 1px solid #f5f5f5; }
.spec-key { color: #999; width: 90px; flex-shrink: 0; }
.spec-val { color: #333; font-weight: 500; }

@media (max-width: 768px) {
  .specs-table { grid-template-columns: 1fr; }
  .spec-row:nth-child(odd) { border-right: none; }
}

.back-nav { margin-bottom: 12px; }
.back-page-btn {
  padding: 8px 18px;
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 20px;
  color: #666;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.back-page-btn:hover {
  color: var(--brand, #fb7299);
  border-color: var(--brand, #fb7299);
}
</style>
