# Python → Java 逐层对照练习清单（以流水线故障记录系统为教材）

> 用途：以本项目 `backend/app/` 的真实实现为「标准答案」，分层把它翻译成 Java / Spring 生态的等价写法，
> 服务于「全面了解工作流技术层次（状态机 / BPMN 引擎 / 任务编排）」的学习目标。
> 每一层的「掌握判定」全部写成可自测的行为，不是「看懂了」。
> 对照对象为 Python 侧文件，链接可点开核对；本清单不改任何业务代码。

## 贯穿全局的定位

**本项目本身就是一个手写的状态机**：

- 状态是一个枚举列：`PipelineFault.status`（pending / processing / awaiting_confirmation / done）
- 流转规则硬编码在 Python：`crud.py` 各动作函数 + `auth.py` 的 `check_can_*`（角色 × 归属 × 当前状态 三维判定）
- 审计是自己建的 append-only 表：`FaultTimeline` + 每次动作同事务 `_write_timeline`

第一~四层是「把这套东西换成 Java 的说法重写一遍，行为逐条对齐」；
第五层（Camunda / Flowable）才是学习正题——**把状态机从代码里搬到引擎里**。

## 动手顺序与 Java 沙箱准备

层与层有依赖，建议顺序：`①语法OOP → ④Bean Validation → ②Spring路由DI → ③JPA/Flyway →（第五层前补 MyBatis-Plus）→ ⑤Flowable`。
①④ 属语言/库层面，先打通「能编译能跑单测」，再进框架。

运行基座（**与本机 `E:\git\TPM-project-be` 对齐，无需新装**）：

- **JDK 1.8**（本机已装，`JAVA_HOME=C:\Program Files\java\jdk1.8.0_121`）——Spring Boot 2.7.x 就跑在它上面
- **Spring Boot 2.7.18** + `javax.*` 命名空间（**不是** Boot 3 的 `jakarta.*`）；校验、持久层注解全按 2.7 口径写
- **Lombok**（TPM 项目全量使用，替代 Java 14+ 才有的 `record`）
- Maven：命令行 `mvn` 未上 PATH，用 **IntelliJ 自带 Maven** 或复用 TPM 项目的 Maven；新建工程走 Maven Wrapper（`mvnw`）
- 练习工程用**独立极简 Maven 模块**（不塞进 JeecgBoot，避免被框架约定淹没基础），仅第五层去读 `E:\git\TPM-project-be` 里的真实 Flowable 代码
- 每层做完，把 Python 版对应接口的 `curl` / 测试当标准答案比对，行为一致才算过

> Java 8 上的取舍：`record`、文本块、`switch` 表达式等 Java 14+ 语法**不可用**，一律用 Lombok `@Value`/`@Data` + 普通类替代——这与 TPM 项目自身写法一致。
>
> 状态数校核：`FaultStatus` 在 models.py 实测 **4 个取值**（pending / processing / awaiting_confirmation / done）。文中「五态」为早期口径，写码以代码为准，多出的那一态（未指派 / 历史态）在第五层建模时单独对齐。

---

## 第一层：语法与 OOP

| 维度 | 内容 |
|---|---|
| 现有 Python | [`models.py`](../backend/app/models.py) 的 `class FaultStatus(str, enum.Enum)`、`@property operator_name`、`__repr__`；`Mapped[int]` / `str \| None` 类型标注；`datetime` |
| Java 等价 | `enum FaultStatus { PENDING("pending"), ... }`（带 `value` 字段 + `@JsonValue`（对应 Python 继承 `str` 让 JSON 直出小写串；MyBatis-Plus 的 `@EnumValue` 留到补持久层再讲））；Lombok `@Data`/`@Value` 普通类 + getter（**Java 8 无 `record`**）；`@ToString` 替 `__repr__`；`Optional<T>` 替 `T \| None`；`java.time.LocalDateTime` 替 `datetime`；`List<T>`/`Map` 泛型替 `list[...]` |

