# 工作流技术学习路线（状态机 → BPMN 引擎 → 任务编排 → 协调框架）

> 记录时间：2026-11-02
> 性质：**学习类备忘**，非交付计划。主线任务仍是第三阶段需求（用户权限与处理闭环），
> 本路线的所有练习一律不在 tracker 交付分支上进行（见第〇节纪律）。
> 来源：第三阶段需求分析会话中，由"引入 TPM-project-fe 的 bpmn-js 流程图插件"一路追问
> （Python 有无对应物 → 有无适用的 Python 工作流引擎）展开出的知识线。

## 〇、总纪律（先读）

1. **交付优先**：第三阶段一周周期内，本路线只允许"读概念"类条目（阶段 4 及各行尾标注
   "阅读"的），动手类练习排在主线交付之后。
2. **练习隔离**：涉及 tracker 代码的练习（阶段 1、3）在独立分支（`learn/xxx`）或
   git worktree 里做，练习代码不合入 main；独立项目练习（阶段 2）放
   `E:\python学习\` 之类的新目录，不进本仓库。
3. **依赖规则不破**：任何练习新装的依赖（transitions、SpiffWorkflow、celery…），
   若最终落在 tracker 环境里，按用户规则 2.5 走确认 + 台账；用完即卸载，不静默残留。
4. **沉淀出口**：每个阶段学完，把稳定认知（非流水账）落到 `guide_file/` 新建一篇
   手册（沿用该目录"实测/待验证"标注风格），这是本路线的文档交付物。

## 一、知识地图（四层，由轻到重）

| 层 | 解决什么问题 | 代表技术 | 核心概念 |
|---|---|---|---|
| ① 状态机 | 单个对象的状态流转规则 | Python `transitions`、TS `xstate` | 状态/事件/转移/守卫(Guard)/副作用回调 |
| ② BPMN 流程引擎 | 人机协同的业务流程（等人、催办、分叉合并） | **SpiffWorkflow**（纯 Python）、Flowable/Camunda（Java）、Camunda 系建模库 camunda-bpmn-mypy | Token 令牌流转、User Task 挂起/认领、网关（排他/并行/包容）、流程实例持久化、历史审计 |
| ③ 任务编排 | 机器作业的调度与依赖（定时、重试、补数） | Celery、APScheduler、Airflow、Prefect/Dagster | DAG、broker/backend、worker、幂等、重试退避 |
| ④ 微服务协调 | 跨服务的长事务、可恢复执行 | Temporal/Cadence、AWS Step Functions | 持久化函数(Workflow as Code)、Orchestration vs Choreography、Saga |

**易混认知（本路线最重要的两条分界线）**：
- ②与③都叫 workflow：②是"业务流程等人办"（BPMN，图上有令牌在走），③是"计算作业按序跑"（DAG，无人在环）。
- ①与②的边界：状态机描述"一个对象此刻在哪"，引擎描述"一张图上令牌走到了哪、在哪个
  人工节点停下"。流程固定且单对象时，状态机足够——这正是 tracker 现状；流程要动态
  定义、多任务并行、超时催办时，才需要引擎。

## 二、阶段 1：transitions 改造 tracker 状态机（1 天，练①）

- **目标**：把 crud.py 里手写的状态流转矩阵（pending/processing/done + 409 规则）
  迁移为 `Machine` 声明式定义，理解守卫与回调。
- **练习内容**：
  1. 读 transitions 官方 Quick Start，用其 Tutorial 例子写一个 50 行的独立 demo（门/锁）。
  2. 在 `learn/transitions` 分支上，把 `transition_fault` 的合法性判断改为 Machine：
     状态 = FaultStatus，事件 = 开始处理/提交结果/确认/退回（按第三阶段 4 态设计），
     守卫 = 角色+归属校验（对应需求二.6），回调 = 写时间线（对应需求四.2 同事务要求）。
  3. 对比自研 if/else 版：哪些代码变少了？哪些约束（如"状态与时间线要么同成要么同败"）
     反而更难表达？得出结论并写进 guide_file。
- **验收标准**：既有测试 `test_crud.py` / `test_api_faults.py` 中与流转相关的用例全绿；
  能口头讲出"事件-守卫-回调"三件套分别对应需求文档里的哪条要求。
- **注意**：本阶段是"用第三阶段需求练手"的副产品，若与主线排期冲突可整体跳过，
  直接学阶段 2 时再回头补概念。

## 三、阶段 2：SpiffWorkflow 独立练习项目（3~5 天，练②，本路线核心）

- **目标**：完整体验一遍"画 BPMN → Python 执行 → 前端渲染着色"的全链路，
  对照理解 TPM-project-fe 的 Flowable 架构为什么那样设计。
- **前置调研结论（会话已核实）**：SpiffWorkflow 纯 Python、支持 User Task；
  官方生态有 Spiff Arena（bpmn.io 系在线设计器，产物为标准 BPMN XML）与
  `bpmn-js-spiffworkflow`（bpmn-js 扩展）。**待验证**：SpiffWorkflow 对 SQLite 的
  持久化支持方式（它自带 TaskSerializer / 可接 SQLAlchemy），动手第一步先验证这点。
- **练习内容**（新目录建项目，建议直接用 fastapi-vue-scaffold 技能起骨架）：
  1. 用 Spiff Arena（或 demo.bpmn.io）画"报修 → 指派 → 处理 → 提交 → 确认/退回"流程，
     User Task 指定 assignee，退回用排他网关。
  2. 后端 FastAPI 集成 SpiffWorkflow：启动流程实例、列任务、认领/完成 User Task，
     流程实例状态存 SQLite。
  3. 前端把 `_p4_bpmn_flow_viewer_memo.md` 里的 FaultFlowViewer 方案落地：bpmn-js
     Viewer 渲染引擎返回的 XML + 按任务历史 `canvas.addMarker` 着色 + overlays 悬浮详情。
  4. 记录：引擎替你做了什么（挂起等待、令牌推进、历史审计），你还写了什么（权限、
     业务字段）——这条边界就是"要不要上引擎"的判据。
- **验收标准**：浏览器里走完一条故障流程，图上绿/橙/红着色随刷新变化；能讲清
  Token 在排他网关处的行为；产出一篇 `guide_file/SPIFFWORKFLOW.md`。

## 四、阶段 3：Celery 异步导出（2~3 天，练③）

- **目标**：理解 broker/worker/backend 三件套与幂等、重试，区别于业务流程。
- **练习内容**：在 `learn/celery` 分支上，把 tracker 的 `GET /api/faults/export`
  改造成：POST 提交导出任务 → 返回 task_id → 轮询状态 → 完成后下载。本地用
  Redis 或 `CELERY_BROKER=memory://`（仅学习用）跑通。
