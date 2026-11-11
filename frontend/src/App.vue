<script setup lang="ts">
// 根组件：固定「顶部标题 + 导航栏」，主区用 <RouterView> 渲染当前路由对应的页面。
// RouterLink / RouterView 由 app.use(router) 全局注册，模板中直接使用、无需 import。
// 第三阶段 M6：登录页整条顶栏不渲染（未登录无导航/用户信息可展示）；登录后顶栏右侧
// 展示当前用户（姓名 + 角色）与登出，
// 「用户管理」入口仅管理员可见（体验层隐藏，真拦截在后端 /api/users 的 AdminUser 依赖）。
import { computed } from 'vue'
import { useRoute } from 'vue-router'
// 仅为面板宽度跟随触发器提供 Popper 类型（type-only 导入，编译期擦除，不新增运行时依赖）
import type { Options } from '@popperjs/core'

import { currentUser, isAdmin, logout } from './composables/useAuth'
// 角色展示暂隐藏（见模板 line 下拉项），FAULT_ROLE_META 随 roleLabel 一并注释，恢复时取消注释即可
// import { FAULT_ROLE_META } from './types/user'

const route = useRoute()
const isLoginPage = computed(() => route.name === 'login')

// 下拉面板宽度跟随触发器（头像 + 姓名那一行）：自定义 Popper modifier 读取 reference
// （即 el-dropdown 默认插槽的触发元素）宽度，写为面板 min-width；modifier 按 name 合并，不覆盖 EP 内置项。
const dropdownPopperOptions: Partial<Options> = {
  modifiers: [
    {
      name: 'matchTriggerWidth',
      enabled: true,
      phase: 'beforeWrite',
      requires: ['computeStyles'],
      fn: ({ state }) => {
        state.styles.popper.minWidth = `${state.rects.reference.width}px`
      },
    },
  ],
}

// 角色文案：未知角色兜底显示原始值（防后端加新角色时前端白屏）
// 暂隐藏（角色下拉项被注释），noUnusedLocals 不允许未使用，恢复时取消注释即可
// const roleLabel = computed(() => (currentUser.value ? FAULT_ROLE_META[currentUser.value.role]?.label ?? currentUser.value.role : ''))
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

      <!-- 顶栏右侧：用户头像 + 退出下拉（仅登录后展示） -->
      <div v-if="!isLoginPage && currentUser" class="app-user">
        <el-dropdown
          trigger="click"
          :popper-options="dropdownPopperOptions"
          @command="(cmd: string) => cmd === 'logout' && logout()"
        >
          <div class="user-trigger">
            <el-avatar :size="30">{{ currentUser.display_name.charAt(0) }}</el-avatar>
            <span class="user-name">{{ currentUser.display_name }}</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <!-- <el-dropdown-item disabled>{{ roleLabel }}</el-dropdown-item> -->
              <el-dropdown-item command="logout">退出</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>
    <el-main class="app-main scrollbar-hover-show">
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
.user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
}
.user-name {
  color: var(--el-text-color-primary, #303133);
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
