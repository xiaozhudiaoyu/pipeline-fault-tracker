# 第三阶段实施计划：用户权限与处理闭环（带依赖关系）

> 生成时间：2026-11-02 ｜ 依据：docs/流水线故障记录系统_第三阶段需求_用户权限与处理闭环.txt
> 性质：L 档任务待办清单（用户规则 2.3），交用户确认后逐阶段执行；
> 其中 M3 认证、M4 权限、M2/M8 数据迁移属**高风险面**（规则 2.4），由用户逐行审查后合入；
> 迁移执行、数据演练属**不可逆操作**（规则 2.6），AI 只出脚本，人工审核后执行。
> 每条里程碑标注：前置依赖 ｜ 产出 ｜ 验收 ｜ 风险档。

## 〇、计划前的决策点（D 系列：须用户拍板，未定则后续按推荐项执行）

| # | 决策 | 推荐 | 理由 |
|---|---|---|---|
| D1 | **数据库口径**：需求一/七.3 写 SQLite，但仓库 compose 已切 PostgreSQL（P3 演练成果） | **compose 切回 SQLite + named volume**，保留代码层双方言能力 | 验收按需求文本走；PG 经验不丢（历史迁移文件不动），后续可再切回 |
| D2 | **状态枚举值策略** | **保留 pending/processing/done 三个既有值，新增值 `awaiting_confirmation`（待确认）**；旧库 status=done 的行天然=新"已完成"，**零数据值迁移** | 最小迁移面、回退容易；代价是 done 字面语义 ≠ 中文"待确认"，靠映射常量消化 |
| D3 | **认证载体** | **JWT（HS256）+ 用户表 `token_version`**：登录发 token，每次请求校验签名 + `is_active` + token_version 一致；登出/停用/改密即 bump 版本 → 旧 token 全失效 | 满足需求二.6"停用后即使已登录也不能操作"，无状态、不建 session 表 |
| D4 | **密码哈希库** | **bcrypt 直用**（或 passlib[bcrypt]，实施第一步核实 passlib 对 bcrypt 4.x 的兼容告警后定） | 需求只要求"安全的密码哈希算法"；候选均已证实存在，选型影响依赖台账 |
| D5 | **旧 `/transition` 端点去留** | **移除**，由语义化动作端点替代 | 需求四.3 明确废除"下拉选状态再推进"交互；保留会造成双入口绕过权限（规则 2.7 多入口风险）。移除属删除既有行为，需用户确认 |
| D6 | **需求模糊点四问**（改派后是否重新开始处理 / 处理中能否改基本信息 / 待确认能否改派 / handling_note 与时间线并存关系） | 按保守解读：改派后状态延续；处理中普通用户不可改基本信息（仅待处理阶段）；待确认**不可**改派；handling_note 保留为"最终结果摘要"字段，过程进展只进时间线 | 逐条已列在需求分析回复第四节，用户可单点改 |

## 一、依赖总览

```
D1~D6 决策确认
   │
   ▼
M0 基线保护 ──► M1 数据层(模型+迁移脚本) ──► M2 迁移演练(空库+旧库)
                     │                          │
                     ▼                          │
               M3 认证模块 ──► M4 权限依赖 ──► M5 后端业务闭环(状态机+时间线+接口)
                                                  │
                              ┌───────────────────┼───────────────────┐
                              ▼                   ▼                   ▼
                        M6 前端闭环         M7 存量缺陷修复      M8 种子/演示数据
                              │                   │                   │
                              └───────────┬───────┘                   │
                                          ▼                           ▼
                                    M9 Docker 与交付 ──────► M10 验收场景回归
```
关键路径：D → M0 → M1 → M2 → M3 → M4 → M5 → M6 → M9 → M10。
M7/M8 可在 M5 完成后并行插入；M7 的时区修复建议提前到 M5 之前单独提交（改的是既有
存储口径，越晚改牵连越多）。

## 二、里程碑明细

### M0 基线保护（0.5 天，无前置）
- 内容：
  1. 确认当前工作区干净、第二/阶段成果已提交（git log 核对，commit 由用户执行，规则 5.1）；
  2. 备份 `backend/fault_tracker.db` → `process/fault_tracker.db.bak-p3-日期`（沿用 p2 惯例）；
  3. 为现有流转行为补**失败测试基线**：把需求三/四的每条规则先写成红测试（TDD 前置，规则 3.7）。
