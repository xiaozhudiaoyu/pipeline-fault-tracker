# Java 语法速查（Python 开发者专用）

> 本文档只覆盖「pipeline-fault-tracker Java 练习」中**实际用到**的语法，不写教科书式全量。
> 每条都附 Python 对照 + 练习工程里的真实例子。遇到新语法会追加。
> 运行基座：JDK 1.8 / Spring Boot 2.7.18 / javax 命名空间。

---

## 1. 文件结构与包

```java
package com.example.fault;   // 必须 = 目录路径（src/main/java/com/example/fault/）
import com.fasterxml.jackson.annotation.JsonValue;  // 全限定名导入
```

| Python | Java | 区别 |
|---|---|---|
| 文件放哪都行，靠 `__init__.py` | **目录 = 包名**，铁律 | 放错目录编译直接报错 |
| `from x import y` | `import x.y;` | Java 没有 `from`，导入的是类全名 |
| 无分号 | **每条语句末尾 `;`** | 漏了编译报错 |

---

## 2. 类型系统

```java
String name = "hello";     // 引用类型，首字母大写
int count = 42;            // 基本类型，小写
boolean flag = true;
void doSomething() {}      // 无返回值
```

| Python | Java | 注意 |
|---|---|---|
| 变量不写类型 | **必须声明类型**（或 `var`，但 Java 8 没有 var） | 编译期强制 |
| `None` | `null` | 只有引用类型能为 null，`int` 不行 |
| `str` | `String`（大写 S） | `string` 小写不存在 |
| 动态类型 | 静态类型，赋值类型不匹配编译报错 | |

---

## 3. 类（POJO）

```java
public class User {
    private final String displayName;       // 字段：类型 + 名字

    public User(String displayName) {       // 构造器：名 = 类名，无返回类型
        this.displayName = displayName;     // this = Python 的 self
    }

    public String getDisplayName() {        // getter：惯例 getXxx()
        return displayName;
    }
}
```

| 概念 | Python | Java |
|---|---|---|
| 字段声明 | `__init__` 里 `self.x = x` 随手写 | **必须在类顶部先声明**（带类型 + 访问修饰符） |
| 构造器 | `def __init__(self, ...)` | `public ClassName(...)` —— 无返回类型 |
| self | 显式第一个参数 | `this` 关键字，不用写在参数里 |
| 属性访问 | `obj.display_name` 直接读 | `obj.getDisplayName()` 走 getter |
| 不可变 | 无原生支持 | `final` 字段：构造器赋值后不可改 |

### 访问修饰符

| 修饰符 | 含义 | Python 近似 |
|---|---|---|
| `public` | 谁都能访问 | 普通属性 |
| `private` | 只有本类内部 | `_name`（约定私有） |
| 不写（default） | 同包内可访问 | 无对应 |

---

## 4. 枚举（enum）

```java
public enum FaultStatus {
    PENDING("pending"),          // 常量名大写，括号传 value
    PROCESSING("processing"),
    DONE("done");                // 最后一个用分号！前面用逗号

    private final String value;

    FaultStatus(String value) {  // 构造器：隐式 private，不能写 public
        this.value = value;
    }

    @JsonValue
    public String getValue() { return value; }
}
```

| Python | Java | 关键差异 |
|---|---|---|
| `class FaultStatus(str, Enum)` | `enum FaultStatus { ... }` | Java 枚举不是字符串 |
| JSON 直出 `"pending"`（继承 str 白得） | 需要 `@JsonValue` 注解 | 不加则输出 `"PENDING"` |
| `FaultStatus("pending")` 按 value 反查 | **没有自动反查**，要手写 `fromValue` | 见下节 |
| `for s in FaultStatus` | `for (FaultStatus s : FaultStatus.values())` | `values()` 自动生成 |
| `FaultStatus.PENDING` | 同 | 常量访问方式一样 |

### 枚举构造器为什么不能 public？

