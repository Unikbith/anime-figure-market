// 注意：Vite 只会把 VITE_ 前缀的变量注入浏览器，后端密钥不会进入前端产物。

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// 前端支付网关地址（用于生成扫码支付的二维码 URL）
// 注意：若非正式线上支付网关，请在 .env 中替换 VITE_PAY_GATEWAY_URL
export const PAY_GATEWAY_URL = import.meta.env.VITE_PAY_GATEWAY_URL || ''
