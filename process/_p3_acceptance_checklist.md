# 第三阶段验收清单（需求九.1~九.6）

- 里程碑：M10 验收场景回归（`process/_p3_implementation_plan.md` · M10）
- 执行日期：2026-11-11　性质：验证类任务，**未改动任何功能代码**；仓库内唯一改动是 README 第十二节一行指向本清单（`git diff --stat` = `README.md | 2 +-`），新增内容全部落在被忽略的 `process/` 目录
- 验证深度（用户裁定）：**只做离线 + 接口态**。Docker 与浏览器两类只出清单交用户自验，AI 未起 dev server、未开容器、未开页面（规则 4.2）
- 事实来源：需求原文 `docs/流水线故障记录系统_第三阶段需求_用户权限与处理闭环.txt` 第 45-51 行「九、验收场景」

## 一、执行了什么命令、得到什么结果

| # | 命令（均在 `backend/` 下） | 结果 | 证据文件 |
|---|---|---|---|
| 1 | `.\.venv\Scripts\python.exe -X utf8 -m pytest -q` | `189 passed, 1 xfailed in 26.31s`，退出码 0 | 终端输出（xfail 为既有 HD2 技术债，见第五节） |
| 2 | `.\.venv\Scripts\python.exe -X utf8 ..\process\verify_m10_upgrade.py > ..\process\_m10_upgrade.log` | 31 项断言全绿（A 空库 14 / B 旧库升级 10 / C 无标记卷 7），失败 0，`exit=0` | `process/_m10_upgrade.log` |
| 3 | `powershell -NoProfile -ExecutionPolicy Bypass -File ..\process\_m10_run_api.ps1` | 191 项断言全绿（S1~S8 八场景），失败 0，`exit=0`，无告警噪声 | `process/_m10_api.log` |

脚本 2 走 alembic 副本演练，脚本 3 走 `httpx.ASGITransport` 进程内直连 FastAPI（真实登录 JWT，不覆盖 `get_current_user`），认证链、权限依赖、状态机、crud、SQLite 全栈都在这条链上。**两者均不触碰 `backend/fault_tracker.db` 与 `process/*.bak-*`**：脚本 2 只用 `process/fault_tracker.db.bak-p2-20261102` 的副本，脚本 3 用临时库 `process/_m10_scratch/api.db`（跑完自动删除）。

## 二、九.1~九.6 勾选表