- 验收：备份文件实测存在（规则 4.3 不信返回信直读）；红测试清单列出、当前全红。
- 风险：S ｜ 产出物：备份文件 + tests 红用例清单。

### M1 数据层：模型 + Alembic 迁移脚本（1 天，前置 D2）
- 改动文件：`backend/app/models.py`（新增 User、FaultTimeline 模型 + FaultStatus 加
  `awaiting_confirmation` + PipelineFault 加 `created_by_id/assignee_id` 外键）、
  `backend/alembic/versions/xxx.py`（新迁移：建 2 表 + 加 2 列）。
- 表设计草案：
  - `users`：id / username(唯一) / password_hash / display_name / role(enum: user|handler|admin) / is_active / token_version(int 默认0) / created_at
  - `fault_timelines`：id / fault_id(FK, ondelete=CASCADE) / action(enum: create|assign|reassign|start|progress|submit|confirm|return|priority_change) / operator_id(FK users, **SET NULL**, 可空=历史数据) / operator_name_snapshot(String, 冗余快照) / from_status / to_status / from_assignee_id / to_assignee_id / note / is_imported(bool, 标记"升级时导入") / created_at
  - `pipeline_faults.created_by_id / assignee_id`：FK users、**可空**（需求六.2 旧数据"未关联账号"）、ondelete=SET NULL。
- ⚠️ 待验证项：SQLite 默认不开外键，`PRAGMA foreign_keys` 需在 database.py 连接事件中确认开启与否（PG 默认强制）——M1 第一步先实测，不能假设。
- 验收：迁移脚本评审通过（用户逐行审，高风险面）；`alembic upgrade head` 在**空库**成功建全表。
- 风险：**L（数据迁移，只出脚本不执行到真实旧库）**。

### M2 迁移演练：空库 + P2 旧库双路径（0.5 天，前置 M1）
- 内容：复制 p2 备份库到临时位置，跑 upgrade；旧故障 created_by/assignee 留 NULL、
  原 handling_note 导入为 `is_imported=true` 的时间线记录（需求六.3，不编造人/时间）；
  写 downgrade 回退脚本并实测一次。
- 验收：旧库升级后原 id/优先级/状态/说明逐字段比对不变（脚本断言行数与抽样值）；downgrade 可逆。
- 风险：**L（不可逆操作演练——只在副本上跑，真实库执行由人工，规则 2.6）**。

### M3 认证模块（1 天，前置 M1；高风险面，用户逐行审）
- 新增：`backend/app/auth.py`（哈希、JWT 签发/校验、Depends 骨架）、`routers/auth.py`
  （POST /api/auth/login、POST /api/auth/logout、GET /api/auth/me）；config.py 加
  `secret_key`（环境变量，无默认值即启动报错——防裸奔上线）；schemas 加登录请求/响应体。
- 规则落点：停用/改密/登出 → token_version bump（需求二.6 即时失效）；错误结构复用
  ErrorOut（401 code=unauthorized / 403 code=forbidden 新增 handler）。
- 依赖：bcrypt、pyjwt（或 python-jose）——按规则 2.5 先确认后装，同步 DEPENDENCIES.md。
- 验收：登录→带 token 访问 me→登出后 me 401→管理员停用账号后原 token 立即 401 全绿；
  密码入库为哈希（sqlite 直读验证无明文）。
- 风险：**L（认证属高风险面）**。

### M4 权限依赖层（0.5 天，前置 M3；高风险面）
- 内容：`auth.py` 内实现 `get_current_user` / `require_roles(...)` / 故障归属校验函数
  （本人创建 / 分派给本人 / 管理员），供 M5 各端点组合声明；需求二.6 三类检查
  （角色、归属、状态）在此收口成统一入口，**后端为最终裁判**。
- 验收：针对校验函数本身的单元测试（角色×归属×状态组合表覆盖，含"改请求里的
  fault_id/assignee 越权"用例，对应需求九.3 直接请求接口验证）。
- 风险：**L（权限）**。

### M5 后端业务闭环：状态机 + 时间线 + 动作端点（1.5 天，前置 M2+M4）
- 状态机新矩阵（替换 crud.transition_fault 的旧矩阵；D5 移除 /transition 端点）：
  - pending --指派(assign)--> pending（只设 assignee，不改状态；未指派不能开始）
  - pending --开始处理(start,负责人)--> processing
  - processing --追加进展(progress)--> processing（note 必填非空白，多次）
  - processing --提交结果(submit)--> awaiting_confirmation（结果说明必填）
  - awaiting_confirmation --确认(confirm,创建人/管理员代确认)--> done（写 closed_at）
  - awaiting_confirmation --退回(return,创建人)--> processing（原因必填，assignee 不变）
  - pending/processing --改派(reassign,管理员)--> 状态不变（原因必填，记 from/to assignee）
  - done 终态一切拒绝；processing 期间创建人可改 priority 与基本信息按 D6 执行
