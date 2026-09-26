import { createRouter, createWebHistory } from 'vue-router'

const HomeView = () => import('@/views/homeView.vue')
const GoodsView = () => import('@/views/goodsView.vue')
const LoginView = () => import('@/views/loginView.vue')
const RegisterView = () => import('@/views/registerView.vue')
const ResetPasswordView = () => import('@/views/resetPasswordView.vue')
const GoodsCartView = () => import('@/views/goodsCartView.vue')
const GoodsDetailView = () => import('@/views/goodsDetailView.vue')
const SearchView = () => import('@/views/searchView.vue')
const ProfileView = () => import('@/views/profileView.vue')
const PublishView = () => import('@/views/publishView.vue')
const StatusView = () => import('@/views/base/statusView.vue')
const AdminLoginView = () => import('@/views/admin/adminLoginView.vue')
const AdminView = () => import('@/views/admin/adminView.vue')
const MonitorView = () => import('@/views/admin/monitorView.vue')
const IpView = () => import('@/views/base/ipView.vue')
const RoleView = () => import('@/views/base/roleView.vue')
const BrandView = () => import('@/views/base/brandView.vue')
const ConfirmPayView = () => import('@/views/confirmPayView.vue')
const OrderSettlementView = () => import('@/views/orderSettlementView.vue')

const getUserToken = () => sessionStorage.getItem('token')
const getUserRole = () => sessionStorage.getItem('userRole')
const getAdminToken = () => sessionStorage.getItem('adminToken')

const whiteList = ['/login', '/register', '/reset-password', '/admin/login', '/']

const merchantGuard = (to, from, next) => {
  const token = getUserToken()
  const role = getUserRole()
  if (token && role === 'merchant') {
    next()
  } else if (!token) {
    next('/login')
  } else {
    next('/')
  }
}

const adminGuard = (to, from, next) => {
  if (getAdminToken()) {
    next()
  } else {
    next('/admin/login')
  }
}

const loginGuard = (to, from, next) => {
  if (getUserToken()) {
    next()
  } else {
    next('/login')
  }
}

const routes = [
  { path: '/', name: 'Home', component: HomeView },
  { path: '/goods', name: 'Goods', component: GoodsView },
  { path: '/login', name: 'Login', component: LoginView },
  { path: '/register', name: 'Register', component: RegisterView },
  { path: '/reset-password', name: 'ResetPassword', component: ResetPasswordView },
  { path: '/cart', name: 'Cart', component: GoodsCartView, beforeEnter: loginGuard },
  { path: '/goods/detail/:id', name: 'goodsDetail', component: GoodsDetailView },
  { path: '/search', name: 'Search', component: SearchView },
  { path: '/profile', name: 'Profile', component: ProfileView, beforeEnter: loginGuard },
  { path: '/publish', name: 'Publish', component: PublishView, beforeEnter: merchantGuard },
  { path: '/status', name: 'Status', component: StatusView, beforeEnter: loginGuard },
  { path: '/ip', name: 'Ip', component: IpView, beforeEnter: loginGuard },
  { path: '/brand', name: 'Brand', component: BrandView, beforeEnter: loginGuard },
  { path: '/role', name: 'Role', component: RoleView, beforeEnter: loginGuard },
  { path: '/confirmPay', name: 'ConfirmPay', component: ConfirmPayView, meta: { noGlobalLayout: true } },
  { path: '/orderSettlement', name: 'OrderSettlement', component: OrderSettlementView, beforeEnter: loginGuard },

  {
    path: '/admin',
    redirect: '/admin/login',
    children: [
      { path: 'login', name: 'AdminLogin', component: AdminLoginView, meta: { noGlobalLayout: true } },
      { path: 'dashboard', name: 'AdminDashboard', component: AdminView, beforeEnter: adminGuard, meta: { noGlobalLayout: true } },
      { path: 'monitor', name: 'AdminMonitor', component: MonitorView, beforeEnter: adminGuard, meta: { noGlobalLayout: true } }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior() {
    return { top: 0, left: 0 }
  }
})

router.beforeEach((to, from, next) => {
  if (whiteList.includes(to.path)) {
    next()
    return
  }
  next()
})

// 路由跳转后兜底恢复 body 滚动（防止弹窗未正常关闭遗留 overflow:hidden）
router.afterEach(() => {
  if (document.body.style.overflow === 'hidden') document.body.style.overflow = ''
})

export default router
