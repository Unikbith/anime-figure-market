<template>
  <div class="home-page">
    <div class="page-container">
      
      <div class="hero-carousel">
        <swiper
          :modules="modules"
          :slides-per-view="'auto'"
          :centered-slides="true"
          :space-between="-140"
          :speed="600"
          :loop="true"
          :grab-cursor="true"
          @swiper="onSwiper"
          @slideChange="onSlideChange"
          class="carousel-swiper">
          <swiper-slide 
            v-for="(slide, index) in carouselSlides" 
            :key="index"
            class="carousel-slide">
            
            <div class="card-bg" :style="{ backgroundImage: `url(${slide.image})` }"></div>
            
            <div class="card-footer">
              <span class="card-title">{{ slide.title }}</span>
              <button class="card-btn">{{ slide.buttonText }}</button>
            </div>
          </swiper-slide>
        </swiper>
      </div>

      
      <div class="title-row">
        <h2 class="page-title">热门商品推荐</h2>
        <div class="btn-group">
          <button class="recommend-btn" @click="openRecommend" :disabled="recommendLoading">
            <span class="recommend-icon">♡</span>
            猜你喜欢
          </button>
        </div>
      </div>

      <LoadingState v-if="loading" message="正在加载商品..." />
      <EmptyState v-else-if="goodsList.length === 0" message="暂无商品，快去上架吧~" />
      <GoodsGrid v-else>
        <GoodsCard
          v-for="goods in goodsList"
          :key="goods.id"
          :goods="goods"
        />
      </GoodsGrid>

      
      <div v-if="!loading && goodsList.length > 0" ref="sentinelRef" class="load-sentinel">
        <span v-if="loadingMore" class="load-hint">正在加载更多…</span>
        <span v-else-if="!hasMore" class="load-hint">— 已经到底啦 —</span>
      </div>
    </div>

    
    <AppDialog v-model="showRecommendModal" title="猜你喜欢" width="320px" gradient>
      <LoadingState v-if="recommendLoading" :spinner="false" message="正在分析您的偏好..." />
      <EmptyState v-else-if="recommendGoods.length === 0" message="暂无推荐商品" />
      <div v-else class="recommend-single">
        <GoodsCard
          :key="recommendGoods[0].id"
          :goods="recommendGoods[0]"
        />
      </div>
    </AppDialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import request from '@/api/request'
import GoodsCard from '@/components/goodsCard.vue'
import LoadingState from '@/components/LoadingState.vue'
import EmptyState from '@/components/EmptyState.vue'
import GoodsGrid from '@/components/GoodsGrid.vue'
import AppDialog from '@/components/AppDialog.vue'
import { showAlert } from '@/utils/modal'
import { useInfiniteLoad } from '@/composables/useInfiniteLoad'
import { Swiper, SwiperSlide } from 'swiper/vue'
import { Pagination, Autoplay } from 'swiper/modules'
import 'swiper/css'
import 'swiper/css/pagination'

import carousel1 from '@/assets/images/轮播图.webp'
import carousel2 from '@/assets/images/轮播图1.webp'
import carousel3 from '@/assets/images/轮播图2.webp'
import carousel4 from '@/assets/images/轮播图3.jfif'
import carousel5 from '@/assets/images/轮播图4.webp'

const modules = [Pagination, Autoplay]

let swiperInstance = null
const onSwiper = (swiper) => {
  swiperInstance = swiper
}

const {
  list: goodsList, loading, loadingMore, hasMore, sentinelRef
} = useInfiniteLoad(
  (page, size) => request.get('/api/goods/list', { params: { page, size } }),
  res => res.data.data,
  res => res.data.pagination?.total,
  20
)

const currentSlide = ref(0)
// 轮播运营位：优先取管理后台配置的 /api/banners（避免前端硬编码），
const carouselSlides = ref([
  { image: carousel1, title: '热门手办推荐', buttonText: '查看详情' },
  { image: carousel2, title: '新品抢先看', buttonText: '查看详情' },
  { image: carousel3, title: '品质甄选', buttonText: '查看详情' },
  { image: carousel4, title: '限量典藏', buttonText: '查看详情' },
  { image: carousel5, title: '人气热销', buttonText: '查看详情' }
])

