# CSS Grid 布局完整使用文档

> 适用范围：CSS Grid Layout Level 1 / Level 2 规范语法，面向所有现代浏览器（Chrome 57+、Firefox 52+、Safari 10.1+、Edge 16+）。`subgrid` 需 Chrome 117+ / Safari 16+ / Firefox 71+，文中单独标注。
> 本文所有属性名、取值与行为描述均依据 W3C CSS Grid Layout 规范及 MDN 文档整理；未在本项目实际验证浏览器行为，作为通用参考手册使用。
> 阅读前提：了解盒模型与 Flexbox 基础。Flexbox 与 Grid 的选型对比见[第九章](#九grid-与-flexbox-对比与选型)。

---

## 目录

1. [核心概念与术语](#一核心概念与术语)
2. [容器基础属性](#二容器基础属性)
3. [轨道定义：grid-template 与隐式轨道](#三轨道定义grid-template-与隐式轨道)
4. [项目定位：线、区域与命名](#四项目定位线区域与命名)
5. [对齐与分布](#五对齐与分布)
6. [间距：gap](#六间距gap)
7. [层叠顺序与网格溢出](#七层叠顺序与网格溢出)
8. [响应式网格模式](#八响应式网格模式)
9. [Grid 与 Flexbox 对比与选型](#九grid-与-flexbox-对比与选型)
10. [典型布局实战](#十典型布局实战)
11. [子网格 subgrid](#十一子网格-subgrid)
12. [常见坑汇总](#十二常见坑汇总)
13. [属性速查表](#十三属性速查表)

---

## 一、核心概念与术语

### 1.1 一句话理解 Grid

Grid 是**二维布局系统**：先沿水平轴和垂直轴把容器划分成一张网格，再把内容摆进网格的单元格或区域。它与 Flexbox 的根本区别是——**布局由容器决定，而不是由内容撑出**（对应坑点 [12.1](#121-坑轨道尺寸写错导致-fr-失效)）。

### 1.2 六个基本术语

```text
      列轨道1      列轨道2      列轨道3
   ┌───────────┬───────────┬───────────┐
 1 │           │           │           │ 1   ← 水平线（行线）
   ├───────────┼───────────┼───────────┤
 2 │   行轨道1  │  ←单元格→  │           │ 2
   ├───────────┼───────────┼───────────┤
 3 │           │           │           │ 3
   └───────────┴───────────┴───────────┘
        1           2           3   4      ← 垂直线（列线）
```

| 术语 | 英文 | 含义 |
|---|---|---|
| 网格容器 | grid container | 设置了 `display: grid` 的元素 |
| 网格项目 | grid item | 容器的**直接子元素**（非直接子元素不参与布局） |
| 轨道 | track | 一行或一列的整体；一行 = 行轨道，一列 = 列轨道 |
| 线 | line | 轨道之间的分界。N 条轨道产生 N+1 条线，**从 1 开始编号**，可用负数从尾 counting（`-1` 是最后一条线） |
| 单元格 | cell | 两条相邻行线与两条相邻列线围成的最小单位 |
| 网格区域 | area | 跨一个或多个单元格的矩形，由四条线围成 |

> 记忆锚点：**轨道由模板定义，线是轨道的副产品**。所有定位语法（`grid-column: 2 / 4`）操作的都是"线"，不是"轨道序号"。

### 1.3 显式网格与隐式网格

- **显式网格**：你用 `grid-template-columns` / `grid-template-rows` 明确声明的轨道。
- **隐式网格**：当项目数量超出显式轨道、或项目被定位到声明范围之外时，浏览器**自动追加**的轨道。隐式轨道尺寸由 `grid-auto-rows` / `grid-auto-columns` 控制（默认 `auto`，即内容撑开）。

这是大量"为什么多出的一行列宽不对"问题的根源（见坑点 [12.3](#123-坑隐式轨道尺寸与预期不符)）。

---

## 二、容器基础属性

### 2.1 display

```css
.container { display: grid; }        /* 块级网格 */
.container { display: inline-grid; } /* 行内级网格：容器本身随文字流排布 */

/* 网格化容器作为直接子元素时，自身也成为父网格的一个项目 */
.container { display: grid; }
.container > .sub { display: contents; } /* .sub 自己不生成盒子，其子元素"冒泡"成 .container 的网格项目 */
```

要点：

1. `display: grid` 后，容器的**直接子元素全部自动成为网格项目**，它们的 `float`、`vertical-align`、`column-*` 失效。
2. 容器仍是一个普通盒子：可以有自己的 `width`、`margin`、`padding`，也可以被父级 Flex/Grid 定位。
3. `display: contents` 用于"跳过一层嵌套"，慎用——部分浏览器历史上会导致该元素的可访问性语义丢失。
4. 伪元素 `::before` / `::after` 若被生成，同样作为网格项目参与布局。

### 2.2 grid-template-columns / grid-template-rows（声明入口）

最常用的一次声明：

```css
.container {
  display: grid;
  grid-template-columns: 200px 1fr 1fr; /* 3 列：侧栏 200px + 两列等分剩余 */
  grid-template-rows: 60px auto 40px;   /* 3 行：顶栏 + 内容自适应 + 底栏 */
}
```

三种轨道取值全家福（详解见[第三章](#三轨道定义grid-template-与隐式轨道)）：

| 取值 | 含义 |
|---|---|
| `<length>` | 固定尺寸：`200px`、`10rem` |
| `<percentage>` | 相对容器内容盒的百分比 |
| `fr` | 剩余空间的等分份数（flexible，Grid 独有） |
| `auto` | 内容自适应；在 `grid-template` 上下文与 `minmax(auto, max-content)` 等价，在 `grid-auto-*` 上下文为 `minmax(min-content, max-content)` |
| `minmax(min, max)` | 最小-最大区间 |
| `repeat(n, ...)` | 重复声明的简写 |

### 2.3 grid-auto-columns / grid-auto-rows（隐式轨道）

```css
.container {
  grid-template-columns: repeat(3, 1fr); /* 显式只有 3 列 */
  grid-auto-rows: 120px;                 /* 第 4 行起，隐式行固定 120px */
  grid-auto-columns: 100px;              /* 被定位到第 4 列之后时，隐式列 100px */
}
```

### 2.4 grid-auto-flow（自动放置方向）

```css
.container { grid-auto-flow: row; }         /* 默认：按行填，满了换行 */
.container { grid-auto-flow: column; }      /* 按列填，满了换列（配合固定行数的"列优先"布局） */
.container { grid-auto-flow: row dense; }   /* 密集回填：允许后面的小项目插队填空缺 */
.container { grid-auto-flow: column dense; }
```

`dense` 解决"跨行项目造成空洞"的问题，但会**打乱视觉顺序与 DOM 顺序的一致性**，纯列表类内容不要开（见坑点 [12.7](#127-坑dense-破坏阅读顺序)）。

---

## 三、轨道定义：grid-template 与隐式轨道

### 3.1 fr 单位的真实语义

`fr` 分配的是**减去固定尺寸与 gap 之后的剩余空间**，因此 `1fr` 永远不为负：

```css
/* 容器 700px，gap 20px：剩余 = 700 - 200 - 20 = 480，两列各 240px */
.container {
  width: 700px;
  gap: 20px;
  grid-template-columns: 200px 1fr 1fr;
}

/* minmax(0, 1fr)：允许轨道收缩到内容最小宽度以下 */
.container { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
```

> 关键差异：`1fr` 实际是 `minmax(auto, 1fr)`，其最小值是 `auto`（≈ min-content），**内容过长会把轨道撑爆、把容器撑宽**。想让 `1fr` 真正可收缩（比如里面放 nowrap 长文本、代码块），必须显式写 `minmax(0, 1fr)`（见坑点 [12.1](#121-坑轨道尺寸写错导致-fr-失效)）。

### 3.2 repeat() 及其自动关键字

```css
.container { grid-template-columns: repeat(3, 1fr); }            /* 数字：固定重复 3 次 */
.container { grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); }
.container { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
```

`auto-fill` / `auto-fit` 是响应式核心，二者的区别见 [8.1](#81-auto-fill-与-auto-fit-的区别)。

禁止：`repeat()` 不能嵌套（`repeat(auto-fill, repeat(3, 1fr))` 无效）。

### 3.3 minmax() 的合法组合

| 写法 | 合法性 | 说明 |
|---|---|---|
| `minmax(100px, 1fr)` | 合法 | 最常用：最小 100px，最大吃掉剩余 |
| `minmax(auto, 300px)` | 合法 | 内容驱动，但不超 300px |
| `minmax(min-content, max-content)` | 合法 | 内容夹逼区间 |
| `minmax(1fr, 2fr)` | **非法** | `fr` 只能作最大值，且此时最小值必须为 `auto` |
| `minmax(auto, auto)` | 合法 | 等价于 `auto` |
| `minmax(100px, 50px)` | 合法但退化 | min > max 时按 min 处理，max 被忽略 |

### 3.4 内容关键字：min-content / max-content

```css
.container {
  grid-template-columns: min-content 1fr max-content;
  /* 第1列：收缩到极限（最宽单词/不可断内容宽度）*/
  /* 第3列：完全不换行的自然宽度 */
}
```

`grid-template-rows: masonry` 是 Grid Level 3 草案的瀑布流关键字，**主流浏览器尚未正式支持**（Chrome 需实验开关），生产环境请用 CSS Columns 或 JS 方案替代，不要依赖。

### 3.5 auto 在两个上下文中的不同含义

| 所在位置 | auto 的等价展开 |
|---|---|
| `grid-template-columns/rows` | `minmax(auto, max-content)` —— 先用剩余空间填充，能长则长 |
| `grid-auto-columns/rows` | `minmax(min-content, max-content)` —— 纯内容尺寸，不参与剩余分配 |

另一个易混点：`auto` 会**吃掉等分剩余的显式行宽**（当所有行都是 `auto` 且容器有固定高度时），而 `fr` 不参与这种均分兜底。

### 3.6 grid-template 简写（含区域语法）

```css
/* 单行声明轨道（较少用） */
.container { grid-template: 60px / 200px 1fr; } /* 行模板 / 列模板 */

/* 命名区域版：每个方括号 [线名] 夹一个行模板 */
.container {
  grid-template:
    [row1-start] "header header header" 60px [row1-end]
    [row2-start] "sidebar main main"    auto [row2-end]
    [row3-start] "footer footer footer" 40px [row3-end]
    / 200px 1fr 1fr;
}
```

区域语法的行高写在每行字符串后面；`none` 可用作某维度的显式清空：`grid-template: none / 1fr 1fr`。

---

## 四、项目定位：线、区域与命名

### 4.1 线定位：grid-column / grid-row

```css
.item { grid-column-start: 2; grid-column-end: 4; } /* 占列线 2~4，即第 2、3 列 */
.item { grid-column: 2 / 4; }                       /* 上式简写 */
.item { grid-column: 2; }                           /* 只定起点，自动跨 1 */
.item { grid-column: span 2; }                      /* 当前位置自动跨 2 列 */
.item { grid-column: 1 / -1; }                      /* 从第 1 条线到最后一条线 = 整行 */
.item { grid-row: 2 / span 3; }                     /* 从行线 2 起跨 3 行 */
```

规则：

1. 线号从 **1** 开始；负数从容器尾部倒计（`-1` = 最后一条线）。
2. `a / b` 要求起点线号小于终点，写反会被浏览器**自动交换**。
3. `grid-area: 1 / 2 / 3 / 4` 是 `grid-row-start / grid-column-start / grid-row-end / grid-column-end` 的四值简写（**行先行**，容易记反）。
4. 只写 start 不写 end：跨度默认 1。只写 `span n`：起点由自动放置决定。

### 4.2 区域定位：grid-template-areas + grid-area

```css
.container {
  display: grid;
  grid-template-columns: 200px 1fr 1fr;
  grid-template-rows: 60px 1fr 40px;
  grid-template-areas:
    "header header header"
    "sidebar main   main"
    "footer footer footer";
}
.header  { grid-area: header; }
.sidebar { grid-area: sidebar; }
.main    { grid-area: main; }
.footer  { grid-area: footer; }
```

区域语法约束：

- 每个字符串的**列数必须一致**，否则整条声明无效。
- 一个区域必须是**矩形**：同名单元格不能在对角位置，否则整个模板被丢弃。
- `.`（一个或多个点）表示**空格**：`"header header ."`, 末尾列留空。
- 区域名会自动成为**命名线**：`grid-template-areas` 里叫 `header` 的区域产生 `header-start` / `header-end` 线，可供线定位引用：`.a { grid-column: header-start / main-end; }`。
- 项目用 `grid-area: 名字` 放置；未定义的名字按线名/`span` 解析，都不匹配则退化为 `grid-area: auto`（自动放置）。

### 4.3 命名线

```css
.container {
  grid-template-columns: [content-start sidebar-start] 200px [sidebar-end content-end] 1fr [content-end];
}
.item { grid-column: content-start / content-end; }
/* 同名多条线时，start/end 后缀自动配对：第 2 个 -start 配第 2 个 -end */
```

多次重复声明时可带索引线名：`repeat(3, [col-start] 1fr [col-end])` 产生 `col-start 1`、`col-start 2`、`col-start 3`。

### 4.4 自动放置与顺序控制

```css
.container { grid-auto-flow: row; }   /* 默认：按 DOM 顺序逐个找空位 */
.item { order: 2; }                   /* 参与自动放置排序，默认 0，可为负 */
```

自动放置算法（简化）：已定位置的项目先摆放 → 未定位的项目按 `order`、再按 DOM 顺序，沿 `grid-auto-flow` 方向找第一个能容纳它且不与"已锁定项目"重叠的空位。`dense` 会让后来的项目有权插队回填。

---

## 五、对齐与分布

Grid 的对齐分三层，**每层的"主轴/交叉轴"含义与 Flexbox 不同**——Grid 中统一叫**行轴（block 方向，垂直）与列轴（inline 方向，水平）**：

| 层级 | 属性 | 作用范围 |
|---|---|---|
| 容器级（管所有项目在自己格内的表现） | `justify-items` / `align-items` / `place-items` | 项目未覆盖时生效 |
| 容器级（管轨道整体在容器里的分布） | `justify-content` / `align-content` / `place-content` | 仅当**轨道总尺寸 < 容器尺寸**时可见效果 |
| 项目级（单个覆盖） | `justify-self` / `align-self` / `place-self` | 优先级最高 |

### 5.1 格内对齐：justify-items / align-items / place-items

```css
.container {
  justify-items: start | end | center | stretch; /* 列轴（水平）默认 stretch */
  align-items: start | end | center | stretch;   /* 行轴（垂直）默认 stretch */
  place-items: center;          /* = align-items: center; justify-items: center;（先纵后横）*/
  place-items: start stretch;   /* 两值：第一个 align，第二个 justify */
}
```

`stretch` 生效前提：项目在该轴**没有固定尺寸**（写死 `width` 后 stretch 失效，见坑点 [12.5](#125-坑stretch-被固定尺寸抵消)）。

### 5.2 格内单点覆盖：justify-self / align-self / place-self

```css
.item { place-self: center end; } /* align-self: center; justify-self: end; */
```

Flexbox 没有 `align-self` 对应的 justify 版本？Grid 三轴齐全，且项目级覆盖容器级。

### 5.3 轨道整体分布：justify-content / align-content

```css
.container {
  justify-content: start | end | center | stretch | space-around | space-between | space-evenly;
  align-content: start | center | end | stretch | space-between | space-around | space-evenly | safe center | unsafe center;
}
```

- 触发条件：显式轨道（含 `auto` 行）小于容器。若用了 `1fr` 轨道撑满，则永远看不到效果。
- `space-*` 系列**只作用于轨道之间的空隙，不会作用于项目**（常见误解，见坑点 [12.4](#124-坑justify-content-对-fr-轨道无效果)）。
- `stretch` 仅在有 `auto` 轨道时可拉伸轨道。
- `safe center`：居中溢出时退回 `start`，避免内容被裁切不可达；`unsafe center`（默认行为）居中后可能溢出左/上边无法滚动到。

### 5.4 边缘推挤技巧：margin: auto

```css
.item { margin-left: auto; }          /* 把自己推到格子右边 */
.item { margin: auto; }               /* 格内绝对居中，且优先于 justify/align-items */
```

`margin: auto` 在 Grid 中同样参与剩余空间分配，且**优先级高于一切对齐属性**——这是把单个项目"钉"在格内某个角落的最稳手段。

---

## 六、间距：gap

```css
.container {
  gap: 20px;             /* 行距 = 列距 */
  gap: 10px 20px;        /* 行间距 10px，列间距 20px（先纵后横）*/
  row-gap: 10px;
  column-gap: 20px;
  gap: 1em;              /* 接受任何 <length> 与百分比；百分比相对容器内边距盒 */
}
```

要点：

1. `gap` 只出现在**轨道之间**，容器最外圈没有 gap——替代了老写法的"子元素 margin + 负边距抵消"。
2. 适用于 Grid、Flexbox（自 Chrome 84+ 全面支持 Flex gap）、多列布局。
3. `gap` 计入 `fr` 的剩余空间计算：三列两 gap，`1fr` 分的是"总宽 − 2×gap"后的份额。
4. 单元格内部项目互相重叠？`gap` 不解决项目跨格堆叠，那是区域设计问题。

---

## 七、层叠顺序与网格溢出

### 7.1 网格项的 z-index

网格项目**即使 position: static 也可以参与层叠**——设置了 `z-index`（非 `auto`）即生效：

```css
.a { z-index: 1; }               /* 无需 position 也能压住同级的无 z-index 项 */
.b { position: relative; }       /* 定位元素默认画在静态层之上（z-index: auto 时） */
```

堆叠层次（由低到高）：背景/边框 → 负 z-index 子 → 静态块盒子 → float → inline → 定位层（z-index: auto / 0）→ 正 z-index。同层级按 DOM 顺序后者盖前者。

### 7.2 项目超出网格

```css
.item { grid-column: 5 / 7; } /* 显式模板只 4 列时，自动创建第 5、6 条隐式列 */
.container { overflow: auto; } /* 内容大于容器时按普通盒子规则滚动 */
```

隐式轨道默认 `auto` 尺寸由内容决定，可用 `grid-auto-rows/columns` 统一接管。

---

## 八、响应式网格模式

### 8.1 auto-fill 与 auto-fit 的区别

两者都按"容器宽度能放几个放几个"计算轨道数，区别在**空轨道的处理**：

```css
/* 容器 800px，minmax(180px, 1fr)：可放 4 列，当前只有 2 个项目 */
.a { grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); }
/* 结果：仍生成 4 条 1fr 轨道，2 个项目占前 2 列，右侧留 2 条空轨道 */

.b { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
/* 结果：空轨道被折叠为 0 宽，2 个项目各得 1/2 容器宽 */
```

一句话：**auto-fill 保底列数（内容少也保持网格），auto-fit 让内容铺满**。卡片区通常用 `auto-fit`，表格型/日历型布局用 `auto-fill`。

### 8.2 三种典型响应式策略

```css
/* 策略1：内容驱动的"自适应列数"，无需媒体查询（最常用）*/
.grid { grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); }
/* min(100%, 280px)：窄于 280px 的设备上最小值取容器全宽，防止横向溢出 */

/* 策略2：媒体查询断点切模板 */
.grid { grid-template-columns: 1fr; }
@media (min-width: 768px)  { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1200px) { .grid { grid-template-columns: repeat(4, 1fr); } }

/* 策略3：区域重排——移动端堆叠，桌面侧栏 */
.layout { grid-template-areas: "main" "aside"; }
@media (min-width: 900px) {
  .layout {
    grid-template-columns: 1fr 300px;
    grid-template-areas: "main aside";
  }
}
```

### 8.3 动态行高

```css
/* 卡片等高：不写死行高，隐式行用 minmax 保底 */
.grid { grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); grid-auto-rows: minmax(160px, auto); }
/* 内容超过 160px 时行自然长高，不足时保持 160px 底线 */
```

---

## 九、Grid 与 Flexbox 对比与选型

### 9.1 维度模型差异

| 维度 | Flexbox | Grid |
|---|---|---|
| 轴向 | 一维（一行**或**一列） | 二维（行**和**列同时） |
| 尺寸决定者 | 内容驱动：项目决定主轴分布 | 容器驱动：模板决定网格，内容放进去 |
| 定位能力 | 只有顺序（order）与对齐 | 精确到线/区域坐标 |
| 间隙 | `gap`（支持较晚） | `gap`（原生） |
| 典型心智 | "把这一排东西排好" | "先画格子再填内容" |

### 9.2 选型速判

- **用 Flexbox**：导航栏、按钮组、一行内"图标+文字"、垂直居中单元素、内容长度未知且需自然伸缩。
- **用 Grid**：页面骨架、卡片墙、表单标签-控件对齐、仪表盘、任何"列与列之间需要上下对齐"的场景。
- **两者共存**：Grid 管页面大骨架，每个格子里的局部小排列交给 Flexbox——这是最普遍的实战组合，不是非此即彼。

判据一句话：**需要"多行/多列之间对齐"用 Grid；只在一条轴上排队用 Flex。**

---

## 十、典型布局实战

### 10.1 圣杯布局（页头 + 侧栏 + 内容 + 页脚）

```css
.holy-grail {
  display: grid;
  grid-template-columns: 220px 1fr 280px;
  grid-template-rows: 64px 1fr 48px;
  grid-template-areas:
    "header  header  header"
    "nav     main    aside"
    "footer  footer  footer";
  min-height: 100vh;
}
.holy-grail > *            { min-width: 0; } /* 防内容撑爆，见坑点 12.1 */
.header { grid-area: header; }
.nav    { grid-area: nav; }
.main   { grid-area: main; }
.aside  { grid-area: aside; }
.footer { grid-area: footer; }
```

### 10.2 响应式卡片墙

```css
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
  gap: 16px;
}
.card { display: flex; flex-direction: column; } /* 格子内部交给 Flex */
.card .body { flex: 1; }                          /* 卡片等高且底部按钮贴底 */
```

### 10.3 完美居中方块

```css
.center { display: grid; place-items: center; min-height: 100vh; }
```

一行 `place-items: center` 即完成水平+垂直居中，比 Flex 版少两个属性。

### 10.4 表面对齐的表单（标签-控件两列）

```css
.form {
  display: grid;
  grid-template-columns: max-content 1fr; /* 左列按最长标签对齐，右列吃掉剩余 */
  gap: 12px 16px;
  align-items: center;                    /* 单行控件垂直居中 */
}
.form label { text-align: right; }
```

### 10.5 固定侧栏 + 自适应内容（后台管理骨架）

```css
.admin {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr); /* minmax(0, 1fr)：内容再宽也不撑破右侧 */
  grid-template-rows: 56px minmax(0, 1fr);
  grid-template-areas:
    "side topbar"
    "side content";
  height: 100vh;
}
.admin .content { grid-area: content; overflow: auto; } /* 内容区独立滚动 */
```

### 10.6 跨行Feature卡片（dense 回填）

```css
.feed {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  grid-auto-rows: 180px;
  gap: 12px;
  grid-auto-flow: row dense; /* 大卡占 2x2 造成空洞时，小卡自动回填 */
}
.feed .featured { grid-column: span 2; grid-row: span 2; }
```

### 10.7 叠放区（Hero 图上浮标题）

```css
.hero { display: grid; }
.hero > * { grid-area: 1 / 1; } /* 所有子元素塞进同一个格子 = 天然叠放层 */
.hero .title { align-self: end; padding: 24px; color: #fff; }
```

`grid-area: 1/1` 全占位是 CSS 叠放布局的最简实现，替代 `position: absolute` 方案。

---

## 十一、子网格 subgrid

### 11.1 解决的问题

嵌套网格的列要对齐外层网格时，传统做法是把所有层级压平（破坏 DOM 语义）。`subgrid` 允许**子元素复用父网格的轨道定义**，同时保留 DOM 嵌套结构。

```html
<div class="list">            <!-- 外层网格：3 列 -->
  <div class="row">           <!-- 跨 3 列，内部声明 subgrid -->
    <span>标题</span><span>状态</span><span>操作</span>
  </div>
</div>
```

```css
.list {
  display: grid;
  grid-template-columns: 1fr 120px 100px;
  gap: 8px;
}
.row {
  display: grid;
  grid-column: 1 / -1; /* 必须明确占据父轨道范围 */
  grid-template-columns: subgrid;
  gap: inherit;        /* subgrid 自动继承父 gap；此处亦可显式处理 */
}
```

### 11.2 行为与限制

1. `subgrid` 不是新网格——它**继承所跨范围内的父轨道线和尺寸**，改轨道须改父模板。
2. 子网格的 `gap` 默认跟随父网格（与父轨道对齐的物理要求）。
3. 兼容性：Chrome 117+（2023.9）、Safari 16+、Firefox 71+；**不支持时整条 `grid-template-columns: subgrid` 被忽略**，须备好固定列宽的降级写法。
4. 行、列各自独立声明：`grid-template-rows: subgrid;` 只做行对齐。

---

## 十二、常见坑汇总

### 12.1 坑：轨道尺寸写错导致 fr 失效

**现象**：`1fr` 的列里有长英文单词、`white-space: nowrap` 文本、宽表格或代码块时，列被撑爆，整个页面出现横向滚动条。
**原因**：`1fr` = `minmax(auto, 1fr)`，最小值是 min-content，不可小于内容最小宽。
**正解**：`minmax(0, 1fr)` 解除收缩下限；或给内容元素加 `min-width: 0` / `overflow: hidden` / `word-break: break-all`。这是 Grid 布局第一高频坑。

### 12.2 坑：只有直接子元素参与网格

**现象**：中间多包一层 `<div>` 后，里面的元素不再进格子。
**原因**：Grid 是严格的两层模型，孙元素由父级（已是网格项目的那个盒子）内部布局决定。
**正解**：DOM 压平；或对包装层用 `display: contents`（注意可访问性历史缺陷）；或给包装层自己声明 `display: grid` 并用 `subgrid` 对齐。

### 12.3 坑：隐式轨道尺寸与预期不符

**现象**：用 `grid-template-columns` 定义了列，行完全交给自动流，结果"多出来的行高矮不一"。
**原因**：隐式行由 `grid-auto-rows` 控制，默认 `auto` 按内容各自撑开；`grid-template-rows` 对隐式行**无效**。
**正解**：`grid-auto-rows: minmax(120px, auto)` 统一兜底。反过来用 `grid-auto-flow: column` 时，溢出的列交给 `grid-auto-columns` 管。

### 12.4 坑：justify-content 对 fr 轨道无效果

**现象**：写了 `justify-content: space-between` 毫无反应。
**原因**：轨道用了 `1fr` 等弹性单位，总宽已撑满容器，没有"剩余空间"可分布。
**正解**：`space-*` 系列只在轨道为**固定尺寸**且总宽 < 容器时生效；想拉开 fr 列的间距应该用 `gap`，想靠边就加空轨道（`grid-template-columns: 1fr auto auto 1fr`）。

### 12.5 坑：stretch 被固定尺寸抵消

**现象**：项目设了 `width` / `height` 后不再填满格子，或内容超长时把格子撑得比轨道声明还大。
**原因**：`justify-items/align-items: stretch` 仅对未定尺寸轴生效；另外 `min-height: 100px` 写在**项目**上会把所在行轨道顶到至少 100px（项目最小尺寸参与轨道自动算法）。
**正解**：区分"容器控格"与"项目撑格"两个方向——要格子多大写轨道，要项目在格内行为用 `self` 属性；限制项目对轨道的影响用轨道侧 `minmax(0, ...)`。

### 12.6 坑：区域模板字符串列数不齐 / 非矩形

**现象**：`grid-template-areas` 整个属性静默失效，布局塌回默认流。
**原因**：任一行字符串列数不同，或同名区域不呈矩形（如 L 形），规范判定整个模板无效，**无任何报错**。
**正解**：DevTools 的 Grid 检查器（元素面板里点 `grid` 徽章）可视化确认轨道；每个区域名出现次数与位置必须构成矩形，留空一律用 `.`。

### 12.7 坑：dense 破坏阅读顺序

**现象**：开了 `grid-auto-flow: dense` 后，键盘 Tab 顺序与视觉顺序不一致，屏幕阅读器用户困惑。
**原因**：dense 允许后续项目插队到前面空洞，视觉提前、DOM 滞后。
**正解**：内容顺序有业务含义（表单、步骤列表、文章）禁用 dense；仅用于图片墙等顺序无关场景。

### 12.8 坑：fr 与百分比/px 混用时 gap 的重复计算

**现象**：`grid-template-columns: 50% 50%` + `gap: 20px` 溢出容器。
**原因**：百分比相对容器全宽计算，不预先扣 gap；两列 50% + 20px gap = 100% + 20px。
**正解**：混用尽量交给 `fr`（`1fr 1fr` + gap 永远不溢出），或用 `calc(50% - 10px)` 手工扣除。

### 12.9 坑：margin: auto 优先于对齐属性

**现象**：设了 `justify-items: center`，某几个项目却死活贴右。
**原因**：项目自带 `margin-left: auto`（或继承了组件库样式中的 auto margin），auto 边距吃掉全部剩余空间，对齐属性无空间可排。
**正解**：检查计算样式里的 margin；二者选其一，不要叠加使用。

### 12.10 坑：旧版浏览器前缀与语法不可移植

**现象**：需要兼容旧 Edge 15 / 旧 Safari 的政企环境时，Grid 部分属性失效。
**原因**：IE 10/11 与 Edge ≤15 使用 `-ms-` 旧规范语法，概念模型不同（用 `-ms-grid-columns` 且不支持 fr / areas / 跨多层 span）。
**正解**：现代浏览器无需任何前缀。真要兼容 IE：用 `@supports (display: grid)` 做渐进增强，IE 落回 float/inline-block 布局，不要指望逐条翻译语法。

---

## 十三、属性速查表

### 13.1 容器属性

| 属性 | 常用值 | 一句话 |
|---|---|---|
| `display` | `grid` / `inline-grid` / `subgrid` | 启用网格 |
| `grid-template-columns` / `-rows` | `repeat()`、`fr`、`minmax()`、`auto`、线名、命名线 | 显式轨道 |
| `grid-template-areas` | 字符串矩阵 | 命名区域 |
| `grid-template` | 区域矩阵或 `行 / 列` | 三合一简写 |
| `grid-auto-columns` / `-rows` | 单个轨道尺寸值 | 隐式轨道 |
| `grid-auto-flow` | `row` / `column` / `dense` 组合 | 自动放置方向与回填 |
| `gap` / `row-gap` / `column-gap` | 长度 / 百分比 | 轨道间距 |
| `justify-items` / `align-items` / `place-items` | `start/end/center/stretch` | 格内对齐（全体） |
| `justify-content` / `align-content` / `place-content` | 上述 + `space-*` | 轨道整体分布（需有剩余空间） |

### 13.2 项目属性

| 属性 | 常用值 | 一句话 |
|---|---|---|
| `grid-column` / `grid-row` | `线号` / `线名` / `span n` / `a / b` / `auto` | 线定位 |
| `grid-area` | 区域名 或 `行起/列起/行止/列止` | 区域定位 / 四值简写 |
| `justify-self` / `align-self` / `place-self` | `start/end/center/stretch` | 格内对齐（单个） |
| `order` | 整数 | 自动放置次序 |
| `z-index` | 整数 | 网格项无需定位即可层叠 |

### 13.3 高频组合配方

| 需求 | 配方 |
|---|---|
| 等分 N 列 | `repeat(N, minmax(0, 1fr))` |
| 自适应列数卡片墙 | `repeat(auto-fill, minmax(min(100%, 280px), 1fr))` |
| 内容少也铺满 | 同上但 `auto-fit` |
| 整行通栏 | `grid-column: 1 / -1` |
| 完美居中 | `display: grid; place-items: center` |
| 叠放层 | 所有子项 `grid-area: 1 / 1` |
| 固定侧栏+自适应 | `grid-template-columns: 240px minmax(0, 1fr)` |
| 等高行 | `grid-auto-rows: 1fr`（显式行均分）或 `minmax(160px, auto)` |
| 表单两列 | `grid-template-columns: max-content minmax(0, 1fr)` |

> 所有配方的浏览器行为以现代 Chromium / Firefox / WebKit 为准；生产使用前建议用浏览器 DevTools 的 Grid 检查器核对轨道渲染结果。
