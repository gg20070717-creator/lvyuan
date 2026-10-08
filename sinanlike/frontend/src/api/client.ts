import axios from 'axios'
import type { AxiosInstance } from 'axios'
import { cleanDisplayPayload } from '@/utils/displayText'

// ── 后端地址配置 ──
// 开发模式：Vite 代理 /api → http://127.0.0.1:18000（rewrite 去 /api 前缀）
// 生产模式（Electron）：直连后端端口
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string || '/api'

const client: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000,  // 3 分钟 — 生成训练材料需要多次 LLM 调用，后端实测约 90s
  headers: {
    'Content-Type': 'application/json',
  },
})

// ── 请求拦截器 ──
client.interceptors.request.use(
  (config) => {
    // 后续可在此注入 token 等
    return config
  },
  (error) => Promise.reject(error),
)

// ── 错误类型枚举（供视图层区分处理）──
export enum ApiErrorType {
  TIMEOUT = 'TIMEOUT',
  NETWORK = 'NETWORK',
  SERVER_ERROR = 'SERVER_ERROR',
  TASK_LOST = 'TASK_LOST',
  UNKNOWN = 'UNKNOWN',
}

export interface ApiError {
  type: ApiErrorType
  message: string
  statusCode?: number
  originalError: Error
}

export function classifyError(error: any): ApiError {
  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    return {
      type: ApiErrorType.TIMEOUT,
      message: '请求超时 — 后端处理中，请重试或简化需求',
      originalError: error,
    }
  }
  if (error.code === 'ERR_NETWORK' || error.code === 'ECONNREFUSED') {
    return {
      type: ApiErrorType.NETWORK,
      message: '后端未连接 — 请确认 API 服务已启动 （本机 18000 端口）',
      originalError: error,
    }
  }
  if (error.response) {
    return {
      type: ApiErrorType.SERVER_ERROR,
      message: `服务器错误 (${error.response.status})`,
      statusCode: error.response.status,
      originalError: error,
    }
  }
  return {
    type: ApiErrorType.UNKNOWN,
    message: error.message || '未知错误',
    originalError: error,
  }
}

// ── 响应拦截器 ──
client.interceptors.response.use(
  (response) => cleanDisplayPayload(response.data),
  (error) => {
    const classified = classifyError(error)
    if (classified.type === ApiErrorType.NETWORK) {
      console.warn(`[API] ${classified.message}`)
    } else if (classified.type === ApiErrorType.TIMEOUT) {
      console.warn(`[API] ${classified.message} (timeout=${client.defaults.timeout}ms)`)
    } else if (classified.type === ApiErrorType.SERVER_ERROR) {
      console.error(`[API] ${classified.message}:`, error.response?.data || error.message)
    } else {
      console.error('[API Error]', error.message)
    }
    // 将分类信息附加到 error 上，让视图层能读取
    error._apiError = classified
    return Promise.reject(error)
  },
)

// ── 健康检查 ──
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const base = API_BASE_URL === '/api' ? '' : API_BASE_URL
    // 开发模式下直接访问后端根路径（绕过 /api 代理前缀）
    const url = base || 'http://127.0.0.1:18000'
    const res = await axios.get(`${url}/`, { timeout: 3000 })
    return res.data?.status === 'ok'
  } catch {
    return false
  }
}

export default client