- 时间线：每个动作同事务写 fault_timelines（需求四.2：**状态更新与时间线插入在同一个
  db.commit() 内**，任一步失败整体回滚——crud 层先改对象+db.add(timeline) 再统一 commit，
  中途不 commit）；优先级调整也记（from/to 值）。
- 新端点清单：`POST /api/faults/{id}/assign|reassign|start|progress|submit|confirm|return`，
  `GET /api/faults/{id}/timelines`；列表接口加 `assignee_id`、`unassigned=true` 筛选与
  角色默认视图过滤（需求四.4：普通用户=本人创建、处理人员=本人负责、管理员=全部）；
  防重复执行：动作端点按"当前状态+归属"守卫，同状态重复调用 409（沿用既有模式）。
- 旧数据兼容：operator_id/created_by_id 为 NULL 时响应显示"历史数据/未关联账号"，
  管理员代确认路径带原因（需求二.5、六.2）。
- 验收：M0 的红测试转绿；导出 CSV 列同步加创建人/负责人（口径变化列入评审）。
- 风险：**L（核心业务逻辑+公共接口，逐行审）**。

### M6 前端闭环（1.5~2 天，前置 M5；部分可与 M5 并行——接口契约定了就能动）
- 新增：登录页 + token 注入（api/client.ts 拦截器）+ 路由守卫 + 401 跳登录；
  顶栏当前用户/登出；`StatusTransitionPanel.vue` **重写**为 `FaultActionPanel.vue`
  （按角色+状态渲染动作按钮，废除下拉选状态，需求四.3）；`FaultTimelineList.vue`
  时间线组件（含"升级时导入"标记）；用户管理页（管理员：新增/启停/重置密码）。
- 修改：列表页角色默认视图 + 负责人筛选 + "未分派"项（需求四.4）；提交期间禁用按钮
  防重复点击（需求四.5）；文案统一"新建故障"等（需求四.5）。
- Zod schema（schemas/fault.ts）与 types 同步新字段/新状态。
- 验收：三账号（普通/处理/管理员）浏览器走通需求九.2 全流程（运行态验证按规则 4.2
  出清单交用户自验，或用户明确要求 AI 代验）。
- 风险：M（多文件；触及公共交互但不触权限判定——权限以后端为准）。

### M7 存量缺陷修复（0.5~1 天，前置 M0，建议尽早、独立提交）
> **状态：已完成（2026-11-10）**。口径由用户选定（规则 3.2 同类多实现须确认）：
> ① 空白校验 = strip 后回写干净值（同第三阶段动作体 `_note_strip`），非 handling_note 的
> 「只校验不回写」；② 范围 = FaultCreate + FaultUpdate 双通道（实测登记通道传纯空格 symptom 也 201）；
> ③ priority = 仅拒显式 null，传合法值仍由 crud 静默忽略（test_n6 既有裁定不动）；
> ④ 实测修正两处计划表述：M7-1 前端早按 `value-format` 发无偏移值、后端 aware 落库是
> 「忽略 tzinfo 存墙钟」（故真正会出错的是 `...Z` 写法）；M7-3 现状已不是 500 而是 200 静默忽略，
> 但 `location/symptom` 显式 null 仍是 500（IntegrityError），已一并按 422 口径拦下。
> 验证脚本：`process/verify_m7_probe_tz.py`、`verify_m7_probe_validate.py`、`verify_m7_alembic_dir.ps1`。
- 需求五逐条与根因定位（已核实）：
  1. **时区 bug**：根因在 FaultCreate.occurred_at 收 aware datetime 落库；修复口径 =
     后端 validator 统一转本地 naive 存储（与 server_default func.now() 口径一致），
     前端发送不带 Z/偏移。牵连面：导出 `_csv_datetime`、列表筛选、既有测试——按 2.7
     先出影响清单再改（M 档）。
  2. **空格校验**：FaultUpdate.location/symptom 补 strip 校验（现仅 pattern 拦首字符空白）；
     确认完成后不可用空格清空说明。
  3. **priority:null 500**：FaultUpdate.priority 显式 null 应 422 而非 500——加 validator
     拒绝显式 null（同 handling_note 既有模式）。
  4. **data 目录**：database.py 建 engine 前自动创建 SQLite 文件父目录（mkdir parents）；
     README 同步说明。
