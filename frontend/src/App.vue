<script setup lang="ts">
// 根组件：固定「顶部标题 + 导航栏」，主区用 <RouterView> 渲染当前路由对应的页面。
// RouterLink / RouterView 由 app.use(router) 全局注册，模板中直接使用、无需 import。
// 第三阶段 M6：登录页整条顶栏不渲染（未登录无导航/用户信息可展示）；登录后顶栏右侧
// 展示当前用户（姓名 + 角色）与登出，
// 「用户管理」入口仅管理员可见（体验层隐藏，真拦截在后端 /api/users 的 AdminUser 依赖）。
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { currentUser, isAdmin, logout } from './composables/useAuth'
import { FAULT_ROLE_META } from './types/user'

const route = useRoute()
const isLoginPage = computed(() => route.name === 'login')

// 角色文案：未知角色兜底显示原始值（防后端加新角色时前端白屏）
const roleLabel = computed(() => (currentUser.value ? FAULT_ROLE_META[currentUser.value.role]?.label ?? currentUser.value.role : ''))
</script>

<template>
  <el-container class="app-shell">
    <!-- 登录页隐藏整条顶栏（isLoginPage 既有判定复用），登录成功后自动出现 -->
    <el-header v-if="!isLoginPage" class="app-header" height="56px">
      <span class="app-title">流水线故障记录系统</span>
      <nav v-if="!isLoginPage" class="app-nav">
        <RouterLink class="nav-link" to="/">故障列表</RouterLink>
        <RouterLink class="nav-link" to="/faults/new">新建故障</RouterLink>
        <RouterLink v-if="isAdmin" class="nav-link" to="/users">用户管理</RouterLink>
      </nav>

      <!-- 顶栏右侧：当前用户 + 登出（仅登录后展示） -->
      <div v-if="!isLoginPage && currentUser" class="app-user">
        <span class="user-name">{{ currentUser.display_name }}</span>
        <el-tag size="small" disable-transitions>{{ roleLabel }}</el-tag>
        <!-- 竖分割线：身份信息与「登出」操作分隔（EP 内置组件，无新依赖） -->
        <el-divider class="user-divider" direction="vertical" />
        <el-button link type="danger" @click="logout">登出</el-button>
      </div>
    </el-header>
    <el-main class="app-main">
      <RouterView />
    </el-main>
  </el-container>
</template>

<style scoped>
.app-shell {
  /* 锁定视口高（非 min-height）：顶栏固定不动，溢出滚动发生在 el-main 内部
     （EP 的 .el-main 自带 flex:1 + overflow:auto，外壳高度一旦限定即生效）。
     高度链：html/body/#app 100%（main.css）→ .app-shell 100vh。 */
  height: 100vh;
}
.app-header {
  display: flex;
  align-items: center;
  gap: 24px;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color, #dcdfe6);
}
.app-title {
  /* 全局字阶 L0：系统名 20px/600 > 页面标题 18px > 面板标题 16px > 菜单 16px */
  font-size: 20px;
  font-weight: 600;
}
.app-nav {
  display: flex;
  gap: 16px;
}
/* 顶栏右侧用户区：margin-left:auto 把它推到最右（header 仍保持左侧标题+导航的既有布局） */
.app-user {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.user-name {
  font-size: 14px;
  color: var(--el-text-color-primary, #303133);
}
/* 分割线间距由 .app-user 的 gap:8px 统一控制，去掉 EP 默认的 0 8px 外边距防叠加过宽 */
.user-divider {
  margin: 0;
}
.nav-link {
  font-size: 16px;
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