const loadBanners = async () => {
  try {
    const res = await request.get('/api/banners')
    if (res.data.code === 200 && Array.isArray(res.data.data) && res.data.data.length) {
      carouselSlides.value = res.data.data.map(b => ({
        image: b.image, title: b.title, buttonText: b.button_text, link: b.link
      }))
    }
  } catch (err) {
    console.error('轮播加载失败，使用内置图:', err)
  }
}
loadBanners()

const onSlideChange = (swiper) => {
  currentSlide.value = swiper.realIndex
}

const showRecommendModal = ref(false)
const recommendGoods = ref([])
const recommendLoading = ref(false)

const openRecommend = async () => {
  showRecommendModal.value = true
  recommendLoading.value = true
  try {
    const res = await request.get('/api/recommend/personal')
    if (res.data.code === 200) {
      recommendGoods.value = res.data.data || []
    }
  } catch (err) {
    console.error('获取推荐失败:', err)
    await showAlert('获取推荐失败，请稍后重试', '', 'error')
  } finally {
    recommendLoading.value = false
  }
}

</script>

<style scoped>

.home-page {
  min-height: 100vh;
  padding: 80px 40px;
  box-sizing: border-box;
  background: #f0f5fa;
}

.hero-carousel {
  position: relative;
  width: 100%;
  height: 500px;
  margin-bottom: 24px;
  overflow: hidden;
}

.carousel-swiper {
  width: 100%;
  height: 100%;
}

.carousel-slide {
  position: relative;
  width: 600px;
  height: 100%;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  opacity: 0.4;
  transition: opacity 0.5s ease;
}

.carousel-slide.swiper-slide-active {
  z-index: 10;
  opacity: 1;
}

.carousel-slide.swiper-slide-prev,
.carousel-slide.swiper-slide-next {
  z-index: 5;
  opacity: 0.4;
}

.card-bg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 88%;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

.card-footer {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: auto;
  background: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  box-sizing: border-box;
}

.card-title {
  font-size: 15px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0;
  line-height: 1.2;
}

.card-btn {
  padding: 6px 18px;
  font-size: 13px;
  font-weight: 500;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
  flex-shrink: 0;
  white-space: nowrap;
}

.card-btn:hover {
  background: #1d4ed8;
}

.page-container {
  max-width: 1200px;
  margin: 0 auto;
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #212121;
  margin: 0;
}

.btn-group {
  display: flex;
  gap: 12px;
}

.recommend-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 16px;
  font-size: 14px;
  color: #fb7299;
  background: #fff;
  border: 1px solid #fb7299;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.recommend-btn:hover {
  background: var(--brand-soft);
  border-color: #fb7299;
  color: #fb7299;
}

.recommend-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.recommend-icon {
  font-size: 16px;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 16px;
  font-size: 14px;
  color: #fb7299;
  background: #fff;
  border: 1px solid #fb7299;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover {
  background: #fb7299;
  color: #fff;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.refresh-icon {
  font-size: 16px;
}

@media (max-width: 1024px) {
  .hero-carousel {
    height: 420px;
  }
  .carousel-slide {
    width: 480px;
  }
  .card-bg {
    height: 76%;
  }
  .card-footer {
    padding: 7px 12px;
  }
  .card-title {
    font-size: 13px;
  }
  .card-btn {
    padding: 4px 12px;
    font-size: 10px;
  }
}

@media (max-width: 768px) {
  .home-page {
    padding: 70px 16px;
  }
  
  
  .hero-carousel {
    height: 380px;
    margin-bottom: 20px;
  }

  .carousel-slide {
    width: 400px;
  }

  .card-bg {
    height: 74%;
  }
  .card-footer {
    padding: 6px 10px;
  }
  .card-title {
    font-size: 12px;
  }
  .card-btn {
    padding: 4px 10px;
    font-size: 10px;
    border-radius: 3px;
  }
}

@media (max-width: 480px) {
  .home-page {
    padding: 60px 12px;
  }
  .page-title {
    font-size: 16px;
  }
  .refresh-btn, .recommend-btn {
    padding: 4px 12px;
    font-size: 12px;
  }
  
  
  .hero-carousel {
    height: 320px;
    margin-bottom: 16px;
  }

  .carousel-slide {
    width: 300px;
  }

  .card-bg {
    height: 72%;
  }
  .card-footer {
    padding: 5px 8px;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  .card-title {
    font-size: 11px;
  }
  .card-btn {
    width: 100%;
    padding: 4px 8px;
    font-size: 10px;
    text-align: center;
  }
}

.recommend-single {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
</style>