枚举常量在类加载时就全部创建好了（单例），外部不允许 `new FaultStatus(...)`。
所以构造器**强制私有**（写不写 private 都一样）。

---

## 5. 静态方法与反查

```java
public static FaultRole fromValue(String value) {
    for (FaultRole role : FaultRole.values()) {
        if (role.value.equals(value)) {   // 比内容用 .equals()！
            return role;
        }
    }
    throw new IllegalArgumentException("Unknown: " + value);
}
```

| 概念 | Python | Java |
|---|---|---|
| 静态方法 | `@staticmethod` | `static` 关键字 |
| 调用方式 | `FaultRole.from_value("admin")` | `FaultRole.fromValue("admin")` —— 类名点，不用 new |
| 遍历所有枚举 | `for r in FaultRole` | `for (FaultRole r : FaultRole.values())` |
| 抛异常 | `raise ValueError(...)` | `throw new IllegalArgumentException(...)` |

### `valueOf` vs `fromValue`

- `FaultRole.valueOf("ADMIN")` —— Java **自带**，只认常量名（大写），认不了就抛异常。
- `FaultRole.fromValue("admin")` —— **我们手写**，按 value（小写串）反查。
- Python 的 `FaultRole("admin")` 等价于后者。

---

## 6. ⚠️ `==` vs `.equals()`（头号大坑）

```java
String a = new String("hello");
String b = new String("hello");
a == b          // false！比的是内存地址（是不是同一个对象）
a.equals(b)     // true！比的是内容
```

| 场景 | 用什么 | 原因 |
|---|---|---|
| 比字符串内容 | `.equals()` | `==` 比引用，内容相同但对象不同就 false |
| 比枚举常量 | `==` 可以 | 枚举是单例，引用相同 = 身份相同 |
| 判 null | `== null` / `!= null` | null 不是对象，没有 .equals() 可调 |
| 忽略大小写比字符串 | `.equalsIgnoreCase()` | 注意：比 equals 宽松，API 场景慎用 |

**Python 的 `==` 永远比内容；Java 的 `==` 比引用。这是跨语言第一大 bug 源。**

---

## 7. null 与空安全

```java
User operator = null;                    // 合法，引用类型默认就是 null
operator.getDisplayName();               // 💥 NullPointerException (NPE)

// 防护：先判 null
if (operator != null) {
    operator.getDisplayName();
}
// 或三元
operator != null ? operator.getDisplayName() : snapshot;
```

| Python | Java |
|---|---|
| `None` | `null` |
| `obj.x` 若 obj 是 None → `AttributeError` | `obj.getX()` 若 obj 是 null → `NullPointerException` |
| `x if x else default` | `x != null ? x : default` |

---

## 8. 三元运算符

```java
return operator != null ? operator.getDisplayName() : operatorNameSnapshot;
```

```python
# Python 等价
return self.operator.display_name if self.operator is not None else self.operator_name_snapshot
```

**格式：`条件 ? 真值 : 假值`** —— 把条件放最前面，和 Python 的 `真值 if 条件 else 假值` 顺序相反。

---

## 9. for-each 循环

```java
for (FaultRole role : FaultRole.values()) {
    System.out.println(role.getValue());
}
```

```python
for role in FaultRole:
    print(role.value)
```

格式：`for (类型 变量 : 集合或数组)`。Java 8 没有 Python 的列表推导式，循环就是循环。

---

## 10. 异常

```java
throw new IllegalArgumentException("未知的动作类型: " + value);
```

| Python | Java |
|---|---|
| `raise ValueError("msg")` | `throw new IllegalArgumentException("msg")` |
| 不需要 `new` | **必须 `throw` + `new`** |
| f-string 拼接 | 字符串用 `+` 拼接 |
| `try / except` | `try / catch` |

常见异常类型：
- `IllegalArgumentException` —— 参数非法（≈ ValueError）
- `NullPointerException` —— 对 null 调方法（≈ AttributeError on None）
- `IllegalStateException` —— 状态不对（≈ RuntimeError）

---

## 11. Lambda 表达式

