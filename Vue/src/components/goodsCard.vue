<template>
  <div class="goods-card slide-in-item" @click="goToDetail">
    
    <div class="img-wrap">
      <img
        :src="goods.images?.[0] || goods.image || fallbackImg"
        :alt="goods.name"
        class="goods-img"
        @error="handleImgError"
      >
      <div v-if="goods.status === '下架'" class="off-shelf-badge">已下架</div>
    </div>

    
    <div class="goods-info">
      <h3 class="goods-name">{{ goods.name }}</h3>
      <p class="goods-price">¥{{ goods.price }}</p>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { handleImgError, fallbackImg } from '@/utils/imageFallback'
const router = useRouter()

const props = defineProps({
  goods: {
    type: Object,
    required: true
  }
})

const goToDetail = () => {
  router.push(`/goods/detail/${props.goods.id}`)
}
</script>

<style scoped>

.goods-card {
  border-radius: 8px;
  padding: 0;
  width: 100%;
  box-sizing: border-box;
  background: #fff;
  transition: transform 0.2s, box-shadow 0.2s;
  cursor: pointer;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.goods-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}

.img-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  flex-shrink: 0;
}

.goods-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  background-color: #f8f8f8;
  border-radius: 8px 8px 0 0;
  user-select: none;
  -webkit-user-drag: none;
}

.off-shelf-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 4px;
  z-index: 1;
}

.goods-info {
  padding: 12px;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.goods-name {
  font-size: 14px;
  color: #333;
  margin: 0 0 6px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  text-overflow: ellipsis;
  min-height: 40px;
  font-weight: 400;
}

.goods-price {
  font-size: 18px;
  font-weight: 700;
  color: #fb7299;
  margin: 0;
  line-height: 1.2;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .goods-name {
    font-size: 12px;
    min-height: 34px;
    margin-bottom: 4px;
  }
  .goods-price {
    font-size: 15px;
  }
  .goods-info {
    padding: 8px;
  }
}
</style>
