<template>
  <div class="cart-page">
    <div class="container">
      <h2 class="page-title">我的购物车</h2>

      <LoadingState v-if="loading" message="正在加载购物车..." />

      <EmptyState v-else-if="cartList.length === 0" class="empty-cart" message="购物车为空，快去挑选商品吧~" />

      
      <div v-else class="cart-content">
        
        <div class="cart-item" v-for="item in cartList" :key="item.id">
          <img :src="item.image" alt="" class="item-img" @error="handleImgError">
          <div class="item-info">
            <h3 class="item-name">{{ item.name }}</h3>
            <p class="item-price">¥{{ item.price }}</p>
          </div>
          <div class="num-group">
            <button @click="updateNum(item, -1)" :disabled="item.num <= 1">-</button>
            <span>{{ item.num }}</span>
            <button @click="updateNum(item, 1)">+</button>
          </div>
          <button class="del-btn" @click="deleteItem(item.id)">删除</button>
        </div>

        
        <div class="cart-footer">
          <div class="total-price">
            合计：<span>¥{{ totalPrice }}</span>
          </div>
          <button
            class="pay-btn"
            @click="goToSettlement"
            :disabled="isSubmitting"
          >
            去结算
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/api/request'
import LoadingState from '@/components/LoadingState.vue'
import EmptyState from '@/components/EmptyState.vue'
import { showAlert, showConfirm } from '@/utils/modal'
import { handleImgError } from '@/utils/imageFallback'

const router = useRouter()

const cartList = ref([])
const loading = ref(false)
const isSubmitting = ref(false)

const getCartList = async () => {
  const token = sessionStorage.getItem('token')
  if (!token) {
    await showAlert('请先登录')
    router.push('/login')
    return
  }
  loading.value = true
  try {
    const res = await request.get('/api/cart/list')
    if (res.data.code === 200) cartList.value = res.data.data
  } catch (err) {
    await showAlert('购物车加载失败', '', 'error')
  } finally { loading.value = false }
}

const updateNum = async (item, step) => {
  const newNum = item.num + step
  try {
    await request.post('/api/cart/update', { id: item.id, num: newNum })
    item.num = newNum
  } catch (err) {
    await showAlert('修改数量失败', '', 'error')
  }
}

const deleteItem = async (id) => {
  if (!(await showConfirm('确定删除？'))) return
  try {
    await request.delete(`/api/cart/delete/${id}`)
    cartList.value = cartList.value.filter(i => i.id !== id)
  } catch (err) {
    await showAlert('删除失败', '', 'error')
  }
}

const totalPrice = computed(() => {
  return cartList.value.reduce((sum, item) => sum + item.price * item.num, 0).toFixed(2)
})

const goToSettlement = async () => {
  if (cartList.value.length === 0) {
    await showAlert('购物车为空，无法结算')
    return
  }

  router.push('/orderSettlement')
}

onMounted(() => { getCartList() })
</script>

<style scoped>

.cart-page {
  min-height: 100vh;
  padding: 80px 20px 40px;
  box-sizing: border-box;
  background: rgb(234, 243, 251);
}

.container {
  max-width: 1500px;
  margin: 0 auto;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  text-align: center;
  color: #212121;
  margin: 0 0 30px;
}

.cart-content {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
}

.cart-item {
  display: flex;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #f0f0f0;
}

.item-img {
  width: 100px;
  height: 100px;
  object-fit: contain;
  border-radius: 8px;
  background: #f9f9f9;
  margin-right: 20px;
}

.item-info {
  flex: 1;
}

.item-name {
  font-size: 16px;
  color: #333;
  margin: 0 0 8px;
}

.item-price {
  font-size: 20px;
  color: #fb7299;
  font-weight: 600;
  margin: 0;
}

.num-group {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 30px;
}

.num-group button {
  width: 32px;
  height: 32px;
  border: 1px solid #ddd;
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

.num-group button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.num-group span {
  min-width: 30px;
  text-align: center;
  font-size: 16px;
}

.del-btn {
  color: #ff4d4f;
  background: none;
  border: none;
  font-size: 14px;
  cursor: pointer;
}

.del-btn:hover {
  color: #ff7875;
}

.cart-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  background: #fafafa;
}

.total-price {
  font-size: 18px;
  color: #333;
}

.total-price span {
  font-size: 24px;
  color: #fb7299;
  font-weight: 600;
}

.pay-btn {
  background: #fb7299;
  color: #fff;
  border: none;
  padding: 12px 40px;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
}

.pay-btn:hover {
  opacity: 0.9;
}

.pay-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .cart-page {
    padding: 10px 0;
  }
  .container {
    padding: 0 12px;
  }
  .cart-item {
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px;
  }
  .item-img {
    width: 80px;
    height: 80px;
  }
  .item-info {
    flex: 1;
    min-width: 0;
  }
  .item-name {
    font-size: 14px;
  }
  .num-group {
    margin-left: 0;
  }
  .del-btn {
    margin-left: auto;
  }
  .cart-footer {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }
  .pay-btn {
    width: 100%;
  }
}
</style>
