<script setup lang="ts">
// 登录页（第三阶段 M6）：用户名 + 密码 → POST /api/auth/login 存 token → 拉 /me 进系统。
// 校验用 Zod（loginSchema，与后端 LoginRequest 同口径）；失败展示后端 message
//（后端对"用户不存在/密码错/已停用"统一话术防枚举，前端照抄不编造）。
// 回车提交：el-form @submit.prevent + input type 原生行为，登录按钮 :loading 防重复点击（需求四.5）。
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { authErrorMessage, login } from '../composables/useAuth'
import { loginSchema } from '../schemas/auth'

const router = useRouter()
const route = useRoute()

const form = reactive({ username: '', password: '' })
const fieldErrors = reactive<Record<string, string>>({})
const formError = ref('')
const submitting = ref(false)

async function onSubmit() {
  formError.value = ''
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key]

  const result = loginSchema.safeParse(form)
  if (!result.success) {
    for (const issue of result.error.issues) {
      const key = String(issue.path[0] ?? 'form')
      if (!fieldErrors[key]) fieldErrors[key] = issue.message
    }
    return
  }

  submitting.value = true
  try {
    await login(form.username.trim(), form.password)
    // 登录成功回跳：优先 redirect 查询参数（401 善后写入），否则回列表页
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
  } catch (err) {
    formError.value = authErrorMessage(err)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="login-page">
    <el-card class="login-card">
      <h2 class="login-title">流水线故障记录系统</h2>
      <p class="login-subtitle">请使用管理员分配的账号登录</p>

      <el-alert v-if="formError" :title="formError" type="error" show-icon :closable="false" class="login-error" />

      <el-form label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名" :error="fieldErrors.username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            maxlength="50"
            autocomplete="username"
            clearable
          />
        </el-form-item>

        <el-form-item label="密码" :error="fieldErrors.password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码Demo@2026"
            maxlength="200"
            autocomplete="current-password"
            show-password
            @keyup.enter="onSubmit"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="submitting" class="login-button">
            登 录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </section>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  /* 登录页顶栏已整体隐藏（App.vue），高度链不再是 100vh-56px；
     父级 el-main 定高（flex:1），百分比高度有效，100% 即撑满可用区 */
  min-height: 100%;
}
.login-card {
  width: 380px;
  padding: 8px 12px;
}
.login-title {
  margin: 0 0 4px;
  /* 登录页无顶栏，卡片标题即系统名，按字阶 L0（20px/600）与顶栏同名对齐 */
  font-size: 20px;
  font-weight: 600;
  text-align: center;
}
.login-subtitle {
  margin: 0 0 20px;
  color: #909399;
  font-size: 13px;
  text-align: center;
}
.login-error {
  margin-bottom: 16px;
}
.login-button {
  width: 100%;
}
/* Chrome 自动填充补丁已升级为全局规则（styles/main.css），本页不再重复维护 */
</style>
