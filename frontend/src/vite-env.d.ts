/// <reference types="vite/client" />

// 为项目专有的环境变量补充类型。
// vite/client 已声明 ImportMetaEnv 的通用字段，这里用「接口合并」追加 VITE_API_BASE_URL，
// 使 t5 的 API client 读取 import.meta.env.VITE_API_BASE_URL 时有类型提示与拼写保护。
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