```java
assertThrows(IllegalArgumentException.class,
        () -> TimelineAction.fromValue("nope"));
```

```python
# Python 等价
with pytest.raises(ValueError):
    TimelineAction("nope")
```

- `() -> 表达式` = 无参 lambda，等价 Python `lambda: 表达式`
- `(x) -> x + 1` = 有参 lambda，等价 Python `lambda x: x + 1`
- Java 8 的 lambda 只能用于**函数式接口**（只有一个抽象方法的接口），不像 Python 随处可用。

---

## 12. 注解（Annotation）

```java
@Size(min = 1, max = 200)       // 贴在字段上
private String title;

@Test                            // 贴在方法上
@DisplayName("描述")
void myTest() { ... }

@JsonValue                       // 贴在 getter 上
public String getValue() { ... }
```

| Python | Java | 区别 |
|---|---|---|
| `@decorator` 装饰器（执行函数包装） | `@Annotation` 注解（纯元数据标签） | 注解本身不执行逻辑 |
| `Field(min_length=1)` | `@Size(min = 1)` | 参数写法 `key = value` |
| 运行时立即生效 | 需要框架读取并执行（如 Validator / Spring） | |

---

## 13. 泛型

```java
Set<ConstraintViolation<FaultCreateDto>> violations = validator.validate(dto);
List<String> names = new ArrayList<>();
```

| Python | Java |
|---|---|
| `set[ConstraintViolation]`（3.9+ 类型标注，可选） | `Set<ConstraintViolation<...>>`（编译期强制） |
| 运行时不检查 | 编译期检查，类型不对直接报错 |
| `list[str]` | `List<String>` |

- 尖括号 `<>` 里写元素类型。
- `new ArrayList<>()` 的 `<>` 叫"钻石推断"，编译器自动推断类型。
- Java 泛型运行时会**擦除**（type erasure），和 Python 完全不同。

---

## 14. Bean Validation API

```java
// 建 Validator（手动，Boot 里框架自动做）
Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

// 校验一个对象
Set<ConstraintViolation<MyDto>> violations = validator.validate(dto);

// 判断结果
violations.isEmpty()    // true = 通过
violations.size()       // 违规条数
```

| Python (Pydantic) | Java (Bean Validation) |
|---|---|
| `Model.model_validate(data)` 失败**抛异常** | `validator.validate(obj)` 失败**返回集合** |
| `except ValidationError as e` | `if (!violations.isEmpty())` |
| `e.errors()` | 遍历 violations，`.getMessage()` / `.getPropertyPath()` |

### 常用校验注解

| 注解 | 语义 | null 时行为 |
|---|---|---|
| `@NotNull` | 不能为 null | 违规 |
| `@NotEmpty` | 不能为 null / 空串 / 空集合 | 违规 |
| `@NotBlank` | 不能为 null / 空串 / 纯空格 | 违规 |
| `@Size(min=, max=)` | 长度/大小范围 | **跳过**（null 不触发） |
| `@Min(n)` / `@Max(n)` | 数值范围 | **跳过** |
| `@Pattern(regexp=)` | 正则匹配 | **跳过** |

**核心原则：除 @NotNull/@NotBlank/@NotEmpty 外，所有注解遇 null 直接放行。**

---

## 15. 字符串常用操作

```java
"hello".equals(other)          // 比内容
"hello".equalsIgnoreCase(other) // 忽略大小写
"hello".isEmpty()              // 长度 == 0
"hello".trim()                 // 去首尾空格（≈ Python strip()）
"hello".length()               // 长度（≈ len()）
"a" + "b"                      // 拼接（≈ f-string / +）
String.valueOf(42)             // 数字转字符串（≈ str(42)）
```

---

## 16. 命名惯例

| 东西 | 惯例 | 例子 |
|---|---|---|
| 类 / 接口 / 枚举 | PascalCase | `FaultStatus`, `UserService` |
| 方法 / 变量 / 字段 | camelCase | `getDisplayName`, `operatorNameSnapshot` |
| 常量 / 枚举成员 | UPPER_SNAKE | `PENDING`, `MAX_RETRY` |
| 包名 | 全小写 | `com.example.fault` |

