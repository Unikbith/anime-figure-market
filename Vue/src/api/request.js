import axios from 'axios'
import { API_BASE_URL } from '@/config'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true // 开启跨域凭证支持
})

api.interceptors.request.use(
  (config) => {
    config.headers = config.headers || {}

    const adminToken = sessionStorage.getItem('adminToken')
    const userToken = sessionStorage.getItem('token')
    const token = adminToken || userToken

    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    if (process.env.NODE_ENV === 'development') {
      console.log(`[请求] ${config.method.toUpperCase()} ${config.url}`, config.data || config.params)
    }

    return config
  },
  (error) => {
    console.error('[请求错误]', error)
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  (response) => {
    if (process.env.NODE_ENV === 'development') {
      console.log(`[响应] ${response.config.url}`, response.data)
    }
    return response
  },
  (error) => {
    console.error('[响应错误]', error)
    if (!error.response) {
      console.error('网络连接失败，请检查后端服务是否启动或网络是否正常')
      return Promise.reject(new Error('网络连接失败'))
    }
    const status = error.response.status
    if (status === 401) {
      const isAdminPage = window.location.pathname.startsWith('/admin')
      sessionStorage.clear()

      if (isAdminPage) {
        console.error('管理员登录已过期，请重新登录')
        window.location.href = '/admin/login'
      } else {
        console.error('登录已过期，请重新登录')
        window.location.href = '/login'
      }
    }
    else if (status === 403) {
      const msg = error.response.data?.msg || '您没有权限执行此操作'
      console.error(msg)
    }
    else if (status >= 500) {
      console.error('服务器内部错误，请稍后重试')
    }
    return Promise.reject(error)
  }
)

export default api

// 用于无需登录态、且不希望在 token 过期时触发 401 自动跳转的公开接口，
// 但**不附带 Authorization、不做登录跳转**。全站统一从此处引入，避免各处重复创建。
export const publicApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})
