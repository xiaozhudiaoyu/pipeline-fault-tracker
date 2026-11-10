<script setup lang="ts">
// 用户管理页（第三阶段 M6，仅管理员，路由 meta.requiresAdmin 已拦非 admin）。
// 功能：账号列表 + 新建 / 启停 / 重置密码（对应 api/users.ts 四个端点，后端全部 AdminUser 把关）。
// 数据流：useUsers(isAdmin) 查询 ['users']，三个变更走 useUserMutations（成功自动失效重拉）。
// 业务镜像：后端禁止管理员停用自己（403），这里对当前登录账号直接禁用「停用」按钮；
// 重置密码会使对方 token 立即失效（D3 token_version），提示文案已含此口径。
import { computed, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'

import { useUserMutations, useUsers } from '../composables/useUsers'
import { currentUser, isAdmin } from '../composables/useAuth'
import { resetPasswordSchema, userCreateSchema } from '../schemas/auth'
import { FAULT_ROLE_META, FAULT_ROLE_OPTIONS } from '../types/user'
import type { FaultRole, User } from '../types/user'
import { formatDateTime } from '../utils/format'

const { data: users, isFetching, isError, error } = useUsers(isAdmin)

const mutations = useUserMutations()
// 任一变更提交中：按钮整体禁用防重复提交（同动作面板口径）
const busy = computed(() =>
  Object.values(mutations).some((m) => m.isLoading.value)
)

const rows = computed(() => users.value ?? [])

// 后端地址（错误提示里展示，同列表页话术）
const apiBase = import.meta.env.VITE_API_BASE_URL
const errorMessage = computed(() => {
  if (!isError.value || !error.value) return ''
  return `加载用户列表失败：${error.value.message}（请确认后端服务已在 ${apiBase} 启动）`
})

// ── 新建账号对话框 ────────────────────────────────────────────────────
const createVisible = ref(false)
const createForm = reactive<{ username: string; password: string; display_name: string; role: FaultRole }>({
  username: '',
  password: '',
  display_name: '',
  role: 'user',
})
const createErrors = reactive<Record<string, string>>({})

function clearCreateErrors() {
  for (const key of Object.keys(createErrors)) delete createErrors[key]
}

function openCreate() {
  createForm.username = ''
  createForm.password = ''
  createForm.display_name = ''
  createForm.role = 'user'
  clearCreateErrors()
  createVisible.value = true
}

function onCreateSubmit() {
  clearCreateErrors()
  const result = userCreateSchema.safeParse(createForm)
  if (!result.success) {
    for (const issue of result.error.issues) {
      const key = String(issue.path[0] ?? 'form')
      if (!createErrors[key]) createErrors[key] = issue.message
    }
    return
  }
  mutations.create.mutate(result.data, {
    onSuccess: () => {
      createVisible.value = false
    },
  })
}

// ── 启停：停用会立即踢掉对方登录态（D3），走二次确认；启用直接执行 ────────
async function onToggleActive(row: User) {
  if (row.is_active) {
    try {
      await ElMessageBox.confirm(
        `停用后 ${row.display_name} 将无法登录且当前登录立即失效，确定停用吗？`,
        '停用账号',
        { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' },
      )
    } catch {
      return // 用户取消
    }
  }
  mutations.toggleActive.mutate({ id: row.id, isActive: !row.is_active })
}

// 停用自己：后端 403（不允许），按钮直接禁用并提示
function isSelf(row: User): boolean {
  return currentUser.value?.id === row.id
}

// ── 重置密码对话框 ────────────────────────────────────────────────────
const resetTarget = ref<User | null>(null)
const resetVisible = computed({
  get: () => resetTarget.value !== null,
  set: (v) => {
    if (!v) resetTarget.value = null
  },
})
const resetValue = ref('')
const resetError = ref('')

function openReset(row: User) {
  resetTarget.value = row
  resetValue.value = ''
  resetError.value = ''
}

function onResetSubmit() {
  const target = resetTarget.value
  if (!target) return
  resetError.value = ''
  const result = resetPasswordSchema.safeParse(resetValue.value)
  if (!result.success) {
    resetError.value = result.error.issues[0]?.message ?? '请输入新密码'
    return
  }
  mutations.resetPassword.mutate(
    { id: target.id, password: result.data },
    { onSuccess: () => (resetTarget.value = null) },
  )
}
</script>

<template>
  <section class="user-manage">
    <header class="manage-header">
      <h2 class="manage-title">用户管理</h2>
      <el-button type="primary" :disabled="busy" @click="openCreate">新建账号</el-button>
    </header>

    <el-alert
      v-if="isError"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
      class="manage-block"
    />

    <!-- 表格区吃掉剩余高度（同列表页套路：定高容器 + el-table height=100%）：
         页头与错误提示常显，账号多时在表格内部滚动、表头固定 -->
    <div class="table-wrap">
    <el-table v-loading="isFetching" :data="rows" style="width: 100%" height="100%" empty-text="暂无账号" stripe border>
      <el-table-column prop="id" label="编号" width="70" />
      <el-table-column prop="username" label="登录名" min-width="130" show-overflow-tooltip />
      <el-table-column prop="display_name" label="展示名称" min-width="130" show-overflow-tooltip />
      <el-table-column label="角色" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="FAULT_ROLE_META[row.role as FaultRole]?.tag ?? 'info'" size="small" disable-transitions>
            {{ FAULT_ROLE_META[row.role as FaultRole]?.label ?? row.role }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small" disable-transitions>
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            size="small"
            :type="row.is_active ? 'danger' : 'success'"
            link
            :disabled="busy || (row.is_active && isSelf(row))"
            :title="row.is_active && isSelf(row) ? '不能停用当前登录的自己' : ''"
            @click="onToggleActive(row)"
          >
            {{ row.is_active ? '停用' : '启用' }}
          </el-button>
          <el-button size="small" type="primary" link :disabled="busy" @click="openReset(row)">
            重置密码
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <!-- 新建账号：字段约束镜像后端 UserCreate（userCreateSchema），重名 409 由 mutation 统一提示 -->
    <el-dialog v-model="createVisible" title="新建账号" width="480px" :close-on-click-modal="false">
      <el-form label-position="top" @submit.prevent>
        <!-- 关闭浏览器自动填充：el-input 默认 autocomplete=off 会被 Chrome 对密码框无视，须显式 new-password；
             否则管理员本机已保存的账号会被填进「登录名/初始密码」，污染新建表单甚至泄露自己的密码 -->
        <el-form-item label="登录名（3~50 字符，创建后不可改）" :error="createErrors.username">
          <el-input v-model="createForm.username" maxlength="50" placeholder="如 zhangsan" autocomplete="off" class="dialog-control" />
        </el-form-item>
        <el-form-item label="初始密码（至少 6 位，请线下告知本人）" :error="createErrors.password">
          <el-input v-model="createForm.password" type="password" maxlength="200" show-password autocomplete="new-password" class="dialog-control" />
        </el-form-item>
        <el-form-item label="展示名称" :error="createErrors.display_name">
          <el-input v-model="createForm.display_name" maxlength="100" placeholder="如 张三" class="dialog-control" />
        </el-form-item>
        <el-form-item label="角色" :error="createErrors.role">
          <!-- 本机 element-plus 2.5.6 的 el-radio 只有 label prop（value prop 自 2.6 才引入，已核源码） -->
          <el-radio-group v-model="createForm.role">
            <el-radio v-for="opt in FAULT_ROLE_OPTIONS" :key="opt.value" :label="opt.value">
              {{ opt.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="mutations.create.isLoading.value" @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="mutations.create.isLoading.value" @click="onCreateSubmit">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 重置密码：只填新密码；成功后对方 token 立即失效（D3），需重新登录 -->
    <el-dialog v-model="resetVisible" :title="`重置密码：${resetTarget?.display_name ?? ''}`" width="420px" :close-on-click-modal="false">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="新密码（至少 6 位）" :error="resetError">
          <el-input v-model="resetValue" type="password" maxlength="200" show-password class="dialog-control" />
        </el-form-item>
      </el-form>
      <p class="reset-hint">重置后该账号当前登录将立即失效，需用新密码重新登录。</p>
      <template #footer>
        <el-button :disabled="mutations.resetPassword.isLoading.value" @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="mutations.resetPassword.isLoading.value" @click="onResetSubmit">
          确定重置
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.user-manage {
  padding: 24px;
  background: #fff;
  border-radius: 8px;
  /* 撑满顶栏以下可用区（同故障列表页）：页头常显，表格吃掉剩余高度 */
  height: 100%;
  display: flex;
  flex-direction: column;
}
.manage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.manage-title {
  margin: 0;
  /* 全局字阶 L1：页面标题 18px/600 */
  font-size: 18px;
  font-weight: 600;
}
.manage-block {
  margin-bottom: 16px;
}
.table-wrap {
  flex: 1;
  /* flex 子项内部滚动必备：允许收缩到内容高度以下 */
  min-height: 0;
}
.dialog-control {
  width: 100%;
}
.reset-hint {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary, #909399);
}
</style>
