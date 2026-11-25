<script setup lang="ts">
// 根组件：固定「顶部标题」，主区用 <RouterView> 渲染当前路由对应的页面。
// RouterLink / RouterView 由 app.use(router) 全局注册，模板中直接使用、无需 import。
// 注意：占位符必须放 script（字符串）里替换，不能直接写在 template 中——{{ }} 是 Vue 插值语法。
const APP_TITLE = '演示系统'
</script>

<template>
  <el-container class="app-shell">
    <el-header class="app-header" height="56px">
      <span class="app-title">{{ APP_TITLE }}</span>
      <!-- 业务接入：在此追加导航 <RouterLink class="nav-link" to="/xxx">…</RouterLink> -->
    </el-header>
    <el-main class="app-main">
      <RouterView />
    </el-main>
  </el-container>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
}
.app-header {
  display: flex;
  align-items: center;
  gap: 24px;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color, #dcdfe6);
}
.app-title {
  font-size: 18px;
  font-weight: 600;
}
.app-main {
  padding: 20px;
  background: #f5f7fa;
}
</style>