Python 用 snake_case  everywhere；Java 用 camelCase + PascalCase 混用。**不要写 snake_case 方法名**（能编译但违反惯例，代码审查会被打回）。

---

## 17. 分号、花括号、注释

```java
// 单行注释（同 Python #）
/* 多行注释 */
/** 文档注释（Javadoc，同 Python docstring） */

if (x > 0) {        // 花括号 = Python 的缩进块
    doSomething();   // 分号 = 语句结束
}
```

- **每条语句末尾必须 `;`**（类/方法声明的花括号后不加）。
- **花括号 `{}` 界定代码块**，不靠缩进（缩进只是美观）。
- 枚举常量列表：逗号分隔，**最后一个用分号**。

---

## 18. Jackson 反序列化注解（第二层踩坑后补）

```java
@JsonCreator
public FaultCreateFixedDto(
        @JsonProperty("title") String title,
        @JsonProperty("description") String description) {
    this.title = title;
    this.description = description;
}
```

| Python (Pydantic) | Java (Jackson) |
|---|---|
| 字段名自动匹配 JSON key | 有参构造器必须加 `@JsonCreator` + `@JsonProperty` |
| 无参构造器不需要 | 无参构造器 + setter 也行（JavaBean 风格） |

**坑**：只写有参构造器不加注解 → `InvalidDefinitionException: no Creators, like default constructor, exist`。

---

## 19. Spring MVC 异常处理与集合（第二层补）

```java
@RestControllerAdvice   // 全局异常拦截器（≈ @app.exception_handler）
public class ValidationExceptionHandler {
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handle(...) { ... }
}
```

| 概念 | Python | Java |
|---|---|---|
| 全局异常处理 | `@app.exception_handler(XxxError)` | `@RestControllerAdvice` + `@ExceptionHandler` |
| 手动指定状态码 | `JSONResponse(status_code=422)` | `ResponseEntity.status(422).body(...)` |
| dict | `{}` | `Map<String,Object>` / `new HashMap<>()` |
| dict 赋值 | `d["k"] = v` | `map.put("k", v)` |
| list | `[]` | `List<T>` / `new ArrayList<>()` |
| list 追加 | `lst.append(x)` | `list.add(x)` |

---

## 20. 自定义约束注解（第四层收尾补）

```java
// 文件 1：注解定义（声明“长什么样”）
@Target({ElementType.FIELD})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = MyValidator.class)
public @interface NotInFutureWithTolerance {
    String message() default "错误消息";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
    int seconds() default 60;   // 自定义参数
}

// 文件 2：校验逻辑（实现“怎么判”）
public class MyValidator implements ConstraintValidator<NotInFutureWithTolerance, LocalDateTime> {
    private int seconds;
    @Override
    public void initialize(NotInFutureWithTolerance a) { this.seconds = a.seconds(); }
    @Override
    public boolean isValid(LocalDateTime v, ConstraintValidatorContext ctx) {
        if (v == null) return true;
        return !v.isAfter(LocalDateTime.now().plusSeconds(seconds));
    }
}
```

| Python | Java |
|---|---|
| `@field_validator` 一个函数搞定 | 拆成注解 + Validator 类两个文件 |
| `raise ValueError(...)` | `return false`（框架自动生成错误消息） |
| `datetime.now()` | `LocalDateTime.now()` |
| `+ timedelta(seconds=60)` | `.plusSeconds(60)` |
| `v > deadline` | `v.isAfter(deadline)` |

---

## 21. Spring Boot 注解（第二层）