最该体会的差异：Python `class FaultStatus(str, enum.Enum)` 同时是枚举又是字符串，`fault.status.value`、JSON 直出 `"pending"` 都是白得的；Java 枚举和字符串是两回事，「两侧口径要一致」那类坑（TimelineAction 那条已踩过）会换个形式重现，值得专门踩一次。

掌握判定（全绿再进下一层）：

- [x] 不看 Python 源码，凭记忆写出 4 个枚举（FaultStatus / FaultPriority / FaultRole / TimelineAction），每个都能序列化成需求里那套小写字符串（写 Jackson 序列化单测断言 `"pending"` 而非 `PENDING`）。**（起步红灯测试已生成：`process/java-practice/` 里的 `FaultStatusTest`——让尚未创建的 `FaultStatus` 编译通过并跑绿，就是整条路线的第一小步。）**已完成（2026-11-18）：4 枚举 + `TimelineActionTest`/`FaultRoleTest` 全绿；并补练了「按 value 反查」静态方法 `fromValue`（Java 无 Python `Enum(value)` 自动反查能力，`valueOf` 只认常量名），运行态由用户在 IntelliJ 实测通过。**遗留**：`fromValue` 非法值抛异常分支未单测，第四层补。
- [x] 用 Java 重写 `TimelineOut.operator_name` 的「优先取 display_name、账号已删回退快照」逻辑（两个可空字段 + 一个派生 getter），单测覆盖「有 operator / operator 为 null 回退快照 / 两者都 null」三条分支。**已完成（2026-11-18）**：范例 `User`/`Timeline` + `TimelineOperatorNameTest` 3 绿；用户仿写 `Attachment.getUploaderName` + `AttachmentTest` 3 绿。

---

## 第二层：Spring Boot 路由与依赖注入

| 维度 | 内容 |
|---|---|
| 现有 Python | [`main.py`](../backend/app/main.py)（app 实例、`lifespan` 建表、`CORSMiddleware`、`include_router`）；[`routers/faults.py`](../backend/app/routers/faults.py) 的 `@router.get("")`、`db: Session = Depends(get_db)`、`user: CurrentUser`、`response_model=`、`Query(...)`；[`auth.py`](../backend/app/auth.py) 的 `get_current_user`、`require_roles(...)` 依赖工厂、`AdminUser` 别名；[`database.py`](../backend/app/database.py) 的 `get_db()` 生成器 |
| Java 等价 | `@RestController` + `@RequestMapping("/api/faults")` 替 `APIRouter(prefix=...)`；`@GetMapping/@PostMapping/@PatchMapping` 替装饰器；`@RequestParam` 替 `Query`、`@PathVariable` 替路径参数、`@RequestBody` 替 Pydantic 请求体；DI 用**构造器注入单例 Bean**（`@Service`/`@Repository` + final 字段）；「每请求一个 session」→ `@Transactional` + `EntityManager` 托管；`CurrentUser`/`require_roles` → Spring Security `@PreAuthorize("hasRole('ADMIN')")` + `SecurityFilterChain`；`CORSMiddleware` → `@CrossOrigin` 或全局 `WebMvcConfigurer`；`lifespan` 建表 → `ApplicationRunner` 或交给 Flyway |

最该体会的差异：FastAPI 依赖是「每请求重跑一遍函数」（`get_current_user` 每次真的解 JWT、查库）；Spring Bean 默认**进程级单例**，「当前用户」这类请求态数据不进 Bean，走 `SecurityContextHolder`。从「显式传参」（`viewer=user` 一路透传到 crud）到「隐式上下文」，是两套 DI 哲学的根本分歧，务必对比着写同一个 `list_faults`。

掌握判定：

- [ ] 用 Spring 复刻 `GET /api/faults`（分页 + 按 pipeline/status/priority/assignee 筛选 + 角色视图过滤），**接口契约与 FastAPI 版逐字节对齐**：同样的 query 参数名、同样的 `{items,total,page,size}` 结构。用同一份 `curl`（改端口）分别打两边，diff 响应体。
- [ ] 让「未登录→401、角色不对→403、越权访问别人故障→404（不泄露存在性）」三条在 Spring Security 下复现——对照 `auth.py` 的 5 道校验链与 `exceptions.py` 里 `PermissionDeniedError` 的 403/404 取舍。

