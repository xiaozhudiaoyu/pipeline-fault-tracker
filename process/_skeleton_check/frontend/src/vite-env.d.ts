/// <reference types="vite/client" />

// Vite 环境变量类型（只暴露 VITE_ 前缀，见 .env.example）
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