- 验收：每条一个回归测试从红到绿；修复 1 需手工验证"输入 13:00 → 保存 → 刷新 →
  重开详情"四点一致。
- 风险：M（跨文件引用：validator 改动影响 schemas/crud/测试/导出多处）。

### M8 种子与演示数据（0.5 天，前置 M5）
> **状态：已完成（2026-11-10）**。seed.py 的 M8 实体代码（5 个演示账号 + 走动作链的演示故障 +
> 双重幂等）实际早已随 `4acbee6`（M6 用户管理端点）合入，本轮按里程碑口径做验收实测，
> 并补齐 README 第四节 / 10.1 的 `SEED_PASSWORD` 与演示账号说明（原步骤照抄会因缺变量直接中止）。
> 验收脚本：`process/verify_m8_seed.py`（**29 项断言全绿（29 PASS / 0 FAIL）**，数目以脚本内 `check(` 计数与
> 日志 `process/_m8_last.log` 实测为准；全部在 `process/_m8_scratch/` 临时库上跑，
> **未触碰真实开发库**），四条路径：
> ① 空库 `alembic upgrade head` → seed ×2 →（第三次不带 SEED_PASSWORD）四表计数恒为
>    `users=5 / pipelines=3 / pipeline_faults=5 / fault_timelines=17`；角色构成 2+2+1、四种状态
>    齐备、每条故障都有 create 时间线、闭环动作（assign/reassign/progress/submit/confirm）齐全、
>    密码入库为 `$2b$` bcrypt 哈希；
> ② 守护路径：空库 + 无 SEED_PASSWORD → seed rc=1 中止并指明缺密码入口，零账号写入（密码不写死的反证）；
> ②b 密码通道（本轮补）：实测发现 `seed.py` 原用 `os.getenv("SEED_PASSWORD")` 取密码，而
>    `.env` 是 pydantic-settings 读进 `Settings` 字段、**不回填 os.environ** —— 即 `.env.example` 里
>    那行注释掉的 `SEED_PASSWORD` 写了也不生效（已探针实测：同文件 DATABASE_URL 生效、os.getenv 为 None）。
>    经用户选定 A+B 共存方案：`config.Settings` 新增 `seed_password: str | None = None`（默认 None，不内置口令），
>    `seed.py` 改读 `settings.seed_password`，文档（`.env.example` / README）同步口径；
>    新增 C1/C2 两项断言用 bcrypt 离线比对入库哈希证实：.env 单通道可用，且两通道并存时环境变量优先；
> ③ 旧库路径：`process/fault_tracker.db.bak-p2-20261102`（停在 a74bf448a946，2 流水线 / 17 故障）
>    `upgrade head` 后 seed ×2 → 只补 5 个账号，流水线/故障数量不变、17 行旧数据逐字段（编号/状态/
>    优先级/说明/位置/现象/发生与完成时间）不变。
> 真实开发库现状（只读直查）：`105a10b2f697`、users=5 / pipelines=2 / faults=18 / timelines=15，
> 演示账号已在库中，本地无需重新播种。
> 遗留观察（**不属 M8**，登记给 M9/M10）：旧 `handling_note` 未导入为 `is_imported=true` 时间线
> （`test_phase3_workflow.py` HD2 仍 xfail），当前按需求六.3「单独显示为历史处理说明」一路满足；
> README 10.1「跑完基线 + 索引 + priority 三个迁移，库内 alembic_version=b3e19c4d7a52」已过时
> （现为四个迁移、head=105a10b2f697），待 M9 文档一次性校正。
- 内容：seed.py 扩展——2 普通用户 + 2 处理人员 + 1 管理员测试账号（密码走环境变量，
  不写死）；保留 P2 模拟库文件用于 M2/验收升级演示；幂等：重复执行不重复插账号。
- 验收：连续执行两次 seed，账号/流水线数量不变（实测 count）。
- 风险：S~M。