---

## 第三层：JPA / Hibernate 与 Flyway 迁移

| 维度 | 内容 |
|---|---|
| 现有 Python | [`models.py`](../backend/app/models.py)：`Base(DeclarativeBase)`、`mapped_column`、`ForeignKey(..., ondelete="CASCADE"/"SET NULL")`、`relationship(back_populates=, cascade="all, delete-orphan", lazy="selectin", order_by=)`、`index=True`、`server_default=func.now()`；[`database.py`](../backend/app/database.py) 的 engine / SessionLocal / `create_all`；[alembic 迁移 `add_priority`](../backend/alembic/versions/b3e19c4d7a52_add_priority_to_pipeline_faults.py)（加列带 `server_default` 回填 + PG 枚举类型坑 + `batch_alter_table`）；[`crud.py`](../backend/app/crud.py) 的 `selectinload` 防 N+1 |
| Java 等价 | `@Entity @Table`（Boot 2.7 用 `javax.persistence`）替 `Base` 子类；`@Id @GeneratedValue(strategy=IDENTITY)` 替 `autoincrement`；`@Column(nullable=, unique=, length=)` 替 `mapped_column`；`@ManyToOne @JoinColumn(onDelete=CASCADE)` 替 FK；`@OneToMany(mappedBy=, cascade=ALL, orphanRemoval=true)` 替 `cascade="all, delete-orphan"`；`@OrderBy`；N+1：`lazy="selectin"` → `@EntityGraph` 或 JPQL `JOIN FETCH`（Hibernate 默认 LAZY + `LazyInitializationException` 是新坑）；`server_default=func.now()` → `@CreationTimestamp/@UpdateTimestamp` 或列 `DEFAULT CURRENT_TIMESTAMP`；**Flyway** 替 Alembic：`db/migration/V1__init.sql`、`V2__add_priority.sql`，配 `spring.jpa.hibernate.ddl-auto=validate`（让 Flyway 独家管 DDL） |

最该体会的差异：SQLAlchemy 可选择 `lazy="selectin"` 精确控制预加载；Hibernate 的 session 缓存、脏检查、`detach` 后访问懒加载直接抛异常，是初学最常翻车处——拿项目里「BUG-C：只写 FK 列导致响应体 assignee 关系陈旧」那个真实案例，在 Java 侧复现「改了 `assigneeId` 没改 `assignee` 关系 → 序列化出旧值」，印象极深。Flyway 默认**只向前、不回滚**（没有 Alembic 的 `downgrade`），与现在依赖回滚的习惯不同，要专门适应。

掌握判定：

- [x] 建 `Pipeline 1─N PipelineFault` + `User`，跑通「删流水线级联删故障」（`orphanRemoval`）和「删用户把 `created_by_id`/`assignee_id` 置空不删故障」（`onDelete=SET NULL`）两条，用 `@DataJpaTest` 断言。**已完成（2026-11-20）**：`CascadeDeleteTest` 4/4 绿 + `SetNullOnDeleteTest` 2/2 绿。注：Hibernate 5.6 无声明式 SET NULL，用应用层清 FK 实现（3c Flyway 补 DDL 双保险）。
- [x] 手写 Flyway `V2` 给已有表加 `priority` 列并回填存量行，**H2 和 PostgreSQL 两方言下都能 `migrate` 成功**（体会 PG 枚举类型坑，看 Flyway + 原生 SQL 怎么绕）。**已完成（2026-11-20）**：`FlywayMigrationTest` 3/3 绿（回填 NORMAL + validate 通过 + DDL 级 SET NULL）。SQL 用 VARCHAR 不用原生 ENUM，H2/PG 通用无方言坑。额外收获：@Enumerated(STRING) 存 .name()（大写）而非 .value（小写）的跨语言坑。
- [x] 打开 Hibernate `show_sql`，用一次列表查询验证加了 `@EntityGraph` 后确实从 `N+1` 条 SQL 降回 1~2 条，与 `selectinload` 效果对齐。**已完成（2026-11-20）**：`NplusOneTest` 2/2 绿（Statistics 计数：LAZY=2条 vs @EntityGraph=1条）。