- **验收标准**：模拟 1 万行导出不阻塞请求线程；杀掉 worker 任务能重派；讲得出
  "为什么导出属于作业流而不是 BPMN 流程"。产出 `guide_file/CELERY.md`（含与
  FastAPI 官方 BackgroundTasks 的选型对比——小需求其实 BackgroundTasks 就够，
  这层取舍也是学习点）。

## 五、阶段 4：Temporal 概念入门（半天，仅阅读，练④）

- **目标**：建立坐标，不装环境不写项目。
- **阅读**：Temporal 官方 docs 的 Core Concepts（Workflow/Activity/Durable Execution）
  + 一篇 Orchestration vs Choreography 对比文章。
- **验收标准**：能用三句话向别人解释 Temporal 解决什么问题、SpiffWorkflow 解决什么
  问题、二者差别在哪。

## 六、顺序与排期建议

`1（1天）→ 2（3~5天）→ 3（2~3天）→ 4（半天）`，总 7~9 个学习日。
- 收益最高的是阶段 2：一次串起本次会话追问的三个问题（TPM 插件原理 / Python 生态
  对应物 / 引擎与状态机之争）。
- 若时间只够一半：做 2 + 4（引擎体感 + 顶层坐标），1、3 后置。
- 一切以第三阶段主线交付为先，本路线在其后见缝插针。
