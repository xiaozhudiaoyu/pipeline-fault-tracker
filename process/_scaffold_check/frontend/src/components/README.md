# components/ —— 复用组件目录

模板默认不包含业务组件：示例页面（views/）直接使用 Element Plus 组件组装。

需要抽取复用组件时（被 ≥2 个页面/组件引用的 UI 块），放此目录，命名 PascalCase，
组件级样式一律写在 `<style scoped>` 内。