| 场景 | 需求要点 | 覆盖用例 | 结论 |
|---|---|---|---|
| 九.1 | 空库初始化 | 脚本 2 A1~A14：`upgrade head` 一次建齐 `pipelines/pipeline_faults/users/fault_timelines/alembic_version`，版本到 `105a10b2f697`，`pipeline_faults` 含 `priority/created_by_id/assignee_id`；`create_admin` 建 1 个 bcrypt `$2b$` 账号、明文不入库、重跑不重建不重置、缺 `ADMIN_PASSWORD` 即中止且零账号 | ✅ 已实测通过 |
| 九.1 | 第二阶段库升级 | 脚本 2 B1~B10：升级前 `a74bf448a946` / 17 故障 / 2 流水线 / 无 `priority` 列 → 升级后 17 行逐字段零差异，`priority` 回填 `normal`，`created_by_id/assignee_id` 留 NULL，新表初始为空，原 `done` 行仍 `done` 且 `closed_at` 保留 | ✅ 已实测通过 |
| 九.1 | 干净环境启动 Compose | —— | ⬜ **未验证**，交用户（第三节 D1） |
| 九.2 | 报修→指派→多条进展→提交→退回→再处理→确认，时间线完整且状态正确 | 脚本 3 S3-1~S3-42：时间线 11 条动作序列恰为 `create, assign, start, progress, progress, priority_change, submit, return_, progress, submit, confirm`，逐条核对操作人/前后状态/前后负责人；旧记录未被覆盖（前缀比对相等）；退回后负责人不变；确认写 `closed_at` | ✅ 已实测通过 |
| 九.2 | 多账号真实登录 | 脚本 3 S1-1~S1-14：管理员 + 2 报修（`reporter01/02`）+ 2 处理（`handler01/02`）各自登录换真 token；匿名 401、错密码 401、伪造 token 401；重复用户名 409、密码不足 6 位 422 | ✅ 已实测通过 |
| 九.3 | 不能查看/修改他人故障 | 脚本 3 S8-4（列表 id 集与 SQL 直查全等，不混入他人）、S4-10（非相关人详情 404，与"不存在"同码不泄露存在性）、S8-14/15（导出同样收敛） | ✅ 已实测通过（**直接打接口**，非看按钮） |
| 九.3 | 处理人员不能处理他人任务或自行确认 | S3-19（负责人自行 confirm 403）、S3-20/21（他人确认、他人退回 403）、S4-3/S4-7/S7-12（非负责人追加进展 403）、S4-8/9（旧负责人 start/submit 403） | ✅ 已实测通过 |
| 九.3 | 普通账号不能管用户 | S1-12（`user` 查用户列表 403）、S1-13（`handler` 自行建 `admin` 号 403 且未落库）、S2-2（非管理员建流水线 403）、S3-7（报修人自行指派 403） | ✅ 已实测通过 |
| 九.4 | 改派后旧负责人失权、新负责人可继续 | S4-1~S4-20：改派后状态延续 `processing`、负责人已换；旧负责人 progress/start/submit 全 403、详情 404；新负责人 progress 200；改派时间线含前后负责人与原因；待确认状态改派/指派 409；改派理由纯空格 422 且负责人与时间线不变 | ✅ 已实测通过 |
| 九.4 | 创建人停用后的管理员代确认 | S5-1~S5-20：停用 `reporter02` → 其**已登录的旧 token 立即 401**（`账号已被停用`）、且不能重新登录；管理员不带理由代确认 403 且状态未变；带理由代确认 → `done`，时间线记管理员操作人与原因；对照组创建人在用时代确认 403；重置密码后旧 token 401、新密码可用、旧密码失效；管理员停用自己 403 | ✅ 已实测通过 |
| 九.4 | 历史故障处理路径 | S6-1~S6-14：直插两单人员字段全 NULL 的"升级而来"故障 → 非管理员详情 404、管理员可见且 `created_by/assignee` 为 null、原 `handling_note` 保留；`pending` 与 `processing` 两单补指派均 200（BUG-C 口径）；接手人 start/submit → 管理员带理由代确认 `done`；时间线从 `assign` 起共 4 条，不编造 `create`、无 `is_imported` 伪历史 | ✅ 已实测通过 |
| 九.5 | 非法值/空白/重复操作/权限失败不产生脏数据 | S7 全段 43 项：每次被拒后立刻比对「状态 + handling_note + 时间线条数」三者不变；`progress/submit/reason/handling_note/location` 的纯空格与长度不足、`priority:null`、`location:null` 全 422（非 500）；重复 start 409；不存在故障 404；登记伪造 `created_by_id` 被 `extra=forbid` 422；未来时间、空白现象、非法枚举、不存在流水线均拒；本轮零入库（故障总数 7→7）、时间线总量恰 +1（仅那条合法进展） | ✅ 已实测通过 |
| 九.5 | 原有筛选、优先级、时间显示、已完成保护 | S8-1~S8-15：三角色默认视图 total 与 SQL 直查交叉相等（admin 7 / reporter01 3 / handler01 5）；`status/priority/assignee_id/unassigned/pipeline_id+status` 五组筛选结果集与 SQL 全等；列表默认 `occurred_at` 倒序；`13:00` 输入回显 `13:00`、传 UTC `2026-11-02T05:00:00Z` 落库为本地墙钟 `2026-11-02 13:00:00`（naive、不带 Z）；已完成故障 PATCH/优先级 409；CSV 表尾 `creator,assignee` 两列、数据行数=视图条数、时间列 `YYYY-MM-DD HH:mm:ss` | ✅ 已实测通过 |
| 九.6 | 容器重启/重建后数据保留 | —— | ⬜ **未验证**，交用户（第三节 D2/D3） |
| 九.6 | 演示主要流程 + 说明谁能操作、状态与过程不漏记 | 第四节文字说明；流程演示即脚本 3 S3/S4/S5 三段 | ✅ 说明已给，界面演示交用户（第三节 B1~B3） |

