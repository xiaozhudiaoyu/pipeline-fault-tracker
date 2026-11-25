# TanStack Vue Query v4 完整使用文档

> 适用版本：`@tanstack/vue-query@4.36.2`（底层 `@tanstack/query-core@4.36.1`），即本项目 `frontend/package.json` 锁定的 `~4.36.0`。
> 本文所有 API 名称、选项、返回值字段均已对照 `node_modules/@tanstack/vue-query/build/lib/*.d.ts` 与 `@tanstack/query-core` 类型定义核实；项目实例均取自本仓库真实代码。
> v4 → v5 的差异见文末[第十二章](#十二v4--v5-迁移要点附录)。**本项目因 Node 16 锁定 v4，请勿直接套用 v5 写法。**

---

## 目录

1. [核心概念](#一核心概念)
2. [安装与配置](#二安装与配置)
3. [useQuery —— 数据查询](#三usequery--数据查询)
4. [useMutation —— 数据变更](#四usemutation--数据变更)
5. [QueryClient —— 缓存操作](#五queryclient--缓存操作)
6. [useQueries —— 并行多查询](#六usequeries--并行多查询)
7. [useInfiniteQuery —— 无限加载](#七useinfinitequery--无限加载)
8. [useIsFetching / useIsMutating —— 全局加载态](#八useisfetching--useismutating--全局加载态)
9. [响应式与解包机制（vue-query 特有）](#九响应式与解包机制vue-query-特有)
10. [本项目实战范式](#十本项目实战范式)
11. [常见坑与最佳实践](#十一常见坑与最佳实践)
12. [v4 → v5 迁移要点（附录）](#十二v4--v5-迁移要点附录)

---

## 一、核心概念

### 1.1 它解决什么问题

传统写法里，"从后端拿数据"这件事的状态（加载中 / 成功 / 失败 / 数据本身 / 是否需要重新拉）散落在每个组件的 `ref` 里，手动管理 `loading`、`try/catch`、缓存、去重、翻页刷新，重复且易错。

Vue Query 把**服务端状态（server state）**从组件里抽出来，交给一个全局缓存统一管理。组件只声明"我需要哪个 key 的数据"，库负责：请求、缓存、去重、失效、重新拉取、后台刷新、错误重试。

> 关键区分：
> - **客户端状态**：表单输入、主题、侧边栏开合 —— 用 `ref` / `reactive` / Pinia。
> - **服务端状态**：故障列表、流水线、详情 —— 用 Vue Query。它本质是"远端数据的本地缓存副本"。

### 1.2 五个核心对象

| 概念 | 说明 |
|---|---|
| **QueryClient** | 全局单例，持有缓存、负责调度所有查询与变更。通过 `VueQueryPlugin` 注入，用 `useQueryClient()` 获取。 |
| **QueryCache** | 缓存容器，里面是一条条 Query。一般不直接操作，通过 QueryClient 的方法间接访问。 |
| **queryKey** | 查询的唯一标识，一个数组（如 `['faults', params]`）。**key 相同 = 同一份缓存**，key 变化 = 触发重新请求。 |
| **Query（useQuery）** | 一次"读"操作。声明 key + queryFn，库负责缓存与同步。 |
| **Mutation（useMutation）** | 一次"写"操作（POST/PATCH/DELETE）。不缓存结果，成功后通常用来失效相关 Query。 |

### 1.3 数据的两种"时间"

这是理解 Vue Query 行为的关键：

- **`staleTime`（保鲜期）**：数据在多久内算"新鲜"。新鲜期内，组件重新挂载 / 窗口重新聚焦**不会**重新请求，直接用缓存。默认 `0`（立即变陈旧）。
- **`cacheTime`（缓存期）**：数据在**没有任何组件订阅**后，还在内存里保留多久，超时后被垃圾回收。默认 `5 * 60 * 1000`（5 分钟）。

一句话：`staleTime` 管"要不要重新拉"，`cacheTime` 管"多久后扔掉"。

### 1.4 状态机

Query 的 `status` 只有三种：`'loading' | 'error' | 'success'`；另有 `fetchStatus`：`'fetching' | 'paused' | 'idle'` 描述"是否正在发请求"。二者组合出常见派生布尔值（见 [3.4 返回值](#34-返回值)）。

---

## 二、安装与配置

### 2.1 安装

本项目已安装（见 [package.json](file:///e:/python项目/pipeline-fault-tracker/frontend/package.json)）：

```jsonc
"dependencies": {
  "@tanstack/vue-query": "~4.36.0"
}
```

若在新项目安装（需 Node ≥ 16；v5 需 Node ≥ 18）：

```powershell
npm install @tanstack/vue-query@~4.36.0
```

### 2.2 注册插件

必须在应用入口注册 `VueQueryPlugin`，本项目见 [main.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/main.ts)：

```ts
import { createApp } from 'vue'
import { VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'

const app = createApp(App)
app.use(VueQueryPlugin)   // 注册后即可在任意组件用 useQuery / useMutation / useQueryClient
app.mount('#app')
```

> 注册顺序无强制要求，本项目约定"先 UI 库、再路由、再数据层"，便于阅读。

### 2.3 插件配置项（VueQueryPluginOptions）

`app.use(VueQueryPlugin, options)` 的 `options` 有两种互斥形态（出处：`vueQueryPlugin.d.ts`）：

**形态 A —— 传配置，让插件内部建 client：**

```ts
app.use(VueQueryPlugin, {
  queryClientConfig: {
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,        // 全局默认保鲜 1 分钟
        retry: 1,                    // 失败重试 1 次
        refetchOnWindowFocus: false, // 关闭"聚焦窗口自动刷新"
      },
    },
  },
})
```

**形态 B —— 传一个自己 new 好的 client：**

```ts
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30 * 1000 } },
})
app.use(VueQueryPlugin, { queryClient })
```

完整字段（`CommonOptions`）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `queryClient` | `QueryClient` | 直接传入自定义实例（与 `queryClientConfig` 二选一）。 |
| `queryClientConfig` | `QueryClientConfig` | 由插件内部据此 new 一个 client。 |
| `queryClientKey` | `string` | 多 client 隔离时的标识，配合 `useQueryClient(key)`。 |
| `contextSharing` | `boolean` | 是否把 client 挂到 `window.__VUE_QUERY_CONTEXT__` 跨微前端共享，默认 `false`。 |
| `clientPersister` | `(client) => [unsubscribe, Promise]` | 持久化 client（如存 localStorage）以便刷新页面恢复缓存。 |
| `clientPersisterOnSuccess` | `(client) => void` | 持久化成功回调。 |

> 本项目采用最简形态 `app.use(VueQueryPlugin)`，不传 options，全部走默认值；单个查询的差异化配置（如 `staleTime`）写在各自 composable 里。

### 2.4 全局默认选项

`defaultOptions.queries` 里设的选项会作为**所有** `useQuery` 的默认值，单个查询仍可覆盖。常用：

```ts
defaultOptions: {
  queries: {
    staleTime: 60_000,
    cacheTime: 5 * 60_000,
    retry: 1,
    refetchOnWindowFocus: false,
    refetchOnReconnect: true,
  },
  mutations: {
    // useMutation 的默认项
  },
}
```

---

## 三、useQuery —— 数据查询

### 3.1 三种调用签名

`useQuery` 有多个重载（出处：`useQuery.d.ts`），常见三种：

```ts
// ① 单对象（本项目统一用这种，最清晰）
useQuery({ queryKey, queryFn, ...options })

// ② key + options
useQuery(queryKey, { queryFn, ...options })

// ③ key + queryFn + options
useQuery(queryKey, queryFn, { ...options })
```

### 3.2 泛型

```ts
useQuery<TQueryFnData, TError, TData, TQueryKey>(...)
```

| 泛型 | 含义 | 默认 |
|---|---|---|
| `TQueryFnData` | `queryFn` 返回的原始数据类型 | `unknown` |
| `TError` | 错误类型 | `unknown` |
| `TData` | 经 `select` 转换后暴露给组件的数据类型 | `= TQueryFnData` |
| `TQueryKey` | queryKey 类型 | `QueryKey` |

> **务必显式声明 `TError`**。v4 默认 `TError = unknown`，不写的话 `error.value` 收窄后是 `{}`，取不到 `.message`。本项目 [useFaultList.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/composables/useFaultList.ts) 就显式写了 `useQuery<FaultList, Error>`。

### 3.3 queryKey 与响应式

queryKey 是一个数组，**可以放入 `ref` / `computed` / `reactive`**，vue-query 内部用 `cloneDeepUnref` 解包并追踪其值。值变化 → key 变化 → 自动重新请求。

本项目 [useFaultList.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/composables/useFaultList.ts) 是典型范例：

```ts
export function useFaultList(params: ComputedRef<FaultListParams>) {
  return useQuery<FaultList, Error>({
    // params 是 computed ref，解包后作为 key 的一部分；筛选/翻页变化即自动 refetch
    queryKey: ['faults', params],
    queryFn: ({ signal }) => fetchFaults(params.value, signal),
    keepPreviousData: true,
  })
}
```

> key 设计约定：**从粗到细**，把"会影响结果的参数"都放进 key。`['faults', params]` 表示"故障列表，且区分不同筛选/分页"；`['fault', id]` 表示"某一条故障详情"。这样失效时可用前缀 `['faults']` 一次性命中所有列表页。

### 3.4 queryFn 与 signal

`queryFn` 接收一个 `QueryFunctionContext`，常用字段：

```ts
queryFn: ({ queryKey, signal, pageParam, meta }) => { ... }
```

- `signal`：`AbortSignal`。**务必透传给 fetch/axios**，这样组件卸载或 key 变化时能取消进行中的请求，避免竞态与内存泄漏。
- `queryKey`：当前（已解包的）key，可从中取参数。
- `pageParam`：仅 `useInfiniteQuery` 用。

本项目 [api/faults.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/api/faults.ts) 的 fetch 封装就接收 `signal`：

```ts
queryFn: ({ signal }) => fetchFaults(params.value, signal)
```

### 3.5 返回值

`useQuery` 返回一个对象，**每个数据字段都是 `Ref`**（内部 `toRefs(readonly(state))` 实现），在 `<script>` 里要 `.value`，在 `<template>` 里自动解包。函数（`refetch` / `remove`）保持普通函数。完整字段（出处：`query-core` 的 `QueryObserverBaseResult`）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `data` | `Ref<TData \| undefined>` | 成功后的数据；未成功为 `undefined`。 |
| `error` | `Ref<TError \| null>` | 错误对象；无错误为 `null`。 |
| `status` | `Ref<'loading'\|'error'\|'success'>` | 主状态。 |
| `fetchStatus` | `Ref<'fetching'\|'paused'\|'idle'>` | 请求进行中状态。 |
| `isLoading` | `Ref<boolean>` | 首次加载且无数据（`status==='loading'`）。 |
| `isSuccess` | `Ref<boolean>` | `status==='success'`。 |
| `isError` | `Ref<boolean>` | `status==='error'`。 |
| `isFetching` | `Ref<boolean>` | **正在发请求**（含后台刷新），不管有没有旧数据。 |
| `isInitialLoading` | `Ref<boolean>` | 首次加载且正在请求（`isLoading && isFetching`）。 |
| `isPreviousData` | `Ref<boolean>` | 当前 `data` 是上一个 key 的旧数据（`keepPreviousData` 生效中）。 |
| `isPlaceholderData` | `Ref<boolean>` | 当前 `data` 是 `placeholderData`。 |
| `isStale` | `Ref<boolean>` | 数据已陈旧。 |
| `dataUpdatedAt` / `errorUpdatedAt` | `Ref<number>` | 数据/错误更新时间戳。 |
| `failureCount` / `failureReason` | `Ref` | 重试次数 / 最近失败原因。 |
| `refetch(options?)` | `Function` | 手动重新请求，返回 Promise。 |
| `remove()` | `Function` | 从缓存移除该查询。 |
| `suspense()` | `Function` | 配合 `<Suspense>` 使用，返回 Promise。 |

> `isLoading` vs `isFetching` 区别：`isLoading` 只在"还没有任何数据"时为 true；后台静默刷新时 `isLoading=false` 但 `isFetching=true`。本项目列表页用 `isFetching` 驱动表格 loading（[FaultListView.vue](file:///e:/python项目/pipeline-fault-tracker/frontend/src/views/FaultListView.vue)），这样翻页时旧数据仍在、只是蒙一层 loading，不闪空。

### 3.6 常用选项

完整选项出处：`query-core` 的 `QueryObserverOptions`。下表为高频项：

| 选项 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `queryKey` | `QueryKey` | — | **必填**，查询标识。 |
| `queryFn` | `(ctx) => Promise<T>` | — | **必填**，请求函数。 |
| `enabled` | `boolean \| Ref<boolean>` | `true` | 为 `false` 时不发请求（守卫非法参数 / 条件查询）。 |
| `staleTime` | `number` | `0` | 保鲜期（ms），期内不重新拉。`Infinity` 永不过期。 |
| `cacheTime` | `number` | `5*60*1000` | 无订阅者后缓存保留时长。 |
| `keepPreviousData` | `boolean` | `false` | key 变化时保留上一页数据，避免闪空（**v4 名称，v5 改为 `placeholderData: keepPreviousData`**）。 |
| `placeholderData` | `TData \| () => TData` | — | 加载期占位数据（与 `keepPreviousData` 不同，这是静态占位）。 |
| `initialData` | `TData \| () => TData` | — | 初始数据；提供后 `data` 类型不再含 `undefined`（返回 `UseQueryDefinedReturnType`）。 |
| `refetchOnWindowFocus` | `boolean \| 'always'` | `true` | 窗口聚焦时若数据陈旧则刷新。 |
| `refetchOnReconnect` | `boolean \| 'always'` | `true` | 网络重连时刷新。 |
| `refetchOnMount` | `boolean \| 'always'` | `true` | 组件挂载时若陈旧则刷新。 |
| `refetchInterval` | `number \| false \| fn` | `false` | 轮询间隔（ms）。 |
| `refetchIntervalInBackground` | `boolean` | `false` | 后台标签页是否继续轮询。 |
| `retry` | `boolean \| number \| fn` | `3` | 失败重试次数/策略。 |
| `retryDelay` | `number \| fn` | 指数退避 | 重试间隔。 |
| `select` | `(data) => TData` | — | 转换/裁剪数据，仅当转换结果变化才触发重渲染。 |
| `notifyOnChangeProps` | `string[] \| 'all' \| fn` | 自动追踪 | 限制只有指定字段变化才重渲染（性能优化）。 |
| `suspense` | `boolean` | `false` | 配合 `<Suspense>`，加载时挂起。 |
| `useErrorBoundary` | `boolean \| fn` | `false` | 错误时抛出到错误边界而非返回 `error`。 |
| `meta` | `object` | — | 附加元信息，可在全局回调里读取。 |
| `onSuccess/onError/onSettled` | `fn` | — | **v4 已标记 `@deprecated`**，建议改在 `watch` 或调用处处理，v5 已移除。 |

### 3.7 enabled —— 条件查询守卫

`enabled` 为 `false` 时查询不会发出。本项目 [useFaultDetail.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/composables/useFaultDetail.ts) 用它拦下非法路由参数：

```ts
export function useFaultDetail(id: Ref<number>) {
  // 合法正整数 ID 才启用查询（NaN / 0 / 负数一律不发请求）
  const enabled = computed(() => Number.isFinite(id.value) && id.value > 0)
  return useQuery<Fault, Error>({
    queryKey: ['fault', id],
    queryFn: ({ signal }) => fetchFault(id.value, signal),
    enabled,
  })
}
```

> 这样 `/faults/abc`（`Number('abc')` = NaN）不会打出 `GET /api/faults/NaN` 被后端 422。`enabled` 可以是 `computed`，其值变化时查询会自动启停。

### 3.8 staleTime —— 主数据缓存

变化极少的主数据可设较长 `staleTime`，减少无谓往返。本项目 [usePipelines.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/composables/usePipelines.ts)：

```ts
export function usePipelines() {
  return useQuery({
    queryKey: ['pipelines'],
    queryFn: ({ signal }) => fetchPipelines(signal),
    staleTime: 5 * 60 * 1000, // 流水线 5 分钟内不重新请求
  })
}
```

> 该 composable 被"列表页筛选下拉"和"登记页流水线下拉"复用。因为 key 都是 `['pipelines']` 且 `staleTime` 内数据新鲜，两个页面共享同一份缓存，只发一次请求。

### 3.9 keepPreviousData —— 翻页不闪空

见 [3.3](#33-querykey-与响应式) 的 `useFaultList`。开启后，切换筛选/翻页时 `data` 暂时保留上一页内容，`isPreviousData` 为 `true`，表格不会先变空再填充。

---

## 四、useMutation —— 数据变更

### 4.1 调用签名与泛型

```ts
useMutation<TData, TError, TVariables, TContext>(options)
```

| 泛型 | 含义 | 默认 |
|---|---|---|
| `TData` | 接口返回数据类型 | `unknown` |
| `TError` | 错误类型 | `unknown` |
| `TVariables` | `mutate(variables)` 入参类型 | `void` |
| `TContext` | `onMutate` 返回、传给 `onSuccess/onError` 的上下文类型 | `unknown` |

### 4.2 返回值

`useMutation` 返回对象，状态字段是 `Ref`，方法是普通函数（出处：`useMutation.d.ts`）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `mutate(variables, options?)` | `Function` | 触发变更，**不返回 Promise、不抛错**（错误进 `onError`/`error`）。 |
| `mutateAsync(variables, options?)` | `Function` | 触发变更，**返回 Promise**，失败会 reject（需自己 catch）。 |
| `reset()` | `Function` | 把 mutation 状态重置回 `idle`。 |
| `data` | `Ref<TData \| undefined>` | 成功返回的数据。 |
| `error` | `Ref<TError \| null>` | 错误。 |
| `status` | `Ref<'idle'\|'loading'\|'success'\|'error'>` | 状态。 |
| `isLoading` | `Ref<boolean>` | 变更进行中（**v5 改名 `isPending`**）。 |
| `isSuccess` / `isError` / `isIdle` | `Ref<boolean>` | 派生状态。 |
| `variables` | `Ref<TVariables \| undefined>` | 本次变更入参。 |

> `mutate` vs `mutateAsync`：表单提交、按钮点击等"触发后不需要 await 结果"的场景用 `mutate`（错误统一在 `onError` 处理，不会因未 catch 而报 unhandled rejection）；需要在流程里 `await` 结果（如成功后拿返回值继续做事）用 `mutateAsync` 并配 `try/catch`。

### 4.3 生命周期回调

```ts
useMutation({
  mutationFn,
  onMutate: async (variables) => {
    // 请求发出前。可返回一个 context，传给 onSuccess/onError/onSettled（乐观更新用）
    return { snapshot }
  },
  onSuccess: (data, variables, context) => { /* 成功 */ },
  onError: (error, variables, context) => { /* 失败，可用 context 回滚 */ },
  onSettled: (data, error, variables, context) => { /* 无论成败都执行 */ },
})
```

回调有**两个层级**，都会执行（hook 级先、调用级后）：

- **hook 级**：写在 `useMutation({ onSuccess })` 里，适合放"通用副作用"（失效缓存、全局 toast）。
- **调用级**：写在 `mutate(vars, { onSuccess })` 里，适合放"本次调用特有"的逻辑（如成功后跳转）。

本项目 [FaultCreateView.vue](file:///e:/python项目/pipeline-fault-tracker/frontend/src/views/FaultCreateView.vue) 就用了调用级回调做跳转：

```ts
create.mutate(payload, {
  onSuccess: (fault) => {
    // 通用反馈（toast + 列表失效）已在 useFaultMutations 的 hook 级回调处理
    router.push({ name: 'fault-detail', params: { id: String(fault.id) } })
  },
})
```

### 4.4 项目实例：useFaultMutations

本项目把所有变更集中在 [useFaultMutations.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/composables/useFaultMutations.ts)，统一处理"调接口 + 刷缓存 + 全局反馈"：

```ts
export function useFaultMutations() {
  const queryClient = useQueryClient()

  // 登记：成功后让列表失效（新记录应出现在列表靠前位置）
  const create = useMutation<Fault, Error, FaultCreatePayload>({
    mutationFn: (payload) => createFault(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['faults'] })
      ElMessage.success('故障登记成功')
    },
    onError: (err) => {
      ElMessage.error(toUserMessage(err))
    },
  })

  // 状态流转：成功后把最新故障写回详情缓存 + 让列表失效
  const transition = useMutation<Fault, Error, TransitionVariables>({
    mutationFn: ({ id, payload }) => transitionFault(id, payload),
    onSuccess: (fault) => {
      queryClient.setQueryData(['fault', fault.id], fault)   // 直接写回，免一次请求
      queryClient.invalidateQueries({ queryKey: ['faults'] }) // 列表状态列可能变化
      ElMessage.success('状态已更新')
    },
    onError: (err) => {
      ElMessage.error(toUserMessage(err))
    },
  })

  return { create, transition }
}
```

要点：
- `transition` 的入参是 `{ id, payload }` 对象 —— 因为 `mutate` 只能接收**单一** `variables`，多值需包成一个对象（见 `TransitionVariables` 接口）。
- 成功后两种刷缓存策略：**`invalidateQueries`**（标记失效、触发重新拉，适合列表）与 **`setQueryData`**（直接写回已知数据、免请求，适合详情）。

### 4.5 乐观更新（Optimistic Update）

先假设成功、立即改 UI，失败再回滚。范式（v4 通用写法）：

```ts
useMutation({
  mutationFn: updateTodo,
  onMutate: async (newTodo) => {
    await queryClient.cancelQueries({ queryKey: ['todos'] })     // 取消进行中的请求
    const previous = queryClient.getQueryData(['todos'])          // 快照，用于回滚
    queryClient.setQueryData(['todos'], (old) => optimisticMerge(old, newTodo)) // 乐观写
    return { previous }                                           // 返回 context
  },
  onError: (_err, _vars, context) => {
    queryClient.setQueryData(['todos'], context.previous)         // 回滚
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['todos'] })        // 最终以服务端为准
  },
})
```

> 本项目未用乐观更新（变更成功后直接 `invalidateQueries` / `setQueryData` 即可满足），此处作为范式参考。

---

## 五、QueryClient —— 缓存操作

### 5.1 获取实例

```ts
import { useQueryClient } from '@tanstack/vue-query'
const queryClient = useQueryClient()        // 默认 client
const other = useQueryClient('my-key')      // 多 client 时按 key 取
```

### 5.2 失效查询 invalidateQueries

标记缓存为陈旧，并（默认）触发所有订阅该 key 的活跃查询重新请求。这是 mutation 成功后最常用的刷新手段。

```ts
// 前缀匹配：所有以 ['faults'] 开头的 key 都失效（含 ['faults', {page:1}]、['faults', {page:2}]…）
queryClient.invalidateQueries({ queryKey: ['faults'] })

// 精确匹配：只失效这一个 key
queryClient.invalidateQueries({ queryKey: ['fault', 1], exact: true })

// 只失效不重新拉（refetchType: 'none'）
queryClient.invalidateQueries({ queryKey: ['faults'] }, { refetchType: 'none' })

// 用谓词自定义
queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'faults' })
```

`InvalidateQueryFilters` 常用字段：`queryKey`、`exact`、`predicate`、`active`（仅活跃查询）、`inactive`、`refetchType`（`'active' | 'inactive' | 'all' | 'none'`）。

### 5.3 读写缓存 setQueryData / getQueryData

```ts
// 读
const fault = queryClient.getQueryData<Fault>(['fault', id])

// 写（直接给值）
queryClient.setQueryData(['fault', fault.id], fault)

// 写（函数式更新，拿旧值算新值）
queryClient.setQueryData<FaultList>(['faults', params], (old) =>
  old ? { ...old, total: old.total + 1 } : old
)
```

> `setQueryData` 会**立即**更新缓存并触发订阅组件重渲染，不发请求。适合"mutation 已返回最新数据，直接写回"的场景（见 [4.4](#44-项目实例usefaultmutations) 的 transition）。

### 5.4 其他缓存方法

| 方法 | 用途 |
|---|---|
| `refetchQueries(filters?)` | 重新请求（不管是否陈旧）。 |
| `resetQueries(filters?)` | 重置到初始状态（清空 data，回到 loading），再按 enabled 重新拉。 |
| `removeQueries(filters?)` | 直接从缓存移除（不等 cacheTime）。 |
| `cancelQueries(filters?)` | 取消进行中的请求（乐观更新前常用）。 |
| `fetchQuery(options)` | 命令式拉一次并返回数据（有缓存且新鲜则直接返回缓存）。 |
| `ensureQueryData(options)` | 同 `fetchQuery`，但**仅在无缓存时**才请求（v4.36 提供）。 |
| `prefetchQuery(options)` | 预取（不返回数据，只填缓存），常用于路由切换前预热。 |
| `getQueryState(key)` | 拿查询的完整内部状态（含 dataUpdatedAt 等）。 |
| `setDefaultOptions` / `getQueryDefaults` / `setQueryDefaults` | 运行时改默认项 / 按 key 设默认项。 |
| `clear()` | 清空整个缓存。 |

### 5.5 命令式取数（组件外 / 路由守卫）

```ts
// 在路由守卫里预取详情页数据
router.beforeEach(async (to) => {
  if (to.name === 'fault-detail') {
    const id = Number(to.params.id)
    await queryClient.prefetchQuery({
      queryKey: ['fault', id],
      queryFn: ({ signal }) => fetchFault(id, signal),
    })
  }
})
```

> `fetchQuery` / `prefetchQuery` / `ensureQueryData` 都返回 Promise，可在 `setup` 之外使用（只要拿得到 `queryClient` 实例）。

---

## 六、useQueries —— 并行多查询

需要"同时发多个独立查询"时用 `useQueries`（如一个页面要同时拉 N 个不同 id 的详情）。

```ts
import { useQueries } from '@tanstack/vue-query'

const ids = ref([1, 2, 3])
const results = useQueries({
  queries: computed(() =>
    ids.value.map((id) => ({
      queryKey: ['fault', id],
      queryFn: ({ signal }: { signal?: AbortSignal }) => fetchFault(id, signal),
      staleTime: 60_000,
    }))
  ),
})
```

> **返回值形态与 `useQuery` 不同**：`useQueries` 返回的是 `readonly(reactive([...]))`，即一个**只读响应式数组**，每个元素是 `QueryObserverResult` 普通对象（**不是 Ref**）。所以访问写 `results[0].data` 而**不是** `results[0].data.value`（出处：`useQueries.mjs` 的 `readonly(state)`）。
>
> `queries` 可以是 `computed`，其值变化（如 ids 增减）时会自动增删对应查询。

---

## 七、useInfiniteQuery —— 无限加载

用于"加载更多 / 无限滚动 / 游标分页"。与普通 `useQuery` 的区别：数据是 `InfiniteData<T>` 结构（`{ pages: T[], pageParams: unknown[] }`），并提供 `fetchNextPage` / `fetchPreviousPage`。

```ts
import { useInfiniteQuery } from '@tanstack/vue-query'

const {
  data,            // Ref<InfiniteData<FaultList> | undefined>，data.value.pages 是各页数组
  fetchNextPage,   // () => Promise，加载下一页
  hasNextPage,     // Ref<boolean>，是否还有下一页
  isFetchingNextPage,
} = useInfiniteQuery<FaultList, Error>({
  queryKey: ['faults-infinite'],
  queryFn: ({ signal, pageParam = 1 }) => fetchFaults({ page: pageParam, size: 20 }, signal),
  getNextPageParam: (lastPage, allPages) => {
    // 根据最后一页返回下一页游标；返回 undefined 表示没有更多
    const loaded = allPages.reduce((n, p) => n + p.items.length, 0)
    return loaded < lastPage.total ? lastPage.page + 1 : undefined
  },
})
```

关键选项（出处：`QueryOptions`）：

| 选项 | 说明 |
|---|---|
| `getNextPageParam(lastPage, allPages)` | **必填**（要支持下一页时）。返回下一页游标，返回 `undefined`/`null` 表示到底。 |
| `getPreviousPageParam(firstPage, allPages)` | 支持向上加载时填，逻辑同上。 |

返回值额外字段：`fetchNextPage` / `fetchPreviousPage`（函数）、`hasNextPage` / `hasPreviousPage` / `isFetchingNextPage` / `isFetchingPreviousPage`（Ref）。`queryFn` 的 `ctx.pageParam` 即上一次算出的游标。

> 本项目列表用的是后端 `page/size` 传统分页（`el-pagination` 控页码），未用无限加载；此章作为需要"滚动加载更多"时的范式参考。

---

## 八、useIsFetching / useIsMutating —— 全局加载态

不绑定单个查询，而是统计"当前有多少查询/变更正在进行"，常用于顶部全局进度条。

```ts
import { useIsFetching, useIsMutating } from '@tanstack/vue-query'

const fetchingCount = useIsFetching()               // Ref<number>，全局进行中的查询数
const fetchingFaults = useIsFetching({ queryKey: ['faults'] }) // 只统计 faults 前缀
const mutatingCount = useIsMutating()               // Ref<number>，全局进行中的变更数
```

模板里：

```vue
<el-progress v-if="fetchingCount" :percentage="100" :indeterminate="true" />
```

两者都返回 `Ref<number>`，可传 `QueryFilters` / `MutationFilters` 缩小统计范围（出处：`useIsFetching.d.ts` / `useIsMutating.d.ts`）。

---

## 九、响应式与解包机制（vue-query 特有）

这是 vue-query 与 react-query 最大的差异，也是最容易踩坑的地方。

### 9.1 入参：MaybeRef + 深度解包

`useQuery` / `useMutation` 的几乎所有选项都接受 `MaybeRef<T>`（即 `Ref<T> | T`），queryKey 更是支持 `MaybeRefDeep`（嵌套对象里的 ref 也能解）。内部通过 `cloneDeepUnref` 递归解包（出处：`types.d.ts`、`useBaseQuery.mjs`）。

并且选项被包在 `computed(() => parseQueryArgs(...))` 里，所以 **queryKey / enabled 里放 `ref`、`computed`、`reactive` 都能被自动追踪**，值变化即触发重新计算 → key 变 → 重新请求。这正是 [3.3](#33-querykey-与响应式) 里 `['faults', params]` 能随筛选自动刷新的原理。

### 9.2 出参：toRefs（每个字段一个 Ref）

`useQuery` 内部把响应式 state 经 `toRefs(readonly(state))` 拆开（出处：`useBaseQuery.mjs` 第 84 行），所以返回对象的**每个数据字段都是独立 Ref**：

```ts
const { data, isLoading, error } = useQuery(...)
data.value        // ✅ script 里要 .value
isLoading.value   // ✅
```

而 `refetch` / `remove` / `mutate` 等**方法**被特意还原成普通函数（不是 Ref），直接调用即可。

### 9.3 模板自动解包 vs 嵌套 Ref 的坑

Vue 模板会自动解包**顶层** ref，但**不会**解包"对象里的 ref"。`useMutation` 返回的是一个对象，`create.isLoading` 是嵌在对象里的 Ref，模板里写 `create.isLoading` 拿到的是 Ref 对象本身（truthy），不是布尔值。

本项目 [FaultCreateView.vue](file:///e:/python项目/pipeline-fault-tracker/frontend/src/views/FaultCreateView.vue) 与 [StatusTransitionPanel.vue](file:///e:/python项目/pipeline-fault-tracker/frontend/src/components/StatusTransitionPanel.vue) 都把它**提成顶层别名**规避：

```ts
const { create } = useFaultMutations()
const submitting = create.isLoading   // 顶层别名，模板中才会被自动解包成布尔值
```

```vue
<el-button :loading="submitting" @click="onSubmit">提交登记</el-button>
```

> 同理，若直接解构 `const { isLoading } = create`，`isLoading` 仍是 Ref，模板里 `:loading="isLoading"` 也能正常解包（因为它成了顶层变量）。两种写法都行，关键是**让它处于模板能自动解包的顶层位置**。

---

## 十、本项目实战范式

### 10.1 分层结构

本项目数据层严格分三层，职责清晰、便于复用：

```
api/           纯 fetch 封装，不碰 vue-query。统一拼 URL、序列化、抛 ApiError。
  client.ts    request<T>() 通用请求 + ApiError 类
  faults.ts    fetchFaults / fetchFault / createFault / transitionFault
  pipelines.ts fetchPipelines
      ↓ 被调用
composables/   vue-query 封装层。一个业务查询/变更 = 一个 composable。
  useFaultList.ts      列表（queryKey 随筛选/分页变化）
  useFaultDetail.ts    详情（enabled 守卫非法 id）
  usePipelines.ts      流水线主数据（staleTime 5 分钟）
  useFaultMutations.ts 登记 + 状态流转（invalidate + setQueryData + 全局 toast）
      ↓ 被消费
views/ components/   只解构 composable 返回值、绑定模板，不直接写 useQuery。
```

> 好处：① 查询逻辑集中、可跨页复用（`usePipelines` 被列表页和登记页共用）；② 视图层干净，只管展示；③ 缓存失效策略统一在 mutations 里，不会各页各写一套。

### 10.2 queryKey 命名约定

| key | 含义 | 失效时机 |
|---|---|---|
| `['pipelines']` | 流水线主数据 | 极少变（staleTime 5 分钟兜底） |
| `['faults', params]` | 故障列表（区分筛选/分页） | 登记成功、状态流转后 `invalidateQueries(['faults'])` |
| `['fault', id]` | 单条故障详情 | 状态流转后 `setQueryData(['fault', id], fault)` 直接写回 |

约定：**第一个元素是资源名（复数=列表，单数=详情），后续是区分参数**。失效列表用前缀 `['faults']` 即可命中所有分页/筛选组合。

### 10.3 错误处理链路

```
fetch 失败
  ├─ 网络层（后端没起/跨域/断网）→ TypeError: Failed to fetch
  └─ HTTP 非 2xx → client.ts 抛 ApiError { status, code, details }
        ↓
mutation 的 onError(err) → toUserMessage(err) 翻译成可读文案 → ElMessage.error
query 的 error.value → 视图层 isError 分支渲染 el-alert（附 apiBase 提示排查）
```

`toUserMessage`（见 [useFaultMutations.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/composables/useFaultMutations.ts)）按错误类型分支：`ApiError` 取后端 message + 第一条字段级 details；`TypeError` 提示"无法连接后端"；其余兜底。

### 10.4 数据流示意（列表页）

```
filters(reactive)
   │  watch 筛选变化 → page 归 1
   ▼
params(computed，规范化空值)
   │  作为 queryKey 一部分
   ▼
useFaultList(params)  ── queryKey 变 → 自动 refetch（keepPreviousData 保留旧页防闪空）
   │
   ▼
{ data, isFetching, isError, error }
   │  data.value?.items / total
   ▼
FaultTable(:loading="isFetching") + el-pagination + el-alert(错误)
```

---

## 十一、常见坑与最佳实践

### 11.1 坑点清单

| # | 坑 | 现象 | 规避 |
|---|---|---|---|
| 1 | 不写 `TError` 泛型 | `error.value.message` 报类型错误（收窄成 `{}`） | `useQuery<Data, Error>` 显式声明（见 [3.2](#32-泛型)） |
| 2 | 模板里用 `mutation.isLoading` | `:loading` 恒为 truthy（拿到 Ref 对象而非布尔） | 提顶层别名 `const submitting = create.isLoading`（见 [9.3](#93-模板自动解包-vs-嵌套-ref-的坑)） |
| 3 | queryFn 不透传 `signal` | 组件卸载/key 变化后旧请求仍跑完，可能覆盖新数据（竞态） | `queryFn: ({ signal }) => api(signal)`（见 [3.4](#34-queryfn-与-signal)） |
| 4 | queryKey 放不稳定引用 | 每次渲染 key 都"变"，无限重新请求 | key 里放原始值或稳定 computed，别放每次新建的对象/函数 |
| 5 | 非法参数直接发请求 | `/faults/abc` → `GET /api/faults/NaN` → 422 | `enabled` 守卫（见 [3.7](#37-enabled--条件查询守卫)） |
| 6 | 在 `setup` / effect scope 外调用 composable | 控制台 warn，可能内存泄漏 | `useQuery` 等只在 `setup()` 或运行中的 effect scope 内调用 |
| 7 | 误用 v5 写法 | `placeholderData: keepPreviousData`、`isPending`、`gcTime` 在 v4 不存在/不生效 | 锁定 v4 API（见[第十二章](#十二v4--v5-迁移要点附录)） |
| 8 | 依赖 query 的 `onSuccess/onError/onSettled` | v4 已标 `@deprecated`，v5 移除 | 改用 `watch(data, ...)` 或在调用处处理 |

### 11.2 最佳实践

- **查询/变更都封装成 composable**，视图层只消费，不直接写 `useQuery`（见[第十章](#十本项目实战范式)）。
- **queryKey 从粗到细**，资源名在前、参数在后，方便前缀失效。
- **mutation 成功后必刷缓存**：列表用 `invalidateQueries`，详情若接口已返回最新数据用 `setQueryData` 写回（省一次请求）。
- **主数据设 `staleTime`**，列表/详情按业务设 `keepPreviousData` 改善体验。
- **错误统一翻译**：用 `ApiError` 承载后端错误体，集中一个 `toUserMessage` 转可读文案。
- **loading 用 `isFetching` 而非 `isLoading`** 驱动"已有数据的刷新"（表格蒙层不闪空）；`isLoading` 只适合"首屏完全无数据"的骨架屏。
- **透传 `signal`**，杜绝竞态。

---

## 十二、v4 → v5 迁移要点（附录）

> 本项目因 Node 16 锁定 v4。若将来升级到 Node ≥ 18 并迁移 v5，注意以下破坏性变更（仅列与本项目相关项）：

| 主题 | v4（本项目当前） | v5 |
|---|---|---|
| 保留上页数据 | `keepPreviousData: true` | `placeholderData: keepPreviousData`（`keepPreviousData` 选项被移除，改用 `placeholderData` + 导出的 `keepPreviousData` 函数） |
| 缓存回收时间 | `cacheTime` | 改名 `gcTime` |
| mutation 进行中 | `isLoading` | 改名 `isPending` |
| query 状态 | `status: 'loading'` 含"无数据" | 拆为 `status: 'pending'`，`isLoading = isPending && isFetching` |
| query 回调 | `onSuccess/onError/onSettled`（已 deprecated） | **移除**，改用 `watch` 或 `queryFn` 内处理 |
| useQuery 签名 | 支持 `(key, fn, opts)` 多重载 | 收敛为**单对象** `useQuery({ queryKey, queryFn, ...opts })` |
| 错误默认类型 | `TError = unknown` | `TError = Error` |
| Node 要求 | ≥ 16 | ≥ 18 |

迁移建议：v5 变动较大，应作为**独立任务**单独进行（依赖升级不与功能改动混提，见用户规则 3.6），先出"破坏性变更清单 + 本项目受影响位置"，逐个 composable 改并验证。

---

## 参考

- 官方文档（v4）：https://tanstack.com/query/v4/docs/vue/overview
- 类型出处（本项目已安装）：
  - `frontend/node_modules/@tanstack/vue-query/build/lib/*.d.ts`
  - `frontend/node_modules/@tanstack/query-core/build/lib/types.d.ts`
- 项目内实例：
  - [useFaultList.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/composables/useFaultList.ts)（queryKey 响应式 + keepPreviousData）
  - [useFaultDetail.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/composables/useFaultDetail.ts)（enabled 守卫）
  - [usePipelines.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/composables/usePipelines.ts)（staleTime 主数据缓存）
  - [useFaultMutations.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/composables/useFaultMutations.ts)（useMutation + invalidateQueries + setQueryData）
  - [main.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/main.ts)（VueQueryPlugin 注册）
