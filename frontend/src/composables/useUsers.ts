// 用户管理相关查询与变更（TanStack Query v4，第三阶段 M6，全部仅管理员页面使用）。
// 缓存口径：['users'] 单键全量（用户量小，不分页）；指派/改派下拉与筛选栏共用该查询，
// 变更后统一失效重拉。queryFn 依赖登录态 token（client.ts 注入），403 由后端兜底。
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { ElMessage } from 'element-plus'
import type { Ref } from 'vue'

import { createUser, fetchUsers, resetUserPassword, setUserActive } from '../api/users'
import { toUserMessage } from './useFaultMutations'
import type { User, UserCreatePayload } from '../types/user'

// enabled 由调用方控制：/api/users 仅管理员可访问（后端 AdminUser），
// 非管理员页面必须传 false 阻止发起 403 请求（如筛选栏/指派下拉按 isAdmin 门控）。
export function useUsers(enabled: Ref<boolean>) {
  return useQuery<User[], Error>({
    queryKey: ['users'],
    queryFn: ({ signal }) => fetchUsers(signal),
    enabled,
  })
}

// 用户管理页的三个变更：新建 / 启停 / 重置密码。成功后失效 ['users'] 重拉。
export function useUserMutations() {
  const queryClient = useQueryClient()

  // 各 mutation 共用成功回调工厂：刷新列表 + 成功提示
  function onUserChanged(successText: string) {
    queryClient.invalidateQueries({ queryKey: ['users'] })
    ElMessage.success(successText)
  }

  const create = useMutation<User, Error, UserCreatePayload>({
    mutationFn: (payload) => createUser(payload),
    onSuccess: () => onUserChanged('账号创建成功'),
    onError: (err) => ElMessage.error(toUserMessage(err)),
  })

  const toggleActive = useMutation<User, Error, { id: number; isActive: boolean }>({
    mutationFn: ({ id, isActive }) => setUserActive(id, isActive),
    onSuccess: (user) => onUserChanged(user.is_active ? '账号已启用' : '账号已停用'),
    onError: (err) => ElMessage.error(toUserMessage(err)),
  })

  const resetPassword = useMutation<User, Error, { id: number; password: string }>({
    mutationFn: ({ id, password }) => resetUserPassword(id, password),
    onSuccess: () => onUserChanged('密码已重置，该用户需重新登录'),
    onError: (err) => ElMessage.error(toUserMessage(err)),
  })

  return { create, toggleActive, resetPassword }
}
