# Vue 3 完整使用文档

> 适用范围：**Vue 3.4+**（本项目 frontend 实际锁定 `vue@~3.4.0`，见 `frontend/package.json`）。文中 API 以 Vue 3.4 官方文档为准；`defineModel`（稳定于 3.4）、`Suspense`/`Teleport`/异步组件等特性如跨小版本有差异，会在正文单独标注。
> 本文是**通用参考手册**，覆盖 Vue 3 的核心知识面，不绑定本项目的具体业务写法；本项目如何使用 Vue（组合式 API + TanStack Query + Zod + Element Plus 的落地方式）由各自的组件源码承载，本手册只提供可查阅的通用语法与原理。
> 编写前提：了解 HTML/CSS/JavaScript 基础与 ES 模块、Promise。阅读顺序可按目录逐章推进，也可按“目录 → 具体章节 → 坑点汇总/速查表”跳跃查阅。

---

## 目录

1. [核心概念与整体认知](#一核心概念与整体认知)
2. [组件与单文件组件（SFC）](#二组件与单文件组件sfc)
3. [模板语法与内置指令](#三模板语法与内置指令)
4. [响应式系统核心 API](#四响应式系统核心-api)
5. [组合式 API 与生命周期](#五组合式-api-与生命周期)
6. [组件通信](#六组件通信)
7. [插槽 Slots](#七插槽-slots)
8. [组件注册与内置组件](#八组件注册与内置组件)
9. [表单与双向绑定深入](#九表单与双向绑定深入)
10. [状态管理与逻辑复用](#十状态管理与逻辑复用)
11. [自定义指令、过渡与动画](#十一自定义指令过渡与动画)
12. [渲染函数、 JSX 与底层机制](#十二渲染函数-jsx-与底层机制)
13. [常见坑汇总](#十三常见坑汇总)
14. [API 速查表](#十四-api-速查表)

---

## 一、核心概念与整体认知

### 1.1 Vue 是什么

Vue 是一个**声明式、组件化**的前端 UI 框架。它的核心工作是：把「数据状态」与「界面结构」建立一层自动同步的绑定——你声明“界面长什么样、依赖哪些数据”，数据变化时 Vue 自动计算最小改动并更新 DOM，你不需要手动操作 DOM。

一句话概括数据流：**状态（state）变化 → 视图（view）重新渲染 → 用户交互（event）→ 再改状态**，形成一个单向闭环。Vue 不强制单向数据流到Redux那种程度，但组件间默认遵循「父传子 props、子报父 emit」的方向。

### 1.2 两种 API 风格：选项式 vs 组合式

Vue 3 同时支持两种组织组件逻辑的写法，**可以混用，但一个组件内应选定主风格**。

| 维度 | 选项式 API（Options API） | 组合式 API（Composition API） |
|---|---|---|
| 组织方式 | 按 `data / methods / computed / watch` 等**选项类型**分块 | 按**逻辑关注点**分块，用 `ref / reactive / computed` 自由组合 |
| 状态响应式来源 | `data` 返回值被隐式代理为响应式 | 显式用 `ref()` / `reactive()` 创建 |
| 逻辑复用 | mixin / 组合式前的复用手段，易命名冲突、来源不清 | 组合式函数（composable），显式导入导出 |
| TypeScript 推断 | 较弱（`this` 类型难以推断） | 天然友好（就是普通函数与变量） |
| 适用场景 | 简单页面、已有选项式代码维护 | 中大型组件、需要跨组件复用逻辑 |

```js
// 选项式：一个功能的代码散落在多个选项里
export default {
  data() { return { count: 0 }; },
  computed: { double() { return this.count * 2; } },
  methods: { inc() { this.count++; } },
};
```

```vue
<!-- 组合式：<script setup> 里按逻辑聚合，本手册后续以此为默认写法 -->
<script setup>
import { ref, computed } from 'vue';
const count = ref(0);
const double = computed(() => count.value * 2);
const inc = () => count.value++;
</script>
```

> 记忆锚点：**选项式按“是什么类型”切文件，组合式按“是什么功能”切文件**。本手册以组合式（`<script setup>`）为主线，选项式在必要处对照说明。

### 1.3 响应式的基本心智模型

Vue 3 的响应式基于 **Proxy**（而非 Vue 2 的 `Object.defineProperty`），因此：

- 能侦测**属性的新增与删除**，也能侦测**数组索引与 length 的变化**——不再需要 `$set` / `$delete`。
- 响应式是“按需追踪”的：渲染时读到哪个响应式属性，就把当前 effect（组件渲染或 `watch`/`computed`）登记为该属性的依赖；属性变化时反向通知依赖者重跑。
- **只有被 `ref`/`reactive` 包过的数据才会触发更新**。普通 JS 对象、`ref` 里整体替换的新对象之外的原生变量，都不会自动响应。

```js
const state = reactive({ a: 1 });
state.b = 2;        // ✅ 新增属性也是响应式的（Proxy 能力）
let n = 1;          // ❌ 普通变量，改它不会触发任何视图更新
n++;
```

### 1.4 一个组件从创建到渲染的宏观流程

```text
new/createApp → 注册组件 → 挂载(mount) →
  首次 render 建立依赖 → 数据变更 →
  scheduler 排队 → 组件重新 render → diff → patch(最小 DOM 更新) →
  触发更新后的生命周期钩子
```

理解这条链路有助于排查“为什么改了数据界面没变”（多半是没进入响应式，或改动不触发依赖追踪，见[第十三章](#十三常见坑汇总)坑点）。

---

## 二、组件与单文件组件（SFC）

### 2.1 组件是渲染的复用单元

组件本质是一个“可复用的、带自己状态和模板的渲染函数”。Vue 组件可以是：

- **单文件组件（SFC，`.vue`）**：模板、脚本、样式三合一，最常用。
- **函数式/无状态组件**：只有一个渲染函数，无自身响应式状态。
- **根组件与应用实例**：`createApp(RootComponent).mount('#app')`。

```js
// main.ts —— 应用入口的典型形态
import { createApp } from 'vue';
import App from './App.vue';

createApp(App).mount('#app');
```

### 2.2 SFC 的三个块

一个 `.vue` 文件由三类顶层块组成，顺序不强制：

```vue
<template>
  <h1>{{ title }}</h1>
</template>

<script setup>
// <script setup> 是编译时语法糖：这里声明的变量/导入自动暴露给模板，
// 无需 return，也无需 components 选项注册同目录组件。
const title = 'Hello';
</script>

<style scoped>
/* scoped：样式只作用于本组件；::v-deep / :deep() 穿透子组件 */
h1 { color: #333; }
</style>
```

要点：

- **每个 `.vue` 文件只能有一个 `<template>`、最多一个 `<script>`（或一个 `<script setup>`）、任意个 `<style>`**。
- `<script setup>` 与 `<script>` 可在同一文件共存（少见，用于声明无法在 setup 里写的选项，如 `name`、自定义选项）。
- `scoped` 通过给元素加唯一属性选择器实现隔离，**不是真正的沙箱**，父子同名标签仍可能相互影响，穿透用 `:deep()`。

### 2.3 组件名与注册的两条路

- **局部注册（推荐）**：在父组件 `<script setup>` 里直接 `import`，导入名即标签名（PascalCase）。
- **全局注册**：`app.component('MyComp', MyComp)`，之后任意模板可用 `<MyComp>`；代价是失去 tree-shaking、难以追踪来源，尽量少用。

> 组件名解析：模板里 `<my-component>` 会自动匹配 `MyComponent`（kebab-case ↔ PascalCase 互为候选）。SFC 文件名默认即为组件名。

### 2.4 模板的编译约束

- 模板必须有**唯一的根节点**吗？——Vue 3 **允许 Fragment（多个顶层节点）**，不再强制单一根。多根时属性透传（fallthrough）需显式指定归属，见 6.5。
- 模板内**不能用 `return`、`var`、`import`、`while` 等语句**，只能写**表达式**（能求值的代码）；`if/else` 逻辑要用 `v-if` 指令或三目、逻辑运算表达。

---

## 三、模板语法与内置指令

### 3.1 插值

| 语法 | 作用 | 说明 |
|---|---|---|
| `{{ msg }}` | 文本插值 | 会转义 HTML，永远以纯文本渲染，防 XSS |
| `v-html="rawHtml"` | 原样渲染 HTML | ⚠️ 只用于可信内容，否则有 XSS 风险 |
| `v-text="msg"` | 相当于 `{{ }}` | 设置元素的 textContent，会覆盖子内容 |
| `v-once` | 只渲染一次 | 后续数据变化不再更新该节点，适合静态内容 |
| `v-pre` | 跳过编译 | 用于展示原始 Mustache 标签 |
| `v-cloak` | 未编译时隐藏 | 配合 `[v-cloak]{display:none}`，主要解决无构建工具时的闪烁 |

```vue
<p>{{ count + 1 }}</p>            <!-- 表达式 -->
<p>{{ ok ? 'YES' : 'NO' }}</p>    <!-- 三目 -->
<p>{{ msg.split('!').join() }}</p><!-- 方法链 OK，但不宜过复杂，复杂逻辑挪到 computed -->
```

> 模板里应避免写长表达式。多步计算、被复用计算一律抽成 `computed`，可读性和缓存都更好。

### 3.2 条件与循环

- **`v-if` / `v-else-if` / `v-else`**：真正销毁/创建 DOM，切换开销大但初始不渲染。
- **`v-show`**：始终渲染，仅切换 `display`，适合频繁切换。
- **`v-for`**：`<li v-for="(item, index) in list" :key="item.id">`。

关键纪律：

1. **`v-for` 必须绑定稳定且唯一的 `:key`**（用数据里的唯一 id，而非数组 index——index 作 key 在增删/排序时会引发复用错乱与状态串位，见坑点 13.2）。
2. **`v-if` 与 `v-for` 不要写在同一元素上**。Vue 3 中 `v-if` 优先级高于 `v-for`，此时 `v-if` 里访问不到 `v-for` 的循环变量。要过滤就用 `computed` 先算好，或用 `<template v-for>` 包裹。

```vue
<!-- ❌ 反例：v-if 拿不到 todo -->
<li v-for="todo in todos" v-if="!todo.done" :key="todo.id">{{ todo.text }}</li>

<!-- ✅ 用计算属性预过滤 -->
<li v-for="todo in activeTodos" :key="todo.id">{{ todo.text }}</li>
```

`v-for` 支持遍历：数组、对象（`(value, key, index)`）、字符串、整数（`(n, index)`，n 从 1 开始）、可迭代对象/Map/Set。

### 3.3 属性与动态绑定

- **`v-bind:`（简写 `:`）**：把表达式的值绑定到 attribute。`<img :src="url">`。
- 绑定对象：`:class="{ active: isActive }"`、`:style="{ color: activeColor }"`。
- **动态多属性**：`v-bind="objectSpread"` 一次展开一个对象到多个属性。
- `attr` 值为 `null`/`undefined` 时该 attribute 会被**移除**。
- **布尔 attribute**：`<input disabled>` 空写等同于 `true`；动态时 `:disabled="isDisabled"`。

`class` / `style` 支持数组与对象混写并自动合并：

```vue
<div :class="[{ active: isActive }, baseClass]" :style="[{ color }, fontSizeStyle]"></div>
```

### 3.4 事件绑定 `v-on`

- 简写 `@`：`<button @click="handle">`。
- 表达式形式：`@click="count++"`、`@click="say('hi')"`。
- **事件参数**：处理器自动收到原生 DOM 事件对象，`@click="handle"` 时 `handle(event)`；若写成 `@click="handle('x')"` 想拿事件需显式传 `$event`：`@click="handle('x', $event)"`。

修饰符（后缀，改变默认行为）：

| 类别 | 修饰符 | 作用 |
|---|---|---|
| 按键 | `.enter` `.esc` `.tab` `.delete` 及组合 `.ctrl.x` `.alt` `.shift` `.meta` | 只在指定按键触发 |
| 鼠标 | `.left` `.right` `.middle` `.exact` | 按钮/修饰键精确匹配 |
| 事件 | `.stop` `.prevent` `.capture` `.once` `.passive` | 等价于 stopPropagation / preventDefault / 捕获 / 只一次 / 被动 |
| 表单 | `.trim` `.number` `.lazy` | 见 9.1 v-model 修饰符 |

```vue
<input @keyup.enter="submit" />
<form @submit.prevent="onSubmit">…</form>
<button @click.stop="doThis">阻止冒泡</button>
```

### 3.5 `v-model` 双向绑定（表单核心）

`v-model` 在表单元素和组件上都是“绑定值 + 监听更新”的语法糖：

- 原生表单：`<input>` / `<textarea>` / `<select>` / `<input type="checkbox">` / `<input type="radio">`，见第九章。
- 组件上：默认等价于 `:modelValue` + `@update:modelValue`；3.4 起可用 `defineModel()` 简化，见 6.4。

### 3.6 其他常用指令速记

| 指令 | 用途 |
|---|---|
| `v-slot`（简写 `#`） | 插槽内容分发，见第七章 |
| `v-memo` | 记忆化子树，跳过不必的重渲染（低频优化） |
| `v-is` | 在 `<table>` 等受限容器里通过指令使用自定义组件 |

---

## 四、响应式系统核心 API

本章是 Vue 3 的心脏。`<script setup>` 里可用的一切响应式能力都来自这里。

### 4.1 `ref` —— 任意值的响应式盒子

```js
import { ref } from 'vue';
const count = ref(0);        // 基本类型
const user = ref({ n: 'A' }); // 对象也行，内部仍用 reactive 包裹
count.value++;               // 脚本里必须 .value
```

- **在 `<script>` 中**访问/修改要写 `.value`；**在模板中自动解包**，直接 `{{ count }}` 即可，无需 `.value`。
- `ref` 可用于任何类型；`reactive` 只能用于对象。
- **数组里的 ref 不会自动解包**：`list.value[0].value`；模板中的顶层 ref 才自动解包，见坑点 13.3。
- `shallowRef(obj)`：只对 `.value` 的整体替换触发更新，**不深入**监听对象内部属性变化，适合大数据/不可变结构/第三方实例，性能更好。

```js
const big = shallowRef({ list: [] });
big.value.list.push(1); // ❌ 不触发更新（未整体替换）
big.value = { list: [...big.value.list, 1] }; // ✅ 整体替换才触发
```

### 4.2 `reactive` —— 对象深度代理

```js
import { reactive } from 'vue';
const state = reactive({ count: 0, nested: { a: 1 } });
state.count++;          // 直接改，无需 .value
state.newKey = 2;       // ✅ 新增属性也响应（Proxy）
```

限制与纪律：

1. **只能用于对象类型**（object / array / Map / Set / Date 等）。
2. **不能整体替换**：`state = reactive({...})` 会丢掉响应式（因为替换的是普通变量绑定，模板仍指向旧代理）。要重置用 `Object.assign(state, newVal)`。
3. **解构会丢失响应式**：`const { count } = state` 后 `count` 是普通快照。需要保持响应式用 `toRefs(state)`。
4. `shallowReactive` 只代理顶层属性。

> `ref` vs `reactive` 选型：**默认用 `ref`**——它有 `.value` 的心智负担，但能对基本类型、能整体安全替换、能在函数间保持响应式传递。`reactive` 适合一组固定字段的状态对象，且记得别解构、别整体替换。

### 4.3 `computed` —— 派生值与缓存

```js
import { computed, ref } from 'vue';
const first = ref('A');
const last = ref('B');
const full = computed(() => `${first.value} ${last.value}`); // 只读
```

- **惰性 + 缓存**：只有依赖变化且被读取时才重算；依赖没变则命中缓存，比模板里写方法调用更省。
- **可写计算属性**：

```js
const scale = computed({
  get: () => size.value,
  set: (v) => { size.value = v; },
});
```

- 计算属性**应当是纯函数**，不要在 getter 里改别的状态或做副作用（副作用放 `watch`）。

### 4.4 `watch` / `watchEffect` —— 副作用

`watchEffect`：**立即执行**，自动收集依赖（回调里读到哪些 ref/reactive 就追踪哪些），依赖变化时重跑。适合“副作用与多个源绑定、不关心旧值”的场景。

```js
import { watchEffect } from 'vue';
watchEffect(() => {
  document.title = `${page.value} - ${count.value}`; // 自动追踪 page、count
});
```

`watch`：**明确指定源**，能拿到新旧值，默认惰性（懒执行，除非 `immediate`）。

```js
import { watch } from 'vue';
// 监听单个 ref
watch(count, (newV, oldV) => { /* ... */ });

// 监听多个源
watch([a, b], ([av, bv], [oa, ob]) => { /* ... */ });

// 监听 reactive 的某个 getter（想比对旧值必须用 getter 返回值）
watch(() => state.count, (n, o) => { /* 这样 n!==o 才有效 */ });

// 深度监听（reactive 对象默认就是 deep；ref 包对象需显式 deep）
watch(state, cb, { deep: true });
```

`watch` 常用选项：

| 选项 | 作用 |
|---|---|
| `immediate: true` | 创建时立即执行一次回调 |
| `deep: true` | 递归追踪嵌套变化 |
| `once: true`（3.4 实验起） | 只触发一次后自动停止，等价手动 `stop()` |
| `flush: 'pre'/'post'/'sync'` | 回调时机。默认 `pre`（DOM 更新前）；`post` 想在回调里读更新后的 DOM 用它，或改用 `onUpdated` |

`watch` 返回一个**停止函数**，可在合适时机（如组件卸载前）手动 `stop()`。

### 4.5 响应式转换工具

| API | 作用 |
|---|---|
| `toRaw(refOrReactive)` | 拿到 Proxy 背后的原始对象（脱离响应式做只读比对/序列化） |
| `markRaw(obj)` | 标记对象永不转成响应式（用于不该被代理的第三方实例，如图表、DOM） |
| `isRef` / `isReactive` / `isReadonly` / `isProxy` | 类型判断 |
| `toRef(obj, 'key')` | 把 reactive 的某属性转为与之联动的 ref |
| `toRefs(obj)` | 把 reactive 每个属性都转成 ref，用于解构不丢响应式 |

```js
// 组合式函数返回响应式状态时，用 toRefs 让调用方解构仍保持联动
export function useMouse() {
  const pos = reactive({ x: 0, y: 0 });
  // ...
  return toRefs(pos); // { x: Ref, y: Ref }
}
```

### 4.6 只读与受限可写

| API | 作用 |
|---|---|
| `readonly(obj)` | 深层只读代理，任何写操作开发环境警告 |
| `shallowReadonly` | 仅顶层只读 |

常用于把状态“下发”给子组件、防止子组件直接改父状态。


---

## 五、组合式 API 与生命周期

### 5.1 `<script setup>` 到底做了什么

`<script setup>` 是编译时语法糖，它让：

- 顶层声明的 import、`ref`、`reactive`、`computed`、函数**自动暴露给模板**，不用 `return`。
- 导入的组件**自动注册**，不用 `components` 选项。
- 用 `defineProps` / `defineEmits` / `defineExpose` / `defineModel` 等**编译器宏**声明组件接口（宏无需 import，只在 `<script setup>` 内可用）。

### 5.2 生命周期钩子

组合式 API 里生命周期是**在 `setup` 同步执行期间注册的函数**，钩子名以 `on` 开头：

```vue
<script setup>
import {
  onBeforeMount, onMounted,
  onBeforeUpdate, onUpdated,
  onBeforeUnmount, onUnmounted,
  onErrorCaptured, onRenderTracked, onRenderTriggered,
} from 'vue';

onMounted(() => {
  // DOM 已就绪，适合初始化第三方库、请求数据、加事件监听
});
onUnmounted(() => {
  // 清理定时器、解绑事件、取消订阅——成对出现，防止泄漏
});
</script>
```

| 钩子 | 时机 | 典型用途 |
|---|---|---|
| `onBeforeMount` | 挂载前，已建立响应式但未渲染 DOM | 少用 |
| `onMounted` | 挂载完成，DOM 可访问 | 取数据、初始化 DOM 相关库 |
| `onBeforeUpdate` | 状态变更、DOM 更新前 | 记录更新前 DOM 状态 |
| `onUpdated` | DOM 更新完成 | 依赖更新后 DOM 的操作（避免在此改状态造成死循环） |
| `onBeforeUnmount` | 卸载前 | 清理 |
| `onUnmounted` | 卸载后 | 清理 |
| `onErrorCaptured` | 捕获后代组件错误 | 返回 `false` 阻断继续上抛 |
| `onRenderTracked`/`onRenderTriggered` | 追踪/触发渲染依赖 | 仅调试 |

> 注意：`<script setup>` 顶层代码本身就等价于 `setup()`/`onBeforeCreate`+`created`——它在组件实例创建时同步执行，**没有 `onSetup`/`created`/`beforeCreate` 钩子**。数据初始化直接写在顶层即可。

### 5.3 组合式函数（composable）

Vue 3 复用逻辑的官方推荐方式：**以 `use` 开头的普通函数，内部自由使用响应式 API 与生命周期**。

```js
// useMouse.js
import { ref, onMounted, onUnmounted } from 'vue';
export function useMouse() {
  const x = ref(0), y = ref(0);
  const update = (e) => { x.value = e.pageX; y.value = e.pageY; };
  onMounted(() => window.addEventListener('mousemove', update));
  onUnmounted(() => window.removeEventListener('mousemove', update));
  return { x, y }; // 返回 ref，调用方各自持有独立状态
}
```

约定（非强制但通行）：

- 命名 `useXxx`；参数与返回值都用 `ref`，保证响应式联动。
- 生命周期钩子只能在 `setup` **同步**阶段注册——组合式函数里注册钩子时，必须在组件 setup 同步调用它（不能在异步回调里才调用 `useXxx`，否则钩子注册失败，见坑点 13.5）。

---

## 六、组件通信

Vue 组件通信按方向分：**父→子（props）**、**子→父（emit）**、**双向（v-model）**、**跨层级（provide/inject）**、**父操作子（ref + expose）**、**兄弟/任意（状态管理或事件总线）**。

### 6.1 父传子：props

```vue
<!-- Child.vue -->
<script setup>
// 带类型与校验的声明（编译器宏）
const props = defineProps({
  title: { type: String, required: true },
  size: { type: String, default: 'medium' },
  count: { type: Number, default: 0 },
});
// 或用 TS 泛型：defineProps<{ title: string; size?: string }>()
</script>
<template><span>{{ props.size }}: {{ title }}</span></template>
```

纪律：

1. **props 单向、只读**。子组件不得直接改 props；需要基于 props 的本地可变副本，用 `ref(props.xxx)` 初始化或 `toRef` 建立联动。
2. 传入的对象/数组本身仍是响应式的，**修改其内部属性会影响父组件数据**——这是隐蔽的双向污染，务必约定“props 只读”。
3. `type` 支持 `String/Number/Boolean/Array/Object/Function/Date/Symbol` 及自定义构造器。

### 6.2 子报父：emit

```vue
<!-- Child.vue -->
<script setup>
const emit = defineEmits(['change', 'submit']); // 或带校验/类型
function onClick() { emit('change', 42); }
</script>

<!-- Parent.vue -->
<Child @change="handleChange" />
```

- 事件名建议用 **kebab-case**（模板中 `@update:model-value` 与 camel 有大小写转换坑）。
- 可声明校验函数与 TS 类型；`defineEmits<{ (e:'change', v:number): void }>()`。
- 未声明的事件会落到原生 DOM 事件（透传），声明后行为更可控。

### 6.3 `defineExpose` —— 父调用子的方法

默认 `<script setup>` 组件是**关闭的**：父组件即便拿到子组件的 ref 也访问不到内部变量。需要暴露的接口用 `defineExpose`：

```vue
<!-- Child.vue -->
<script setup>
function reset() { /* ... */ }
defineExpose({ reset }); // 只暴露 reset
</script>
```

父组件：`<Child ref="childRef" />` + `childRef.value.reset()`。

### 6.4 组件上的 `v-model` 与 `defineModel`

一个组件可有**多个** `v-model`：

```vue
<!-- Parent -->
<UserForm v-model:firstName="a" v-model:lastName="b" />

<!-- Child（Vue 3.4 稳定语法） -->
<script setup>
const firstName = defineModel('firstName'); // 返回一个可读写 ref
const lastName = defineModel('lastName');
</script>
```

- 默认（不带名）的 `v-model` 对应 `modelValue` prop + `update:modelValue` 事件。
- 3.4 之前用 `defineEmits`+`defineProps` 手写这套；`defineModel` 是它的语法糖，且可加 `local`/选项。
- `v-model` 修饰符：`v-model.trim="x"`，子组件通过 `useModelModifiers` / defineModel 选项读取。

### 6.5 属性透传（fallthrough）与多根

未在子组件 props 中声明的 attribute（`class`、`style`、原生事件、`data-*` 等）会**自动合并到子组件根元素**。

- 不想透传：`inheritAttrs: false`，然后用 `$attrs` 手动绑定到需要的元素。
- **多根（Fragment）组件不会自动透传**（不知该给哪个根），必须显式 `v-bind="$attrs"` 指定，否则开发环境告警。

### 6.6 跨层级：provide / inject

适合“依赖注入”式深层传递（主题、当前用户、表单组上下文），避免逐层 props 透传（prop drilling）。

```js
// 祖先
import { provide, readonly, ref } from 'vue';
const theme = ref('dark');
provide('theme', readonly(theme)); // 提供只读，防止后代直接改

// 后代（任意深度）
import { inject } from 'vue';
const theme = inject('theme', 'light'); // 第二参数为默认值（可选链兜底）
```

纪律：

- key 用 `Symbol` 或 `InjectionKey<T>`（TS）避免字符串冲突并携带类型。
- **provide 的值要保持响应式**：提供 `ref`/`reactive` 而非其快照，否则后代收不到更新。
- 想“可写但集中管理”，同时 `provide(key, readonly(state))` 与 `provide(key+'Set', mutateFn)`，让读走只读、改走方法（参考 Element Plus 表单上下文的实现思路）。

### 6.7 兄弟 / 任意组件

- **提升到共同父组件**（props+emit 中继，最朴素）。
- **共享 composable + 模块级单例状态**（轻量全局）。
- **Pinia 状态管理**（正式方案，见第十章）。
- 传统全局事件总线在 Vue 3 已被移除 `this.$on/$emit`，如需可用第三方 `mitt`，但优先上面三种。

---

## 七、插槽 Slots

插槽让父组件向子组件“传模板而非传值”，是内容分发的核心。

### 7.1 默认插槽

```vue
<!-- Card.vue -->
<template><div class="card"><slot>默认内容（fallback）</slot></div></template>

<!-- 使用 -->
<Card>塞进默认插槽的内容</Card>
```

### 7.2 具名插槽

```vue
<!-- Card.vue -->
<template>
  <div><slot name="header">无头</slot><slot /></div>
</template>

<!-- 使用：v-slot 简写 # -->
<Card>
  <template #header><h2>标题</h2></template>
  <p>正文进默认插槽</p>
</Card>
```

### 7.3 作用域插槽（子传数据给父模板）

子组件把内部数据作为插槽 prop 抛出，父组件在插槽内容里消费：

```vue
<!-- List.vue -->
<template>
  <ul><li v-for="item in items" :key="item.id"><slot :row="item" :index="loopIndex">{{ item.text }}</slot></li></ul>
</template>

<!-- 使用 -->
<List>
  <template #default="{ row, index }">
    {{ index }} - {{ row.name }}   <!-- 父组件决定每一行怎么渲染 -->
  </template>
</List>
```

要点：

- 插槽内容**永远在定义它的父组件作用域**里编译，能访问父组件的数据；插槽 prop 是子组件传给父模板的唯一“越界”通道。
- 解构插槽 prop 可改名、可给默认值：`#default="{ row: r = {} }"`。
- 动态插槽名：`#[dynamicName]` 或 `v-slot:[dynamicName]`。
- Vue 3.4 起，非动态插槽内容若为纯文本/静态，编译器会做**插槽内容缓存**优化，减少子组件重渲染时的无谓更新。

---

## 八、组件注册与内置组件

### 8.1 动态组件 `<component :is>`

```vue
<component :is="currentTabComp" />
<!-- currentTabComp 可以是导入的组件对象，也可以是已注册组件的字符串名 -->
```

- 切换会**销毁旧组件、创建新组件**。要保留状态配合 `<KeepAlive>`。
- 可传 props / 事件，与普通标签一致。

### 8.2 `KeepAlive` —— 缓存组件状态

```vue
<KeepAlive :include="['CompA']" :max="10">
  <component :is="view" />
</KeepAlive>
```

- 被缓存的组件不触发 `onUnmounted`，改触发 `onActivated` / `onDeactivated`。
- `include`/`exclude`/`max`（LRU 淘汰）；匹配依据是组件 `name`（`<script setup>` 需用 `defineOptions({ name })` 或文件名）。

### 8.3 `Teleport` —— 传送到组件树之外

把 DOM 渲染到 body 等指定位置，但**逻辑上仍是当前组件的子节点**（能正常收 props/emit、走生命周期）。常用于模态框、浮层、toast。

```vue
<Teleport to="body" :disabled="isMobile">
  <div class="modal">…</div>
</Teleport>
```

### 8.4 `Suspense` —— 异步内容编排（实验性）

等待后代组件的异步依赖（如 `async setup`、异步组件加载）完成时展示 fallback：

```vue
<Suspense>
  <template #default><AsyncChild /></template>
  <template #fallback><p>加载中…</p></template>
</Suspense>
```

> `Suspense` 仍标注为实验特性，API 可能微调，大规模使用前关注版本说明。数据加载更推荐 TanStack Query 之类的方案而非直接依赖它。

### 8.5 异步组件 `defineAsyncComponent`

按需/延迟加载组件，配合路由懒加载、降低首屏体积：

```js
import { defineAsyncComponent } from 'vue';
const Heavy = defineAsyncComponent({
  loader: () => import('./Heavy.vue'),
  loadingComponent: Loader,
  errorComponent: Err,
  delay: 200,     // 显示 loading 前的延迟，防闪烁
  timeout: 10000, // 加载超时
});
```

### 8.6 `Transition` / `TransitionGroup`

见第十一章（过渡与动画）。


---

## 九、表单与双向绑定深入

### 9.1 原生表单上的 `v-model`

| 元素 | 绑定行为 |
|---|---|
| `<input type="text">` / `<textarea>` | 绑定 `value` |
| `<input type="checkbox">`（单个） | 绑定 `checked`（布尔） |
| `<input type="checkbox">`（多个 + 数组 v-model） | 勾选值收集进数组 |
| `<input type="radio">` | 选中时把 `value` 属性写入 v-model |
| `<select>`（单选/`multiple`） | 绑定选中项的 value |

修饰符：

- `.lazy`：改为 `change` 事件同步（而非每次 `input`），减少高频更新。
- `.number`：自动 `parseFloat` 转数字。
- `.trim`：去除首尾空格。
- 可组合：`v-model.trim.number="age"`。

### 9.2 值绑定 `:value` 与“动态 value”

radio/checkbox 的选项值应通过 `:value="opt"`（动态）绑定，`v-model` 绑的是**当前选中项**，两者不要混：

```vue
<label v-for="f in fruits" :key="f">
  <input type="checkbox" :value="f" v-model="picked" /> {{ f }}
</label>
<!-- picked 是数组，勾选把对应 f 推入 -->
```

### 9.3 表单校验的组织方式

Vue 本身不提供校验，只提供绑定与响应式。常见路线：

1. **组合式函数 + 计算属性**：把字段值、错误信息、校验函数聚合到 `useForm`。
2. **schema 校验库**：如本项目采用的 **Zod**——用 schema 定义规则，`safeParse` 得到结构化错误，再映射到 UI。校验逻辑与视图解耦，便于前后端共用 schema。
3. **组件库表单**：Element Plus 的 `<el-form :rules>` 等，把校验交给组件。

不论哪种，核心纪律一致：**受控输入（v-model 单一数据源）+ 明确的校验触发时机（blur / submit / 实时）**，避免同时维护多份“影子状态”。

### 9.4 非受控 vs 受控

推荐全程**受控**：值以响应式状态为准。若需“本地编辑、点保存才提交”，用 `ref(props.xxx)` 复制一份本地态，提交时再 emit，避免直接改 props。

---

## 十、状态管理与逻辑复用

### 10.1 何时需要什么

| 需求 | 首选 |
|---|---|
| 单组件内状态 | `ref` / `reactive` |
| 两个组件局部共享 | composable + 提升状态到共同父 |
| 跨层级少量共享 | `provide` / `inject` |
| 全局、多页面、需 devtools/持久化 | **Pinia**（Vue 官方推荐） |
| 服务端数据缓存（列表/详情/失效重取） | TanStack Query 等数据层（与 Pinia 并存、各司其职） |

> 区分**客户端状态**（UI、表单草稿，归 Pinia/composable）与**服务端状态**（后端数据的缓存副本，归查询库）。把服务端数据塞进全局 store 手动同步失效，是常见架构债。

### 10.2 Pinia 基本形态

Pinia 是 Vue 3 官方状态库，用“store”取代 Vuex 的 mutation/action 复杂度，天然组合式与 TS 友好。

```js
// stores/counter.js —— setup store（组合式风格）
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useCounter = defineStore('counter', () => {
  const count = ref(0);
  const double = computed(() => count.value * 2);
  function inc() { count.value++; }
  return { count, double, inc };
});
```

```vue
<script setup>
import { useCounter } from '@/stores/counter';
const counter = useCounter(); // 解构会丢响应式，需 storeToRefs
</script>
<template><button @click="counter.inc">{{ counter.double }}</button></template>
```

要点：

- 从 store **解构状态要用 `storeToRefs(store)`**，直接解构 `const { count } = store` 会丢响应式；**方法/action 可直接解构**。
- 批量改状态：`store.$patch({ ... })`；重置：`store.$reset()`；订阅：`store.$subscribe`。
- 在组件外（如路由守卫、拦截器）使用 store 需在 `app.use(pinia)` 之后调用。

### 10.3 逻辑复用的优先级

复用顺序建议：**composable（无状态共享）→ provide/inject（树内共享）→ Pinia（全局共享）**。三者都能复用“逻辑”，区别在状态的**作用域与生命周期**。把带副作用的复用逻辑写成 `useXxx`，把需要跨路由存活的全局数据放 Pinia。

---

## 十一、自定义指令、过渡与动画

### 11.1 自定义指令

当需要对**底层 DOM**做复用行为（聚焦、权限隐藏、拖拽、懒加载）而组件抽象不经济时，用指令。

```js
// 注册局部指令（<script setup> 里以 v 开头的驼峰变量即指令，vFocus -> v-focus）
const vFocus = {
  mounted: (el) => el.focus(),
};
```

```vue
<input v-focus />
```

钩子（相对 Vue 2 已改名，语义对齐组件生命周期）：

| 钩子 | 触发 |
|---|---|
| `created` | 元素/组件创建后、指令绑定前 |
| `mounted` | 绑定元素插入父 DOM 后 |
| `beforeUpdate` | 含指令的组件 VNode 更新前 |
| `updated` | 组件 VNode 更新后 |
| `beforeUnmount` | 卸载前 |
| `unmounted` | 卸载后 |

回调签名 `(el, binding, vnode)`；`binding.value` / `binding.arg` / `binding.modifiers` 拿到使用处传参。全局指令 `app.directive('name', {...})`。**能用组件/属性解决的不要用指令**，指令应少用。

### 11.2 `Transition` 单元素过渡

```vue
<Transition name="fade">
  <p v-if="show">内容</p>
</Transition>
```

自动应用 6 个 class：`{name}-enter-from/enter-active/enter-to`、`{name}-leave-from/leave-active/leave-to`。也可用 `@before-enter`、`@enter`、`@after-enter`、`@enter-cancelled`（leave 同理）做 JS 动画（对接 GSAP/Anime.js）。

- `mode="out-in"` / `"in-out"` 控制进出时序（切换列表项、路由转场常用 `out-in`）。
- `appear` 首次渲染也播放；`:type` 指定 transition/animation；`:duration` 精确时长。

### 11.3 `TransitionGroup` 列表过渡

```vue
<TransitionGroup name="list" tag="ul">
  <li v-for="item in items" :key="item.id">{{ item.text }}</li>
</TransitionGroup>
```

- **每个子项必须有唯一 `key`**。
- 移动过渡（FLIP）依赖 `v-move`/`{name}-move` class；`leave-active` 需 `position:absolute` 配合避免挤压。

### 11.4 路由级过渡

```vue
<RouterView v-slot="{ Component }">
  <Transition name="fade" mode="out-in">
    <component :is="Component" />
  </Transition>
</RouterView>
```

---

## 十二、渲染函数、JSX 与底层机制

> 绝大多数场景用模板即可。以下仅在“需要完全动态的渲染逻辑、写通用组件库”时了解。

### 12.1 渲染函数 `h()`

模板最终被编译成渲染函数。也可以直接写：

```js
import { h } from 'vue';
export default {
  render() {
    return h('div', { class: 'box' }, [
      h('h1', this.title),
      h(MyChild, { msg: 'hi' }),
    ]);
  },
};
```

`h(type, props, children)`：type 为标签/组件/Fragment；props 含 attrs、props、onXxx 事件；children 为字符串/数组/slots 对象。

### 12.2 JSX

在 `.tsx` / `<script lang="tsx">` 中用 JSX，需配置 `@vitejs/plugin-vue-jsx`。语义与 `h()` 等价，适合函数式组件与高度动态 UI。

### 12.3 虚拟 DOM 与 diff 要点

- Vue 用**带 key 的同层 diff + 双端比较 + 最长递增子序列**复用节点，这就是 `v-for` 强依赖 `key` 的底层原因。
- **静态提升 / PatchFlags / 树结构打洞**：编译器把静态节点提出、给动态部分打标记，使更新只 diff 动态部分，是 Vue 3 相对 Vue 2 的性能核心。理解它有助于写“对编译器友好”的模板（少用复杂行内表达式，善用 `v-memo`、静态 class 等）。

### 12.4 模板 ref

```vue
<script setup>
import { ref, onMounted } from 'vue';
const inputEl = ref(null);          // 普通元素
const childRef = ref(null);         // 子组件实例（需子组件 defineExpose）
onMounted(() => inputEl.value.focus());
</script>
<template>
  <input ref="inputEl" />
  <Child ref="childRef" />
</template>
```

`v-for` 中的 ref 会收集为数组：`:ref="el => (refs[i] = el)"`。


---

## 十三、常见坑汇总

> 编号与正文交叉引用对应，排查问题时优先来这里对号入座。

### 13.1 `ref` 忘了 `.value`（脚本侧）

在 `<script setup>` 里读写 `ref` 必须 `.value`，漏写拿到的是盒子对象本身，判断/计算全错；模板里则**不能**写 `.value`（自动解包）。`reactive` 对象属性不需要 `.value`。混用两者时最易踩。

### 13.2 用数组 index 作 `v-for` 的 `key`

index 会随增删/排序漂移，导致 Vue 复用错节点、组件内部状态（输入框、勾选）串到别的数据上，且子组件不会正确更新。**始终用数据自身的稳定唯一 id**。列表完全静态、永不重排才勉强可用 index。

### 13.3 数组 / 普通对象里的 `ref` 不自动解包

自动解包**只发生在模板顶层和 reactive 对象的直接属性**。数组元素、Map/Set、以及“ref 里再套 ref”的内层 ref 都需要手动 `.value`。

```js
const arr = reactive([ref(1), ref(2)]);
arr[0].value++;            // 需要 .value
const wrapped = ref({ n: ref(5) });
wrapped.value.n.value;     // 内层 ref 需 .value
```

### 13.4 `reactive` 整体替换 / 解构丢响应

`state = reactive({...})`、`const { a } = state` 都会脱离响应式。重置用 `Object.assign(state, 新值)`；解构用 `toRefs(state)`。见 4.2。

### 13.5 生命周期/`watch` 在异步里注册失效

组合式 API 的钩子与 `watch` 必须在 `setup` **同步**执行阶段注册。在 `await` 之后或回调里调用 `onMounted`/`useXxx`（内含钩子注册）会静默失效并告警。需要异步后再注册的，把逻辑放回同步段或用 `onServerPrefetch`/显式 effect scope。

### 13.6 `watch` 监听 reactive 属性拿不到旧值

`watch(state.count, ...)` 传的是**值**不是 getter，Vue 无法比对新旧（都指向同一响应式源）。要 `n !== o` 生效必须写成 `watch(() => state.count, ...)`。

### 13.7 深层 watch 的性能与“意外触发”

对大对象 `watch(x, cb, { deep: true })` 会递归遍历所有嵌套属性，代价高且任何细微变动都触发。只关心某几个字段时用 getter 精确监听，而非整对象 deep。

### 13.8 直接修改 props / emit 声明缺失

子组件 `props.list.push(...)` 会污染父状态并触发只读告警。需要本地改先复制。自定义事件名在模板监听时，**camel 事件在 DOM 模板里要转 kebab**（`@update:modelValue` 在浏览器原生 HTML 模板大小写不敏感会失效，SFC 模板无此问题）。

### 13.9 多根组件属性透传丢失

Fragment（多根）组件默认不知道把 `class`/事件落到哪个根，需在其中一根显式 `v-bind="$attrs"`，否则父传入的透传属性无效。

### 13.10 `KeepAlive` 里等 `onUnmounted` 做清理不执行

被缓存组件卸载走的是 `onDeactivated`，不触发 `onUnmounted`；真正销毁（超出 max / 被 exclude）才 unmount。需要“离开时暂停”的逻辑放 `onDeactivated`，别只写 `onUnmounted`。

### 13.11 `<script setup>` 组件默认对外关闭

父组件 `xxxRef.value.someMethod()` 报 undefined——子组件没 `defineExpose`。这是设计上的封装默认，需要暴露的接口显式 `defineExpose`。

### 13.12 解构 store 丢响应式

`const { count } = useCounter()` 后 count 不再联动。用 `storeToRefs`；action/方法可直接解构。见 10.2。

### 13.13 `v-if` 与 `v-for` 同元素

Vue 3 中 `v-if` 先于 `v-for` 求值，`v-if` 访问不到循环变量，得到 `undefined` 报错或永远为假。用 computed 预过滤或 `<template v-for>` 分层。见 3.2。

### 13.14 组件外/早于 pinia 安装使用 store

在 `app.use(createPinia())` 之前 import 并调用 store，会报 “no active pinia”。确保在应用装配完成后再在守卫、拦截器等处使用。

### 13.15 误把服务端数据塞进全局 store 手改

后端返回的列表放 Pinia 再到处手动同步，容易脏。这类“远端缓存状态”交给查询层（TanStack Query 等）做缓存/失效，store 只放真正的客户端全局状态。

---

## 十四、API 速查表

### 14.1 响应式

| API | 一句话 |
|---|---|
| `ref(v)` / `.value` | 任意类型的响应式盒子，脚本需 `.value` |
| `shallowRef(v)` | 仅整体替换 `.value` 触发，不深入 |
| `reactive(obj)` | 对象深度代理，无需 `.value`，勿整体替换/解构 |
| `shallowReactive` | 只代理顶层 |
| `readonly` / `shallowReadonly` | 只读代理 |
| `computed(get[, set])` | 缓存派生值，可只读/可写 |
| `watch(src, cb, opts)` | 显式源、拿新旧值、可懒执行 |
| `watchEffect(cb, opts)` | 自动收集依赖、立即执行 |
| `watchPostEffect` / `watchSyncEffect` | flush post / sync 的 watchEffect 变体 |
| `toRef` / `toRefs` | reactive 属性 ↔ ref 联动，解构不丢响应 |
| `toRaw` / `markRaw` | 取原始对象 / 标记永不代理 |
| `isRef` / `isReactive` / `isReadonly` / `isProxy` | 类型判断 |
| `unref` / `toValue` | 拆 ref / 归一 ref\|getter\|原值 |

### 14.2 生命周期（组合式）

`onBeforeMount` · `onMounted` · `onBeforeUpdate` · `onUpdated` · `onBeforeUnmount` · `onUnmounted` · `onActivated` · `onDeactivated` · `onErrorCaptured` · `onRenderTracked` · `onRenderTriggered` · `onServerPrefetch`

### 14.3 组件与依赖注入

| API | 用途 |
|---|---|
| `defineProps` / `defineEmits` | 声明入参 / 事件（宏） |
| `defineModel` | 组件 v-model 语法糖（3.4 稳定） |
| `defineExpose` | 暴露子组件接口给父 |
| `defineOptions` | 声明 name 等无法在 setup 的选项 |
| `defineSlots` | 声明插槽类型（TS） |
| `provide` / `inject` | 跨层级依赖注入 |
| `useAttrs` / `useSlots` / `useCssVars` / `useModel` | 读取 attrs/slots/CSS 变量/v-model |
| `defineAsyncComponent` | 异步组件 |
| `createApp` / `app.use/mount/component/directive/provide/mixin` | 应用装配 |

### 14.4 内置组件

`<Teleport>` · `<Suspense>` · `<KeepAlive>` · `<BaseTransition>` · `<Transition>` · `<TransitionGroup>`

### 14.5 内置指令

`v-bind(:)` · `v-on(@)` · `v-model` · `v-show` · `v-if/v-else-if/v-else` · `v-for` · `v-text` · `v-html` · `v-pre` · `v-cloak` · `v-once` · `v-slot(#)` · `v-memo` · `v-is`

### 14.6 效果作用域与进阶

| API | 用途 |
|---|---|
| `effectScope()` / `.stop()` | 批量管理 effect/watch 的销毁 |
| `getCurrentScope` / `onScopeDispose` | 组合式函数里挂作用域清理 |
| `customRef` / `readonly` 工厂 | 自定义 ref 追踪逻辑（如防抖） |
| `h` / `Fragment` / 静态提升 | 渲染函数与编译优化 |
| `createHydrationRenderer` / 自定义渲染器 | 非 DOM 目标（进阶） |

### 14.7 Pinia

`createPinia` · `setActivePinia` · `defineStore`（选项式 / setup 式）· `storeToRefs` · `mapStores/mapState/mapActions` · store 实例方法 `$patch`/`$reset`/`$subscribe`/`$onAction`。

---

> 本手册为通用参考，API 细节以你所用 Vue 小版本的官方文档为最终依据；涉及本项目具体组件写法时，以 `frontend/src` 下实际源码为准。