## 三、未验证项登记与用户验证清单（规则 4.1/4.2/4.6）

以下项**静态与接口态都无法证明**，AI 未执行，请自行验证；预期结果按需求原文写。

### D 组：Docker（对应九.1 前半、九.6）

- **D1 干净环境一条龙启动**
  操作：仓库根 `copy .env.example .env` → 把 `SECRET_KEY` 改为 ≥32 字节随机串 → `docker compose up -d --build` → `docker compose ps`
  预期：backend/frontend 均 Up；`GET http://localhost:8000/api/health` 返回 `{"status":"ok"}`；backend 日志里 entrypoint 的 `alembic upgrade head` 无报错；`data/fault_tracker.db` 自动生成且带 `alembic_version` 表。
- **D2 重启容器数据保留**
  操作：`docker compose restart`（或 `down` 不带 `-v` 再 `up -d`）→ 登录原账号查一条已完成的故障
  预期：账号、故障、时间线条数与重启前一致，`docker compose down` 未加 `-v` 时卷 `pft-data` 不丢。
- **D3 重建容器与换镜像后数据保留**
  操作：`docker compose up -d --force-recreate --build` → 同上抽查
  预期：数据仍在；`create_admin.py` 重跑不重置已有密码（该行为脚本 2 A11/A12 已离线证明）。
- **D4 旧数据卷接管（README 10.2 告警）**
  预期：只被 `create_all` 建过表、无 `alembic_version` 的旧卷，首启 `upgrade head` 会撞已存在的表；须先 `stamp a74bf448a946`。该行为脚本 2 C1~C7 已在副本上复现并证明接管后零丢失，**容器内的等价操作未实测**。

### B 组：浏览器界面态（对应九.6 演示）

- **B1 三账号闭环演示**：用 `user/handler/admin` 三个账号（本地路线或 `seed.py` 演示账号）走「报修 → 指派 → 追加多条进展 → 提交 → 退回 → 再处理 → 确认」。预期：时间线顺序与内容与接口态一致，退回后仍显示原负责人，`done` 后所有操作按钮消失或禁用。
- **B2 越权的界面表现**：以非创建人打开他人故障链接。预期：列表看不到、详情进不去（后端 404），页面无空白报错刷屏；本项接口侧已证（九.3），界面渲染未证。
- **B3 提交期间按钮禁用**：快速连点「提交处理结果」「确认完成」。预期：请求期间按钮 disabled 不重复提交（代码侧已静态看到 `FaultActionPanel.vue` 的 `:disabled="anyLoading"` 与 mutation pending 态，但未运行态证实）；后端幂等由状态机 409 兜底（S7-11 已证重复动作被拒）。
- **B4 历史故障显示**：管理员打开无账号关联的历史故障。预期：创建人/负责人位显示"历史数据/未关联账号"一类占位，原处理说明仍可读；接口字段已证（S6-4/5），渲染未证。

## 四、九.6 要求说明的两件事（后端如何裁决）

1. **谁能操作**：三维判定全部集中在 `backend/app/auth.py`，路由层以依赖注入调用，不存在"前端藏了就安全"的旁路。
   - 身份层：`get_current_user` 依次校验 Header 存在 → JWT 签名 → 用户存在 → `is_active` → `token_version` 与签发时一致，任一不过即 401；停用与改密通过 bump `token_version` 让**已发出的旧 token 当场作废**（S5-5、S5-16 实测）。
   - 权限层：`check_can_assign/reassign/start/progress/submit/confirm/return/priority_change` 各自**先判角色再判状态**，角色不符 403、状态不符 409；`can_view_fault` + `crud._viewer_filter` 决定列表与详情的可见集合，无权限与不存在**同为 404**，不泄露存在性。
   - 数据层：`created_by_id` 只能由后端按登录账号写入，`FaultCreate` 用 `extra=forbid` 把客户端传来的 `created_by_id` 直接判 422（S7-18）。
