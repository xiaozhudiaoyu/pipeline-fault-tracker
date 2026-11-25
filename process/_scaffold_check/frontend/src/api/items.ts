// 示例实体接口封装：对应后端 routers/items.py 的五个端点。
import { request } from './client'
import type {
  Item,
  ItemCreatePayload,
  ItemList,
  ItemListParams,
  ItemUpdatePayload,
} from '../types/item'

// GET /api/items —— 分页查询（按状态筛选，created_at 倒序）。
export function fetchItems(params: ItemListParams = {}, signal?: AbortSignal): Promise<ItemList> {
  return request<ItemList>('/api/items', { query: { ...params }, signal })
}

// GET /api/items/{id} —— 单条详情（不存在返回 404 item_not_found）。
export function fetchItem(id: number, signal?: AbortSignal): Promise<Item> {
  return request<Item>(`/api/items/${id}`, { signal })
}

// POST /api/items —— 创建（成功 201；名称重复 409；校验失败 422）。
export function createItem(payload: ItemCreatePayload): Promise<Item> {
  return request<Item>('/api/items', { method: 'POST', body: payload })
}

// PATCH /api/items/{id} —— 部分更新（404 不存在 / 409 名称冲突 / 422 校验）。
export function updateItem(id: number, payload: ItemUpdatePayload): Promise<Item> {
  return request<Item>(`/api/items/${id}`, { method: 'PATCH', body: payload })
}

// DELETE /api/items/{id} —— 删除（204 成功 / 404 不存在）。
export function deleteItem(id: number): Promise<void> {
  return request<void>(`/api/items/${id}`, { method: 'DELETE' })
}
