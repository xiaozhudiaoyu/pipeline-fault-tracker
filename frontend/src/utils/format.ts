// 展示层格式化工具（纯函数，无第三方依赖——预授权清单无 dayjs，用原生 Date 即可，规则 2.6/3.1）。

// 把后端返回的 ISO 8601 字符串格式化为本地「YYYY-MM-DD HH:mm:ss」。
// 空值显示占位符「—」；无法解析时原样返回，避免显示 Invalid Date。
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`
    // `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  )
}

// 字节数人性化显示（附件体积展示）：不足 1MB 用 KB，否则 MB，均保留一位小数。
// 仅展示用途，不做单位换算精度保证（KB=1024、MB=1024²）。
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