| 注解 | 作用 | Python 对照 |
|---|---|---|
| `@SpringBootApplication` | 启动入口 + 组件扫描 | `app = FastAPI()` |
| `@RestController` | 标记为 HTTP 控制器 | `APIRouter()` |
| `@RequestMapping("/api/faults")` | 路由前缀 | `APIRouter(prefix="/api/faults")` |
| `@GetMapping` / `@PostMapping` | 具体路由 | `@router.get("")` / `@router.post("")` |
| `@Service` | 注册为业务 Bean | 无直接对应（FastAPI 无 DI 容器） |
| `@RequestBody` | 请求体反序列化 | Pydantic model 参数 |
| `@Valid` | 触发 Bean Validation | Pydantic 自动校验 |
| 构造器注入 | DI：Spring 自动 new 并传入 | `Depends(get_db)` |

**核心哲学差异**：FastAPI 依赖每请求重跑；Spring Bean 默认进程级单例。

---

## 22. JPA 实体注解（第三层）

```java
@Entity                          // ≈ class Pipeline(Base):
@Table(name = "pipelines")       // ≈ __tablename__ = "pipelines"
public class PipelineEntity {
    @Id                          // ≈ primary_key=True
    @GeneratedValue(strategy = GenerationType.IDENTITY)  // ≈ autoincrement=True
    private Long id;

    @Column(name = "code", length = 50, unique = true, nullable = false)
    private String code;         // ≈ mapped_column(String(50), unique=True, nullable=False)

    protected PipelineEntity() {}  // Hibernate 反射必需（不能删！）
}
```

| Python (SQLAlchemy) | Java (JPA) |
|---|---|
| `class X(Base)` | `@Entity` |
| `__tablename__` | `@Table(name=)` |
| `mapped_column(primary_key=True)` | `@Id` + `@GeneratedValue` |
| `mapped_column(String(50))` | `@Column(length=50)` |
| `Mapped[int]` 类型标注 | 字段类型 `Long` / `Integer` |
| 不需要无参构造 | **必须有**（protected 即可） |

---

## 23. JPA 关系映射（第三层）

```java
// 多端（持有 FK）
@ManyToOne(fetch = FetchType.LAZY)
@JoinColumn(name = "pipeline_id", nullable = false)
private PipelineEntity pipeline;

// 一端（被引用）
@OneToMany(mappedBy = "pipeline", cascade = CascadeType.ALL, orphanRemoval = true)
private List<PipelineFaultEntity> faults = new ArrayList<>();
```

| Python | Java | 说明 |
|---|---|---|
| `ForeignKey("pipelines.id")` + `relationship()` | `@ManyToOne` + `@JoinColumn` | **合成一个字段** |
| `relationship(back_populates=)` | `@OneToMany(mappedBy=)` | 镜像声明 |
| `cascade="all, delete-orphan"` | `cascade=ALL, orphanRemoval=true` | 拆成两个属性 |
| `ondelete="CASCADE"` | DDL: `ON DELETE CASCADE` | JPA 注解不管 DDL 级行为 |
| `ondelete="SET NULL"` | DDL: `ON DELETE SET NULL` | Hibernate 5.6 无声明式，应用层手动清 |
| `lazy="selectin"` | `@EntityGraph(attributePaths={...})` | 防 N+1 |

**核心差异**：Python 的 FK 列和关系是两个独立属性（可以各写各的 → BUG-C）；
JPA 合成一个字段，Hibernate 自动推导 FK，从设计上堵住 BUG-C。

---

## 24. Spring Data JPA Repository（第三层）

```java
public interface PipelineRepository extends JpaRepository<PipelineEntity, Long> {
    // 零实现代码！继承即获得 save/findById/findAll/deleteById/count...
}

public interface PipelineFaultRepository extends JpaRepository<PipelineFaultEntity, Long> {
    // 方法名派生查询（不用写 SQL）
    List<PipelineFaultEntity> findByPipelineId(Long pipelineId);

    // @EntityGraph 预加载（防 N+1）
    @EntityGraph(attributePaths = {"pipeline"})
    List<PipelineFaultEntity> findAllBy();
}
```

