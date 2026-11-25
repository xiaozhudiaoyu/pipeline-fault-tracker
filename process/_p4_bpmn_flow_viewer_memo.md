# 第四阶段候选：故障处理流程图（BPMN 只读视图）

> 记录时间：2026-11-02（第三阶段需求分析会话）
> 决策状态：**方案已选定，未实施**。实施排期在第三阶段主线（认证/权限/时间线）落地之后。

## 一、需求来源

- 用户希望引入 `E:\git\TPM-project-fe` 的流程图查看效果（技术文件审查页面的"流程图"弹窗：
  未完成的 BPMN 流程图，按办理进度给节点着色，图例为 未完成/进行中/已完成/退回）。
- 对应第三阶段需求文档（用户权限与处理闭环）的"报修—指派—处理—确认/退回"闭环，
  在详情页以流程图形式直观展示当前流转位置。需求四.1 只强制要求时间线列表，本图为增强项。

## 二、参照物实证（已核对 TPM-project-fe 源码）

截图弹窗的完整链路：

| 层 | 位置 | 说明 |
|---|---|---|
| 弹窗封装 | `src/views/procedure/document/component/flowBpmn.vue` | BasicModal + `<BpmnViewer :businessKey>` |
| 查看器组件 | `src/components/BpmnViewer/src/index.vue`（+ `index.less`、`index.ts`） | 基于 `bpmn-js/lib/Viewer` 的**只读**查看器 |
| 导航模块 | `diagram-js/lib/navigation/{movecanvas,zoomscroll}` | 拖拽平移 + 按钮缩放（禁用滚轮缩放） |
| 着色逻辑 | `fillColor/bpmnNodeList`：`canvas.addMarker(id, 'highlight'/'highlight-todo'/'highlight-back')` | 标记类样式在 `index.less` 定义 |
| 悬浮详情 | `overlays.add(...)`：已审/待审人员、节点状态、起止时间 | 数据源为活动历史 |
| 类型声明 | `types/bpmn/{index,moddle,panel}.d.ts` | `import type { Canvas, ModdleElement } from 'bpmn'` 依赖此目录 |
| 数据接口 | `getHistoryList(businessKey)` → `{ xml, taskList, historyList }` | **后端是 Flowable 工作流引擎**，xml 为流程定义（含 BPMNDiagram 坐标） |

依赖版本（TPM 的 package.json，锁精确版本）：`bpmn-js@17.5.0`、`diagram-js@14.6.0`；
另装有 `bpmn-js-token-simulation@0.34.1`、`diagram-js-minimap@4.1.0`，**查看器未使用，不移植**。
工具栏图例/按钮用的是 **ant-design-vue**（Tag/Tooltip/Space/a-button），本项目为 Element Plus。

## 三、选定方案：静态 BPMN 图 + 时间线着色（不引入工作流引擎）

**结论**：只移植"渲染与着色"，不搬"引擎与数据链路"。

- 后端**不**部署 Flowable（Java 服务，违背第三阶段需求"继续用原技术栈"约束，已被否决）。
- 流程定义以**一份静态 BPMN XML** 的形式存于前端（`frontend/src/assets/fault-flow.bpmn.xml`，
  用 bpmn.io 编辑器画一次即可，DI 坐标必须随 XML 携带，程序无法自动生成布局）。
- 节点状态数据来源 = 第三阶段的时间线表（`action` 枚举：登记/指派/开始处理/追加进展/
  提交结果/退回处理/确认完成），前端把最新状态与退回记录映射为高亮，**不新增后端接口**
  （若时间线接口返回结构不够用，届时按 M 档另行评估）。

### 固定流程图的节点映射（4 态状态机 → BPMN 元素）

| BPMN 元素 | 业务含义 | 着色规则（映射自时间线） |
|---|---|---|
| StartEvent 开始 | 报修发起 | 有"登记"记录 → 已完成 |
| UserTask 待指派 | 管理员指派/改派 | 有"指派"记录 → 已完成；当前 status=pending → 进行中 |
| UserTask 处理中 | 负责人开始处理、追加进展、提交结果 | 同上按 status 与记录推断 |
| UserTask 待确认 | 创建人确认或退回 | status=awaiting_confirmation → 进行中 |
| UserTask 已完成（或 EndEvent） | 终态 | status=done → 已完成，连线全绿 |
| 退回连线（虚线回 处理中） | 退回处理 | 存在"退回"记录 → 该节点与连线标红（highlight-back 样式） |
| 改派连线（回 待指派） | 管理员改派 | 存在"改派"记录 → 叠加标记 |

> 注：节点划分与连线走向为实施草案，属需求四"字段、表结构及接口由开发者设计"范畴，
> 实施前需用户过目一版静态图。

## 四、移植改造清单（实施时执行）

1. **依赖**（按规则 2.5，实施前经用户确认后安装，并同步 `DEPENDENCIES.md`）：
   - `bpmn-js@17.5.0`、`diagram-js@14.6.0`（与 TPM 同版本，已验证可用；兼容性优先 3.3）。
   - 安装路线按本项目既有锁文件策略（npm + package-lock.json）。
2. **新增文件**：
   - `frontend/src/components/FaultFlowViewer/index.vue` —— 从 BpmnViewer 移植：
     保留 init/createDiagram/fitViewport/zoomViewport/addEventBusListener(overlays) 骨架；
     `fillColor/bpmnNodeList` 重写为"时间线 → marker"的简化映射（TPM 版按 taskList
     顺序递归着色且含 `findLast`（ES2023，需核对本项目 tsconfig target/lib），本项目按
     状态机 4 态判断即可，逻辑大幅简化）。
   - `frontend/src/components/FaultFlowViewer/flow-styles.css` —— 移植 `index.less` 中
     highlight/highlight-todo/highlight-back 及 overlays 弹层样式（less → 原生 css，
     本项目无 less 依赖，不为此新增）。
   - `frontend/src/assets/fault-flow.bpmn.xml` —— 静态流程定义（bpmn.io 绘制）。
   - `frontend/src/types/bpmn.d.ts` —— 从 TPM `types/bpmn/index.d.ts` 摘取查看器所需
     最小类型（Canvas、ModdleElement 等），不整目录照搬。
3. **UI 适配**（已定：改写为 Element Plus）：图例 4 个 Tag → `<el-tag type=...>`；
   缩放/居中按钮 → `<el-button>` + `<el-tooltip>`；图标沿用 TPM 的 material-symbols/ooui
   在线图标集或改本项目既有图标（实施时二选一，倾向后者，避免新增外部图标依赖）。
4. **接入点**：`FaultDetailView.vue` 增加"查看流程图"按钮 → el-dialog 内挂载
   FaultFlowViewer，传 `fault` + 时间线列表。**不得影响**需求四.3 的动作按钮区。
5. **测试**（分层测试策略）：组件级至少手工冒烟——四种状态各造一条故障，核对着色与
   退回红色标记；bpmn-js 渲染类逻辑不做单测（成本高、收益低），列入用户验证清单。

## 五、风险与注意事项

- bpmn-js 体积较大（gzip 后约 100KB+），仅在详情页弹窗**异步组件懒加载**，不进主 bundle。
- 静态 XML 与代码状态机是**两份定义**，第四阶段若改状态机必须同步改 XML —— 在
  XML 文件头部注释里写明此耦合。
- 历史故障（无创建人/未关联账号，需求六.2）在图上按"待指派"起点着色，overlays 显示
  "历史数据"，不编造办理人。
- 本备忘中的节点映射表是推测草案，非 TPM 现成能力复用，验收标准需在实施时与用户确认。
