// API 客户端：基于原生 fetch（预授权依赖清单无 axios，故用浏览器内置 fetch，规则 2.6/3.1）。
//
// 职责：
//   · 统一拼接 BASE_URL（VITE_API_BASE_URL）+ 路径 + 查询参数；
//   · 统一 JSON 序列化/反序列化；
//   · 第三阶段：统一注入 Authorization: Bearer（token 来自 utils/token 的 localStorage）；
//     已登录状态下收到 401（token 过期/被停用/被 bump 失效）触发登出回调跳登录页；
//   · 把非 2xx 响应转成携带后端 {code, message, details} 的 ApiError，供上层按 code 分支、按 details 标红。
import type { ApiErrorBody } from '../types/fault'
import { getToken, notifyUnauthorized } from '../utils/token'

// 后端源地址（见 frontend/.env.example）；接口路径自带 /api 前缀，故这里只拼源。
const BASE_URL = import.meta.env.VITE_API_BASE_URL

// 统一 API 错误：既保留 HTTP 状态码，也保留后端错误体，方便上层区分 404/409/422 与网络错误。
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: ApiErrorBody['details']

  constructor(status: number, body: ApiErrorBody) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.details = body.details ?? []
  }
}

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
type QueryValue = string | number | boolean | undefined | null

interface RequestOptions {
  method?: HttpMethod
  body?: unknown
  signal?: AbortSignal
  query?: Record<string, QueryValue>
}

// 拼接查询参数：跳过 undefined/null/空串，其余转字符串。
function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const url = `${BASE_URL}${path}`
  if (!query) return url
  const sp = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') {
      sp.append(key, String(value))
    }
  }
  const qs = sp.toString()
  return qs ? `${url}?${qs}` : url
}

// 通用请求：成功返回解析后的 JSON（T），失败抛 ApiError；网络层错误（服务未启动）由 fetch 抛 TypeError。
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, query } = options
  const hasBody = body !== undefined

  // 第三阶段：有 token 就带 Authorization 头（登录前无 token 照发，公开接口不受影响）。
  const token = getToken()
  const headers: Record<string, string> = {}
  if (hasBody) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(buildUrl(path, query), {
    method,
    signal,
    headers: Object.keys(headers).length > 0 ? headers : undefined,
    body: hasBody ? JSON.stringify(body) : undefined,
  })

  // 204 无内容
  if (resp.status === 204) {
    return undefined as T
  }

  const text = await resp.text()
  const data: unknown = text ? JSON.parse(text) : null

  if (!resp.ok) {
    // 携带 token 的请求收到 401 = 登录态已失效（过期/停用/改密 bump）：触发登出回调跳登录页。
    // 登录接口自身密码错误的 401 不算（无 token 不会进此分支）。
    if (resp.status === 401 && token) notifyUnauthorized()
    // 后端错误体统一为 {code, message, details}；非该结构（如网关返回的 HTML）时兜底。
    const errBody: ApiErrorBody =
      data !== null && typeof data === 'object' && 'code' in data
        ? (data as ApiErrorBody)
        : { code: `http_${resp.status}`, message: resp.statusText || `请求失败（${resp.status}）`, details: [] }
    throw new ApiError(resp.status, errBody)
  }

  return data as T
}