2. **状态改了而过程漏记怎么防**：所有状态变更都走 `crud` 的同一批函数，函数内部先改 ORM 对象、再调 `_write_timeline(...)` 追加记录，`_write_timeline` **不 commit**，由函数末尾**唯一一次 commit** 收口——即"状态 + 时间线"在同一事务里，要么一起成功要么一起回滚，没有"只写了状态"的中间态。脚本 3 的每条被拒用例都顺带比对时间线条数不变（S7 的 `rejected()` 助手），43 项断言未见漏记或多记。

## 五、实测中发现的两处观察（未改代码，供决策）

1. **时间线动作在库内是枚举成员名，不是值**：`models.py` 用 `Enum(TimelineAction)` 且未设 `values_callable`，SQLAlchemy 按 **name** 落库，故 `return`（Python 关键字）在库里是 `return_`；对外 JSON 走 **value**，仍是 `return`（S3-28 与 S3-32c 已分别实测）。影响面：全仓检索确认**没有任何 SQL 或代码按字符串过滤 `action`**，故当前无功能影响；若将来写 `WHERE action='return'` 或在 PG 上按值比对会落空，届时可加 `values_callable=lambda e: [m.value for m in e]`（属依赖升级外的行为变更，需单独通道）。前端 `frontend/src/types/timeline.ts` 第 2-3 行的注释结论（"JSON 里就是 return"）经实测成立。
2. **PyJWT 对短 HMAC 密钥会打 `InsecureKeyLengthWarning`**：本次演练初始用了 30 字节测试密钥而触发 stderr 告警，改到 35 字节后消失。项目自带的开发默认密钥 `dev-only-insecure-secret-change-me`（34 字节）与 README/`.env.example` 要求的 ≥32 字节随机串均**不受影响**，无需改动，只是自我提醒不要把过短的 `SECRET_KEY` 配进生产。

既有技术债（本轮未动）：`test_phase3_workflow.py` HD2 仍 `xfail` —— 旧 `handling_note` 未导入成 `is_imported=true` 时间线，按需求六.3「单独显示为历史处理说明」路径已满足，README 第十二节第 2 条已登记。

## 六、本次新增与遗留的验证产物

| 文件 | 作用 | 去留 |
|---|---|---|
| `process/verify_m10_upgrade.py` | 九.1 三条迁移路径离线演练（可重复执行，自带副本与清理） | 保留 |
| `process/verify_m10_api.py` | 九.2~九.5 接口态八场景，191 项断言 | 保留 |
| `process/_m10_run_api.ps1` | 跑上一项并写出 UTF-8 日志（本机控制台码页为 GBK，直接 `>` 重定向会乱码） | 保留 |
| `process/_m10_upgrade.log` / `process/_m10_api.log` | 两份逐项结果证据，含失败项计数 | 保留至验收结论确定 |
| `process/_m10_probe_bak.py` | 一次性探针：确认 P2 备份库结构（`a74bf448a946`、17 故障、无 `priority` 列），为脚本 2 的 B1 断言取基线 | 使命已完成，可删；本次未删（规则 3.1：删除需经确认） |
| `process/_m10_scratch/` | 脚本运行期的临时库目录 | 首跑实测**残留过** `api.db`：Windows 上模块级 engine 的连接池持有文件句柄，`rmtree(ignore_errors=True)` 把失败默吞了。已在脚本内加 `dispose_engine()`（`engine.dispose()` 后 `ignore_errors=False`）修正，复跑实测 `Test-Path process\_m10_scratch` = `False`；需要保留现场时加 `--keep` |

真实开发库 `backend/fault_tracker.db` 与全部 `process/fault_tracker.db.bak-*` 备份：本次**一次都没写入过**，所有演练都在副本/临时库上进行（规则 2.6）。

两点补充事实：

- **未改功能代码的交叉证据**：`git status --short` 仅 ` M README.md`（一行指向本清单的文档改动），`backend/` 与 `frontend/` 源码零改动。`process/` 整个目录被 `.gitignore` 第 60 行忽略，本清单与三个验证脚本**不进版本库**；若验收需要留档归档，需手工拷出或调整忽略规则（本轮未动）。
- **日志编码**：`python … > xxx.log` 在本机（码页 936）会把 UTF-8 输出二次转码成乱码，故日志统一由 `_m10_run_api.ps1` 强制 `[Console]::OutputEncoding = UTF8` 后用 `Out-File -Encoding utf8` 写出。
