<script setup lang="ts">
// 根组件：固定「顶部标题 + 导航栏」，主区用 <RouterView> 渲染当前路由对应的页面。
// RouterLink / RouterView 由 app.use(router) 全局注册，模板中直接使用、无需 import。
// 注意：占位符必须放 script（字符串）里替换，不能直接写在 template 中——{{ }} 是 Vue 插值语法。
const APP_TITLE = '演示系统'
</script>

<template>
  <el-container class="app-shell">
    <el-header class="app-header" height="56px">
      <span class="app-title">{{ APP_TITLE }}</span>
      <nav class="app-nav">
        <RouterLink class="nav-link" to="/">列表</RouterLink>
        <RouterLink class="nav-link" to="/items/new">新建</RouterLink>
      </nav>
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
.app-nav {
  display: flex;
  gap: 16px;
}
.nav-link {
  padding: 4px 8px;
  border-radius: 4px;
  color: var(--el-text-color-regular, #606266);
  text-decoration: none;
}
.nav-link:hover {
  color: var(--el-color-primary, #409eff);
}
/* vue-router 运行时给激活链接追加 .router-link-active 类，用于高亮当前页 */
.nav-link.router-link-active {
  color: var(--el-color-primary, #409eff);
  font-weight: 600;
}
.app-main {
  padding: 20px;
  background: #f5f7fa;
}
</style>