### M9 Docker 与交付文档（1 天，前置 M6+M7+M8）
> **状态：代码/文档已落地（2026-11-10），运行态待用户自验**。用户裁定「两种都要」：
> ① compose **定稿为 SQLite 默认主线**（`docker-compose.yml`：`sqlite:////app/data/fault_tracker.db`
> + named volume `pft-data`，无 postgres）+ **PostgreSQL 可选覆盖**（新增 `docker-compose.pg.yml`，
> 多 `-f` 叠加切方言）；② **推翻早期「entrypoint 暂不实施」决策**，新增 `backend/entrypoint.sh`
> （`alembic upgrade head` 幂等 → `exec uvicorn`），Dockerfile 改 ENTRYPOINT+CMD、`COPY` 前 `sed 剥 CR`；
> ③ 新增 `backend/create_admin.py`（读 `settings.admin_*`，幂等、已存在即跳过不重置密码，配 config.py 三字段）；
> ④ `SECRET_KEY: ${:?}` 强制根 `.env`（新增根 `.env.example`），密钥/口令不写死；⑤ README 全面重写（角色
> 流程/接口表/配置/Docker 部署/自检与已知问题）、`docker.md` 追加 12.8 定稿节。
> **静态实测**：空库 alembic upgrade head 建全 5 表至 head `105a10b2f697`；create_admin 临时库 18 项断言全绿；
> compose config 校验 SQLite/PG 合并/缺 SECRET_KEY 被拒三态均符预期；py_compile 通过。
> **验收脚本**：`process/verify_m9_create_admin.py`（M9 遗留观察处理：README 10.1 迁移数已过时→已校正为 4 个、
> head=105a10b2f697；HD2 旧 handling_note 未导入 is_imported 时间线仍 xfail，已登记进 README 已知问题，
> 按需求六.3「历史处理说明」一路满足，不阻塞）。
- 内容：compose 按 D1 切回 SQLite（backend 挂 named volume 存 fault_tracker.db，
  DATABASE_URL 指容器内路径）；容器启动时执行 `alembic upgrade head`（幂等，多次启动
  不清库不重插）；初始管理员创建脚本（已存在则跳过不重置密码，需求七.4）；README 补：
  角色权限与业务流程简述、配置项、启动/升级/停止/日志/备份、本地开发路线保留、
  自检结果与已知问题（需求八.4）。
- 验收：干净环境 `docker compose up -d --build` 一条龙跑通（运行态出清单交用户，
  或按需 AI 代验附截图）；重启容器数据仍在（需求九.6）。
- 风险：M~L（部署属不可逆操作类，compose 变更出脚本+人工执行）。

### M10 验收场景回归（0.5~1 天，前置全部）
- 按需求九.1~9.6 逐场景执行：空库初始化+旧库升级双路径；全流程时间线完整性；
  **直接请求接口**验证越权拦截（非只看按钮隐藏）；改派后旧负责人失权；创建人停用后
  管理员代确认；非法值/空白/重复操作不产生脏数据；容器重建数据保留。
- 产出：验收清单勾选表 + 未验证项登记（规则 4.1/4.6），交用户演示。
- 风险：验证类任务，不改功能。

## 三、排期与并行建议（一周周期）

| 天 | 主线 | 并行 |
|---|---|---|
| D1 上午 | 决策确认 D1~D6 + M0 | — |
| D1 | M1 → M2 演练 | M7-4（data 目录，独立小改） |
| D2 | M3 认证 | M7 其余条目（时区影响清单先行） |
| D3 | M4 权限 + M5 状态机/时间线 | M6 登录页/守卫（契约已稳） |
| D4 | M5 动作端点 + 列表筛选 | M6 动作面板/时间线组件 |
| D5 | M6 收尾 + M7 修复合入 + M8 | README 草稿 |
| D6 | M9 Docker + 干净环境演练 | M2 旧库升级复验（用最新迁移） |
| D7 | M10 验收回归 + 压缩包交付检查 | 缓冲 |

## 四、全程约束提醒

- 高风险面（M1/M2/M3/M4/M5/M9）：AI 出实现 → **用户逐行审查**后才算合入；
- 不可逆操作（真实旧库迁移、容器部署、git 提交/打包）：AI 只出脚本与步骤，人工执行；
- 依赖新增（bcrypt、pyjwt）：装前确认、装后补 DEPENDENCIES.md 台账（规则 2.5）；
- 每个里程碑独立可验证、独立可提交（规则 5.1 一次提交一件事）；M7 与功能改动**分开提交**；
- 流程图查看器（_p4_bpmn_flow_viewer_memo.md）不在本周期范围，M5 的时间线接口即其数据基础。