| Python (crud.py) | Java (Spring Data) |
|---|---|
| `session.execute(select(X).where(...))` | `findByXxx(...)` 方法名即查询 |
| `session.add(obj); session.commit()` | `repo.save(obj)` |
| `session.get(X, id)` | `repo.findById(id)` → `Optional<T>` |
| `session.delete(obj)` | `repo.deleteById(id)` |
| 手写每个操作 | **继承即全套 CRUD** |

---

## 25. Flyway 迁移（第三层）

```
src/main/resources/db/migration/
├── V1__create_tables.sql    ← 建表 + 种子数据
└── V2__add_priority.sql     ← ALTER TABLE + UPDATE 回填
```

| Python (Alembic) | Java (Flyway) |
|---|---|
| `versions/xxxx_name.py` | `db/migration/V1__name.sql` |
| Python 代码 `op.add_column(...)` | **纯 SQL** `ALTER TABLE ...` |
| 有 `downgrade()` 可回滚 | **只向前**，没有回滚 |
| revision 哈希链 | 版本号数字排序 |
| `alembic upgrade head` | Spring Boot 启动自动执行 |
| `create_all()` 或 Alembic 管 DDL | Flyway 独家管，Hibernate 只 `validate` |

**坑**：`@Enumerated(STRING)` 存 `.name()`（大写 NORMAL），不是 `.value`（小写 normal）。
SQL 里必须写大写，否则读回时 `valueOf("normal")` 报 `No enum constant`。

---

## 26. Hibernate 一级缓存与 N+1（第三层）

```java
// N+1 复现：
List<Fault> faults = faultRepo.findAll();       // 1 条 SQL
for (Fault f : faults) f.getPipeline().getName(); // 每条触发 1 条懒加载 SQL

// 修复：@EntityGraph → 1 条 LEFT JOIN 全拿
List<Fault> faults = faultRepo.findAllBy();     // 1 条 SQL（含 JOIN）
```

| 概念 | Python | Java |
|---|---|---|
| 一级缓存 | Session identity map | Persistence Context |
| 清缓存 | `session.expunge_all()` | `em.clear()` |
| 刷 SQL | `session.flush()` | `em.flush()` |
| 懒加载 | `lazy="select"` | `FetchType.LAZY` |
| 预加载 | `selectinload(...)` | `@EntityGraph` / `JOIN FETCH` |
| 计数 SQL | `echo=True` 看日志 | `Statistics.getPrepareStatementCount()` |

**坑**：删用户后数据库已置 NULL，但内存对象还持旧引用 → 必须 `em.clear()` 再查。
这就是 Python BUG-C 的 Java 版。

---

## 27. @DataJpaTest 切片测试（第三层）

```java
@DataJpaTest   // 只加载 JPA 层（Entity + Repository），不加载 Web/Service
class CascadeDeleteTest {
    @Autowired PipelineRepository pipelineRepo;
    @Autowired TestEntityManager em;  // .flush() / .clear()
}
```

≈ Python conftest.py 的 `db_session` fixture（内存 SQLite + 回滚），但一个注解全搞定。
每个测试方法包在事务里，结束自动回滚。

---

## 速记卡片（打印贴屏幕旁）

```
比内容 → .equals()        比引用/枚举/null → ==
抛异常 → throw new Xxx()  捕获 → try/catch
字符串拼接 → +            判空 → != null
三元 → 条件 ? 真 : 假     循环 → for (T x : list)
注解 → @Xxx(key=val)      泛型 → List<String>
构造器 → 名=类名,无返回类型  静态 → static,类名.调用
枚举最后 → 分号;          语句末尾 → 分号;
实体 → @Entity+@Table     主键 → @Id+@GeneratedValue
外键 → @ManyToOne+@JoinColumn  一对多 → @OneToMany(mappedBy=)
级联删 → cascade=ALL+orphanRemoval  防N+1 → @EntityGraph
查库 → repo.findById()    存库 → repo.save()
清缓存 → em.clear()       刷SQL → em.flush()
迁移 → V1__name.sql       枚举存库 → 大写 .name()
```