> 衔接（第五层前补 MyBatis-Plus）：TPM 项目持久层用的是 **MyBatis-Plus 3.5.3.2**（`BaseMapper` + `@TableName`/`@TableField` + `IService`/`ServiceImpl` + `LambdaQueryWrapper`），哲学上是「SQL Mapper + 轻 ORM」，与 JPA 的「实体导航 + Unit-of-Work」正相反。JPA 打完概念后，照 `jeecg-boot-base-core` 里的实体/Mapper 对照写一遍同一张 `PipelineFault`；届时把上面「`@EntityGraph` 防 N+1」换成 MyBatis-Plus 的「`@TableField(select=false)` + 手写 join / 批量查」再看一遍——两套 ORM 设计光谱的差异，本身就是工作流领域之外最值钱的一课。

---

## 第四层：Bean Validation 校验

| 维度 | 内容 |
|---|---|
| 现有 Python | [`schemas.py`](../backend/app/schemas.py)：`Field(min_length=, max_length=, ge=, pattern=r"^\S.*$")`、`ConfigDict(extra="forbid")`、`@field_validator` 的 `_strip_required`（strip 后**重验长度并回写**）、`occurred_at_not_in_future`（业务时区归一 + 容忍 60s）、`handling_note_min_length`、「显式 null 一律 422」；错误汇入 [`exceptions.py`](../backend/app/exceptions.py) 的 `RequestValidationError` handler 转成 `{code,message,details}` |
| Java 等价 | `javax.validation`（Boot 2.7 仍是 `javax`，**非** Boot 3 的 `jakarta`）：`@NotBlank`/`@NotNull`/`@Size(min=5,max=1000)`/`@Pattern`/`@Min(1)` 替 `Field(...)`；`@FutureOrPresent` / 自定义 `@Constraint(validatedBy=...)` 替 `field_validator`（「不晚于当前」这类跨值校验 Java 无现成注解，要自己写 `ConstraintValidator`）；`extra="forbid"` → Jackson `@JsonIgnoreProperties(ignoreUnknown=false)` 或全局 `FAIL_ON_UNKNOWN_PROPERTIES`；`@Valid @RequestBody` 触发校验；`MethodArgumentNotValidException` + `@RestControllerAdvice` 复刻 `ErrorOut` 结构 |

最该体会的差异（也是本项目的精华）：Python 侧踩过的两个真实坑——① 字段级 `min_length` 作用在**未 strip 的原值**上，纯空格能穿过；② `| None` 让显式 `null` 绕过字段级校验、被 `setattr` 到 NOT NULL 列变 500——**在 Bean Validation 里会几乎一模一样地重演**（`@Size` 默认也不 strip，`null` 默认不触发约束）。最佳练法：把 `schemas.py` 的 `_strip_required` 和「不接受显式 null」两条裁定原样搬到 Java，亲眼看 Spring 是不是也给同样的坑，再同样用自定义 validator 补掉。「带着已知的坑去换语言验证」比从零写 CRUD 收获大得多。

掌握判定：

- [x] 对 `POST /api/faults` 让下面 5 个输入的 HTTP 结果与 FastAPI 版**完全一致**：`symptom="     "`→422、`location` 首字符空格→422、`occurred_at` 未来时间→422、`{"status":"done"}` 混进登记体→422（extra forbid）、缺 `pipeline_id`→422；逐条比对 `details[].field/type`。**已完成（2026-11-19）**：`FaultControllerPostTest` 7/7 绿。
- [x] 自定义 `@NotInFutureWithTolerance(seconds=60)` 约束，实现 `occurred_at_not_in_future` 的容差逻辑并写单测（含边界：正好 +60s、+61s）。**已完成（2026-11-19）**：`NotInFutureWithToleranceTest` 4/4 绿（+60s 通过 / +61s 拒绝 / 过去通过 / null 通过）。

> **进度（2026-11-19）**：核心概念已打通——`ValidationBugTest` 证明 @Size 的两个坑在 Java 重演；`FaultCreateFixedDtoTest` 2/2 绿证明 @NotBlank 修好。HTTP 级：`FaultControllerPostTest` **6/6 绿**（空格→422、null→422、首字符空格→422、extra forbid→422、缺必填→422、合法→201）。第一条判定 5 个输入已完成 4 个，剩 `occurred_at` 未来时间需自定义约束（第二条判定）。

---

## 第五层：用 Flowable 重做「五态闭环」（与 TPM 项目同版本 6.8.1，学习目标核心）

这一层不再是「翻译」，而是**换范式**，也是「全面了解工作流技术层次」的正题。现有实现本质见文首「贯穿全局的定位」。

| 你手写的东西 | BPMN 引擎里的对应 |
|---|---|
| `FaultStatus` 枚举 | 流程实例的**当前 Token 位置**（引擎管，不用自己存 status 列） |
| `check_can_*` 里「下一步能去哪」 | BPMN 图的**顺序流 + 网关（exclusive gateway）**，`return` 退回边就是回环 |
| 动作端点 `start/submit/confirm/return` | **User Task**（待处理→「开始处理」任务、待确认→「确认/退回」任务），完成任务即推进 |
| `assignee_id` | User Task 的 `assignee`/`candidateGroups`（handler 组），引擎原生懂「这活儿归谁」 |
| `FaultTimeline`（谁何时做了啥） | 引擎**内置 History Level**（`TASK`/`FULL`），自动生成活动历史 |
| `InvalidTransitionError`（非法流转 409） | 当前节点根本没有这条出线 → 调 API 完成不了 → 天然拦截 |
| `_write_timeline` 与状态同事务 | 引擎的**流程事务**天然保证「推进 + 记历史」原子性 |

Java 侧写法：Flowable 用 `repositoryService.createDeployment().addClasspathResource("fault.bpmn20.xml")` 部署；`runtimeService.startProcessInstanceByKey("faultHandling")` 对应 `create_fault`；`taskService.complete(taskId, vars)` 对应 `submit/confirm` 等动作；`historyService.createHistoricActivityInstanceQuery()` 查时间线。角色 × 归属的「谁能点哪个按钮」用 Flowable IDentity 或退回 Spring Security `@PreAuthorize` 做门禁，引擎只管流程推进。版本对齐 TPM 项目的 **Flowable 6.8.1**（`javax` 栈，随 Spring Boot 2.7）。

> **现成教材就在手边**：`E:\git\TPM-project-be\jeecg-module-system\jeecg-system-biz` 已引入 Flowable 依赖并封装其 service API（`repositoryService`/`runtimeService`/`taskService` 在真实业务里怎么被调用、流程定义存 DB 而非 classpath `.bpmn`）。到这一层先去读它的流程部署与任务完成链路，再回头给自己的 `faultHandling` 建最小流程，比凭空写玩具例子收获大得多。

掌握判定（不追求全绿，追求「讲得清差异」）：

- [ ] 画一张 `faultHandling` 的 BPMN 2.0 图，**节点与 5 态 + return 回环一一对应**，部署后跑通「登记→开始→提交→确认」和「提交→退回→再提交→确认」两条路径（后者正好验证 D6 / SM8「待确认才能退回」规则）。
- [ ] 写一段**对比笔记**（可回填本文件或长期记忆）：把 `status` 存业务表 vs 存引擎 Token，在「并发修改、可审计性、改流程要改代码还是改图、跨系统编排」上的取舍——这就是「状态机 / BPMN 引擎 / 任务编排」三层的本质区分。
- [ ] 诚实记录引擎**帮不上忙**的部分：附件上传（`crud.py` 的 magic bytes 流式落盘）、CSV 导出、密码 / JWT——认清「BPMN 引擎管流程，不管这些 CRUD 与文件」，避免为用引擎而用引擎。

---

## 一句话总纲

①~④ 层是「用 Java 把这 9 个 Python 模块重讲一遍，行为逐条对齐」（每层都拿现有接口/异常当标准答案去 diff）；
⑤ 层是「把已经手写透的那个状态机交给引擎托管，然后说清换了什么、丢了什么」——⑤ 是学习阶段的落点，①~④ 只是到达它必须的语言地基。
