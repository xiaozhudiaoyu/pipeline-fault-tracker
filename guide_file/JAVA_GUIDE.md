# Java 完整使用文档（Python 开发者版）

> 适用版本：**JDK 1.8**（本机 `C:\Program Files\java\jdk1.8.0_121`，与练习工程 `process/java-practice` 基座一致）。文中所有 Java 8 代码示例已经本机 `javac 1.8` 编译验证；凡 JDK 9+ 才有的语法均显式标注「Java 8 不可用」。
> 定位：面向 **Python 开发者**的通用 Java 学习手册——语法、面向对象、集合、异常、函数式、IO、并发、工具链全景，每节附 Python 对照。已学知识点的速查版见 [process/java-practice/JAVA_SYNTAX_FOR_PYTHON_DEV.md](../process/java-practice/JAVA_SYNTAX_FOR_PYTHON_DEV.md)，本文是它的完整展开。
> 可信度标注：「实测」= 已用本机 JDK 1.8 编译验证；其余为 Java 官方文档行为。

---

## 目录

1. [Java 与 Python 的世界观差异](#一java-与-python-的世界观差异)
2. [环境与工具链](#二环境与工具链)
3. [基础语法与类型系统](#三基础语法与类型系统)
4. [面向对象](#四面向对象)
5. [异常处理](#五异常处理)
6. [集合与泛型](#六集合与泛型)
7. [函数式编程：Lambda 与 Stream](#七函数式编程lambda-与-stream)
8. [字符串与 IO](#八字符串与-io)
9. [并发基础](#九并发基础)
10. [Maven 与 Spring Boot 生态对照](#十maven-与-spring-boot-生态对照)
11. [坑点汇总](#十一坑点汇总)
12. [速查表](#十二速查表)

---

## 一、Java 与 Python 的世界观差异

### 1.1 一张对照表看懂

| 维度 | Python | Java |
|---|---|---|
| 类型检查 | 动态类型，运行时报错 | **静态类型，编译时报错** |
| 执行方式 | 解释执行（.py → 字节码 → VM） | 编译执行（.java → 字节码 .class → JVM） |
| 「一切皆对象」 | 是（int 也是对象） | 否（`int`/`boolean` 等基本类型不是对象，对应包装类 `Integer`/`Boolean` 才是） |
| 变量 | 名字绑定到对象，随时换类型 | 变量**声明时定死类型**，只能指向该类型的值 |
| 函数是一等公民 | 天然可以 | Java 8 起通过 Lambda / 方法引用间接可以 |
| 空值 | `None` | `null`，且 `NullPointerException` 是 Java 头号运行时异常 |
| 多行结构 | 缩进决定 | **大括号 `{}` 决定**，缩进只是习惯 |
| 语句结尾 | 换行即结束 | **每条语句以 `;` 结尾** |
| 生态入口 | pip + venv + pyproject.toml | Maven/Gradle + pom.xml/build.gradle |
| Web 框架代表 | FastAPI / Flask | Spring Boot |

### 1.2 心智模型转变

- **Python 思维**：先写逻辑，类型跑起来自然清楚，错了运行时告诉你。
- **Java 思维**：先声明「世界由哪些类型构成」（类、接口、泛型），编译器帮你把所有引用关系验一遍，**能编译过，类型层面就基本不会错**；但类型系统的 upfront 成本（写 getter、声明异常、指定泛型）也要自己付。
- 对 Python 开发者最大的三处不适应：**没有默认参数**（靠方法重载补）、**没有关键字参数**（靠 Builder/配置对象补）、**没有多继承**（靠接口 default 方法补）。

---

## 二、环境与工具链

### 2.1 JDK / JRE / JVM

| 名词 | 含义 | Python 近似 |
|---|---|---|
| JVM | 运行字节码的虚拟机 | CPython 解释器 |
| JRE | JVM + 核心类库 | 一个装好的 Python 运行时 |
| JDK | JRE + 编译器 `javac` + 工具 | Python 解释器 + pip + venv 全家桶 |

现在下载 JDK 一般只有 JDK（JRE 从 Java 11 起不再单独发布）。Java 8 常用发行版：Oracle JDK、Amazon Corretto、Eclipse Temurin（均免费可用）。

### 2.2 本机的 JDK 现状（实测）

- `C:\Program Files\java\jdk1.8.0_121`：主用 JDK 8（练习工程基座）；
- `C:\Users\wisdom\.jdks\corretto-1.8.0_392`：IDE 下载的 Corretto 8；
- `C:\Program Files\Java\apache-maven-3.3.3`：Maven 3.3.3。

验证命令（实测）：

```powershell
& "C:\Program Files\java\jdk1.8.0_121\bin\javac.exe" -version
# javac 1.8.0_121
```

### 2.3 编译与运行：最小闭环

Python 开发者最需要先建立的直觉——**源码文件名、类名、目录结构三者是被编译器强制关联的**。

```powershell
# Hello.java（文件名必须与 public 类名一致）
javac -encoding UTF-8 -d out Hello.java   # 编译：.java -> out/Hello.class
java -cp out Hello                        # 运行：类路径 + 类名（不带 .class）
```

对照 Python：`python hello.py` 一步到位；Java 拆成 `javac`（编译期）与 `java`（运行期）两步，`-cp`（classpath）约等于告诉 JVM「去哪里找模块」，作用类似 `PYTHONPATH` 但几乎所有场景都被构建工具接管（见第十节）。

### 2.4 常用启动参数

| 参数 | 作用 | 类比 |
|---|---|---|
| `-cp` / `-classpath` | 类搜索路径 | `sys.path` |
| `-Dname=value` | 设置系统属性 | 环境变量 |
| `-Xmx512m` | 最大堆内存 | 无（Python 托管给 OS） |
| `-encoding UTF-8` | 源文件编码 | `# -*- coding: utf-8 -*-`（Python 3 默认就是 UTF-8） |

---

## 三、基础语法与类型系统

### 3.1 变量声明与基本类型

```java
int count = 42;                 // 整数默认类型
long big = 100_000L;            // 长整数要加 L 后缀
double ratio = 3.14;            // 浮点默认类型
float f = 1.5f;                 // 单精度要加 f 后缀
char c = 'A';                   // 单引号 = 字符（2 字节 Unicode）
boolean ok = true;
String s = "hello";             // 大写 S，是类不是基本类型
var x = 1;                      // ❌ Java 8 不可用（Java 10+ 才有）
```

对照 Python 的注意点：

| Python | Java | 差异 |
|---|---|---|
| `int` 无限精度 | `int` 固定 32 位，溢出**静默回绕** | 大数用 `long`（64 位）或 `BigInteger` |
| `10//3`、`10%3` | `10 / 3`（整型相除截断）、`10 % 3` | 同为整型时 `/` 就是地板除，无独立运算符 |
| `-7 // 2 == -4`（向负无穷） | `-7 / 2 == -3`（向零截断） | 负数除法方向不同，坑点见第十一节 |
| `abs()` `divmod()` | `Math.abs()`；无 divmod | 数学函数全在 `Math` 类 |
| `True/False` | `true/false`（小写） | 大小写敏感 |
| `and/or/not` | `&&`/`\|\|`/`!`；无 and/or | 短路行为一致 |
| 链式比较 `a < b < c` | **语法可过但语义错**（`(a<b)<c` 类型不符，实际编译不过） | 必须拆成 `a < b && b < c` |

### 3.2 类型转换

```java
int a = 7, b = 2;
double r1 = a / b;          // 3.0 —— 先整除再转，经典错误
double r2 = (double) a / b; // 3.5 —— 先转再除，正确姿势
int back = (int) 3.99;      // 3  —— 强制截断，不四舍五入
long auto = a;              // 小 -> 大自动提升，无需写
String num = "42";
int parsed = Integer.parseInt(num);   // 字符串 -> 数字：显式解析
String str = String.valueOf(42);      // 数字 -> 字符串
```

Python 的 `int("42")` / `str(42)` 在 Java 里是**静态方法调用**，各类型各一个名字（`Integer.parseInt`、`Double.parseDouble`…），没有统一的构造器式转换（`new Integer("42")` 已废弃）。

### 3.3 字符串基础（详版见第八节）

Java 字符串**不可变**且是对象，比较内容必须 `.equals()`，这是 Python 开发者第一坑（第十一节坑 1）。字面量拼接用 `+`，循环拼接用 `StringBuilder`。Java 8 **没有** f-string、多行三引号、`in` 运算符。

### 3.4 流程控制

```java
// if / while 与 Python 逻辑一致，条件必须带括号
if (count > 0) { ... } else if (count == 0) { ... } else { ... }

// for 三段式：初始化; 条件; 步进
for (int i = 0; i < 10; i++) { ... }
// for-each：相当于 Python 的 for x in iterable
for (String name : names) { ... }

// switch：传统形式，Java 8 不能当表达式用，每个分支必须 break
switch (code) {
    case 1: doA(); break;
    case 2:
    case 3: doBC(); break;   // 穿透用于合并分支
    default: doOther();
}
// switch 表达式（case 1 -> ...，返回值）是 Java 14+ 语法，Java 8 不可用

// Java 没有 for...else、没有推导式；列表推导的替代见第七节 Stream
```

### 3.5 数组：定长的「底层容器」

```java
int[] arr = new int[5];            // 定长，默认填 0
int[] nums = {3, 1, 4, 1, 5};      // 字面量初始化
nums.length                        // 属性而非方法，Python 的 len() ≈ .length / .size()
Arrays.sort(nums);                 // 原地排序
Arrays.toString(nums);             // "[1, 1, 3, 4, 5]"，直接打印是哈希地址
int[] copy = Arrays.copyOf(nums, 10);
int[][] matrix = new int[3][4];    // 二维数组 = 数组的数组
```

数组定长、不自动扩容、打印要 `Arrays.toString`——日常业务代码里它的地位约等于 Python 里「用 `list` 但提前预分配且不能 append」。**默认用 `ArrayList` 代替数组**（第六节）。

---

## 四、面向对象

### 4.1 类与对象

```java
public class User {
    private final String displayName;    // 字段必须在类顶部声明
    private static int instanceCount = 0; // 类变量（≈ Python 类属性）

    public User(String displayName) {     // 构造器：名同类名、无返回类型
        this.displayName = displayName;   // this ≈ self，但通常省略不报错
        instanceCount++;
    }

    public String getDisplayName() { return displayName; } // getter 惯例
    public static int getInstanceCount() { return instanceCount; }

    @Override
    public String toString() { return "User(" + displayName + ")"; }
}
```

| 概念 | Python | Java |
|---|---|---|
| 字段初始化 | `__init__` 里 `self.x = x` | 类顶部声明 + 构造器赋值 |
| 私有 | `_x` / `__x` 约定与名称改写 | `private` **编译期强制** |
| 类属性/实例属性 | 都是 dict 里的 key | `static` 字段属于类，普通字段属于实例，**必须先声明** |
| `@property` | 描述符协议 | 没有等价物，用 getter/setter 方法 |
| `__str__` | 返回可读字符串 | `toString()` |
| `__repr__` | 调试字符串 | 无统一约定，实践中即 `toString()` |
| `__eq__` | 定义 `==` 行为 | `equals()`，且**必须配套重写 `hashCode()`** |
| `__hash__` | 可哈希性 | `hashCode()` |
| `__len__` | 协议方法 | 无运算符重载，各容器自定 `size()` / `length` |
| 运算符重载 | 支持（`__add__` 等） | **不支持** |
| dataclass | `@dataclass` 一行 | 手写样板 或 Lombok `@Data`（IDE 可自动生成 equals/hashCode/ getter） |

### 4.2 构造器与方法重载（替代默认参数）

```java
public User() { this("anonymous"); }          // 无参构造器
public User(String name) { ... }              // 同参数类型不同默认值也无法重载！
```

Java 没有默认参数，「可选参数」靠**重载**表达；但两个构造器参数顺序相同仅默认值不同时无法用重载区分，Python 的 `def f(a=1, b=2)` 任意子集调用在 Java 里要么写 2ⁿ 个重载，要么改用 **Builder 模式**（链式 `.a(1).b(2).build()`，Lombok `@Builder` 可自动生成）。

### 4.3 继承与多态

```java
public class AdminUser extends User {         // 单继承，Java 没有多继承
    public AdminUser(String name) { super(name); }  // 调父类构造器

    @Override                                  // 注解让编译器帮你检查签名拼写
    public String toString() { return "Admin" + super.toString(); }
}

User u = new AdminUser("tom");                 // 向上转型自动发生
String s = u.toString();                       // 运行时按实际类型分发 → "AdminUser(tom)"
AdminUser a = (AdminUser) u;                   // 向下转型必须显式 + 建议 instanceof 检查
```

- Java 所有实例方法**默认就是虚方法**（Python 的 `def` 也默认动态派发，这点心智一致）；`final` 方法/static 方法不参与多态。
- 接口实现：`class Foo implements Bar, Baz`，一个类可**实现多个接口**但只能**继承一个类**。
- Java 8 接口可写 `default` 方法（带实现），用「接口默认方法」模拟多继承，无 Python MRO，多接口同签名 default 方法必须重写消歧。

### 4.4 抽象类 vs 接口

| | 抽象类 `abstract class` | 接口 `interface` |
|---|---|---|
| 构造器 | 可以有 | 没有 |
| 字段 | 任意（含实例状态） | 只能 `public static final` 常量 |
| 方法 | 抽象 + 具体混合 | Java 8：抽象 + `default` + `static` |
| 继承数 | 单继承 | 可多实现 |
| Python 近似 | ABC 抽象基类 | Protocol / 纯抽象接口 |

选择惯例：只约定行为不带状态 → 接口；需要共享字段或构造逻辑 → 抽象类。

### 4.5 枚举（Java  enum 是「真」类）

```java
public enum FaultStatus {
    PENDING("pending"),
    DONE("done");                 // 最后一个常量后是分号

    private final String value;   // 枚举可以有字段、构造器、方法
    FaultStatus(String value) { this.value = value; }  // 构造器隐式 private
    public String getValue() { return value; }
    public static FaultStatus fromValue(String v) {    // 无自动反查，手写
        for (FaultStatus s : values()) {
            if (s.value.equals(v)) return s;
        }
        throw new IllegalArgumentException(v);
    }
}
```

与 Python `class Status(str, Enum)` 的关键差异：Java 枚举不「继承 str」，每个常量是**该枚举类的唯一实例（单例对象）**，可以带字段和方法，可用 `==` 比较（因为是单例），但**与字符串比较永远 `==` 为 false**，JSON 序列化对外文本默认是常量名大写（`PENDING`），要输出小写 value 需 Jackson `@JsonValue`（练习工程已实证）。

---

## 五、异常处理

### 5.1 语法骨架

```java
try {
    String line = Files.readAllLines(Paths.get("in.txt")).get(0);  // 会抛 IOException
    int x = Integer.parseInt(line);                                 // 会抛 NumberFormatException
} catch (NumberFormatException e) {          // 可多个 catch
    log.warn("bad number", e);
} catch (IOException | RuntimeException e) { // multi-catch（Java 7+）
    throw new IllegalStateException("wrap", e);  // 异常链：无裸 from 语法
} finally {
    cleanup();                               // 无论是否异常都执行
}

try (FileInputStream in = new FileInputStream(f)) {  // try-with-resources（Java 7+）
    ...                                       // 自动 close，≈ Python with
}
```

⚠️ multi-catch/受检异常 catch 有编译期可达性检查：try 体内**不可能抛出**该受检异常时，catch 它直接编译报错（「在相应的 try 语句主体中不能抛出异常错误」）——Python 的 `except` 从不这样拦你，见第十一节坑 19。

对照：`raise` → `throw`；`except` → `catch`；`with open(...)` → try-with-resources；裸 `from None` 抑制因果链的显式语法没有，Java 用构造器传入 cause 表达「异常链」。

### 5.2 受检异常：Java 独有，Python 没有

**受检异常（checked）**：继承 `Exception` 且非 `RuntimeException` 子类的异常，编译器**强制**你在方法签名 `throws` 声明或就地 catch，否则编译不过（`IOException`、SQLException 是典型）。

**非受检（unchecked）**：`RuntimeException` 子类（`NullPointerException`、`IllegalArgumentException`、`IndexOutOfBoundsException`）和 `Error`，无需声明。

| Python | Java |
|---|---|
| 所有异常都是显式 `raise`，调用方爱接不接 | 受检异常逼调用方表态：catch 或继续 throws |
| `try/except Exception` 一网打尽 | 同效果需 `catch (Exception e)`，但仍盖不住 Error |

受检异常在业界争议很大（代码噪音大），Spring 体系的做法是把受检异常包进 `RuntimeException`（如 `DataAccessException`）。练习阶段建议：**业务校验抛 `IllegalArgumentException`/`IllegalStateException`（unchecked）**，只有「调用方真的有能力恢复」的场景才设计受检异常。

### 5.3 自定义异常

```java
public class BusinessException extends RuntimeException {  // 继承 unchecked 更省心
    private final String code;
    public BusinessException(String code, String msg) {
        super(msg);
        this.code = code;
    }
    public String getCode() { return code; }
}
```

对照 FastAPI 的 `HTTPException(status_code, detail)`：Java 侧同样在 Service 层抛自定义异常，由 Web 层的全局异常处理器（Spring `@RestControllerAdvice`）统一转 JSON 响应——与你项目后端的 `app/exceptions.py` 同构。

---

## 六、集合与泛型

### 6.1 集合框架总览（对照 Python 内置容器）

```text
Collection
 ├── List   有序可重复   ArrayList（默认） LinkedList（两端操作）
 ├── Set    无序不可重复 HashSet（默认）  LinkedHashSet（保插入序） TreeSet（排序）
 └── Queue  队列        ArrayDeque（栈/队列都用它，不用 Stack）
Map（不属于 Collection）
 └── HashMap（默认）  LinkedHashMap（保序）  TreeMap（按键排序，≈ 有序 dict）
```

| Python | Java 等价 | 获取长度 |
|---|---|---|
| `[]` | `new ArrayList<>()` | `len()` vs `.size()` |
| `{}` set 字面量 | `new HashSet<>()`（无字面量） | |
| `{}` dict | `new HashMap<>()` | |
| 列表推导 | Stream `.collect(Collectors.toList())` | 见第七节 |
| `dict.get(k, default)` | `map.getOrDefault(k, def)` | |
| `setdefault` | `map.putIfAbsent(k, v)` / `computeIfAbsent` | |
| `sorted(lst, key=f)` | `lst.sort(Comparator.comparing(f))` | |

### 6.2 常用读写操作

```java
List<String> names = new ArrayList<>();
names.add("tom");
names.get(0);            // 越界抛 IndexOutOfBoundsException（≈ IndexError）
names.remove(0);         // 按下标删；删值用 remove(Object)
Map<String, Integer> age = new HashMap<>();
age.put("tom", 18);
age.getOrDefault("bob", 0);
for (Map.Entry<String, Integer> e : age.entrySet()) { ... }  // ≈ for k, v in dict.items()
```

空集合的不可变版本：Java 8 没有 `List.of()`（Java 9+），只有 `Collections.emptyList()` / `Collections.unmodifiableList(...)`。

### 6.3 泛型：编译期的容器说明书

```java
List<String> box = new ArrayList<>();   // 尖括号 = 这个容器只装 String
box.add("ok");
String s = box.get(0);                  // 取出无需强转（编译器知道是 String）
// box.add(1);                          // 编译报错——这就是泛型的价值
List<int[]> matrix = new ArrayList<>(); // 数组是对象，可以作为类型参数
List<int> bad = ...;                    // ❌ 基本类型不能当类型参数，写 List<Integer>
```

对照 Python：Python 的 `list[int]`（PEP 585 注解）**只是提示，运行时不拦你**；Java 泛型是**编译期强制**的类型契约（擦除后运行时其实也不检查，但编译器会拦住所有违规代码）。

常用通配符（只读 `? extends`，只写 `? super`，PECS 原则）：

```java
void printAll(List<?> list) { }                 // 接受任意元素类型的 List ≈ list[Any]
double sumAll(List<? extends Number> list) {}   // 能读 Number ≈ 协变（Python 的 list 是 invariant）
```

### 6.4 equals / hashCode 契约

作为 HashMap 键或 HashSet 元素的类**必须**同时重写 `equals` 和 `hashCode`：`a.equals(b)` 为真 ⇒ `a.hashCode() == b.hashCode()`。只写 equals 不写 hashCode，会出现「放进去取不出来」的经典 bug（IDE/Lombok 生成时两个一起勾）。

---

## 七、函数式编程：Lambda 与 Stream

### 7.1 Lambda 与函数式接口

```java
// Java 的 Lambda 必须「面向接口」：目标类型是一个函数式接口（只有一个抽象方法）
Runnable r = () -> System.out.println("hi");          // ≈ lambda: print("hi")
Function<String, Integer> len = s -> s.length();      // ≈ lambda s: len(s)
BiFunction<Integer, Integer, Integer> add = (x, y) -> x + y;
Predicate<String> notEmpty = s -> !s.isEmpty();
// 单表达式自动 return；多语句要写 {} 和显式 return
// 捕获的局部变量必须是 effectively final（不能在 Lambda 之后又改它）
```

| Python | Java |
|---|---|
| `def f(x): ...` 随便当值传 | 方法不能单独传递，必须包成接口实例 |
| `lambda x: x+1` | `x -> x + 1`，且上下文必须声明函数式接口类型 |
| 内置 `Function` 概念 | 四大件：`Function<T,R>`、`Predicate<T>`、`Consumer<T>`、`Supplier<T>` |

方法引用是 Lambda 的简写：`String::length` ≈ `s -> s.length()`，`User::new` ≈ 构造器引用。

### 7.2 Stream：Java 的列表推导

Stream 一次性消耗，不可复用；惰性求值（中间操作不触发计算，碰到终端操作才跑）。

```java
List<String> result = users.stream()
        .filter(u -> u.getAge() >= 18)                 // ≈ [u for u in users if ...]
        .sorted(Comparator.comparing(User::getAge)     // ≈ sorted(key=...)
                             .reversed())
        .map(User::getName)                            // ≈ 表达式改写部分
        .distinct()
        .limit(10)
        .collect(Collectors.toList());
```

| Python 推导式 | Java Stream 等价 |
|---|---|
| `[f(x) for x in lst]` | `lst.stream().map(f).collect(toList())` |
| `[x for x in lst if p(x)]` | `.filter(p)` |
| `any(p(x) for x in lst)` | `.anyMatch(p)` |
| `all(...)` | `.allMatch(p)` |
| `sum(...)` | `.mapToLong(...).sum()` 或 `Collectors.summingInt` |
| `sorted(..., key=...)` | `.sorted(Comparator.comparing(...))` |
| `groupby`（标准库更重） | `Collectors.groupingBy(classifier)` |
| `"".join(...)` | `.collect(Collectors.joining(", "))` |
| `enumerate` | 无直接等价，用 IntStream.range 或老实写循环 |

### 7.3 Optional：安全的「可能为 null」

```java
Optional<User> u = findUser(id);
String name = u.map(User::getName).orElse("anonymous");  // ≈ name or "anonymous"
u.ifPresent(x -> log.info("{}", x));
u.orElseThrow(() -> new NotFoundException(id));          // ≈ raise
// ❌ 不要用 u.get()（等价裸访问 null）；❌ Optional 不当方法参数/字段类型，只当返回值
```

对照 Python：`x or default`、`x?.attr ?? default`（其他语言）；Java 没有空安全语法糖，`Optional` 是**显式把「可能没有」编码进返回值类型**的约定，作用近似 Rust/TS 的 `Option`/`?`。

---

## 八、字符串与 IO

### 8.1 字符串 API 对照

| Python | Java | 备注 |
|---|---|---|
| `len(s)` | `s.length()` | |
| `s[0]` / `s[1:3]` | `s.charAt(0)` / `s.substring(1, 3)` | 左闭右开一致 |
| `"x" in s` | `s.contains("x")` | |
| `s.split(",")` | `s.split(",")` | ⚠️ Java 参数是**正则**，split("\\.") 要点转义 |
| `",".join(lst)` | `String.join(",", lst)`（Java 8+） | 方向反了：分隔符在前 |
| `s.strip()` | `s.trim()`；Java 11 才有 `strip()` | trim 不去全角空格 |
| `s.lower()/upper()` | `toLowerCase()/toUpperCase()` | 土耳其 locale 坑：业务场景建议带 `Locale.ROOT` |
| `s.startswith()` | `s.startsWith()` | |
| `f"{name}!"` | `String.format("%s!", name)` 或 `new StringBuilder` | Java 8 无 f-string / 文本块 |
| `s.replace` | `replace`（字面量）/ `replaceAll`（正则） | |
| 多行三引号 | 无（Java 15+ 文本块 `"""`），用 `+ "\n"` 拼接 | |

### 8.2 字符串拼接与 StringBuilder

字符串不可变：`str += "x"` 循环 n 次会创建 n 个中间对象（Python 同写法 VM 有优化，Java 没有）。循环拼接必须 `StringBuilder`：

```java
StringBuilder sb = new StringBuilder();
for (String p : parts) { sb.append(p).append(','); }
String out = sb.toString();
```

### 8.3 文件读写

```java
// 读全部文本行（Java 7+ NIO.2，日常首选）
List<String> lines = Files.readAllLines(Paths.get("data.txt"), StandardCharsets.UTF_8);
// 逐行流式读（大文件）
try (Stream<String> stream = Files.lines(Paths.get("big.txt"))) {
    stream.filter(l -> !l.isEmpty()).forEach(this::handle);
}  // 自动关闭 ≈ Python with open(...)
// 写文件
Files.write(Paths.get("out.txt"), "done\n".getBytes(StandardCharsets.UTF_8));
// 老式 IO（理解用）：InputStream/OutputStream 字节流，Reader/Writer 字符流，装饰器模式层层包
```

路径类：`Path`/`Paths`（新，推荐）与 `File`（旧，仍大量见于存量代码）。`os.path` 的 join/exist/isfile 对应 `Paths.get(...).resolve(...)`、`Files.exists(...)`、`Files.isDirectory(...)`。

---

## 九、并发基础

### 9.1 线程创建

```java
// 方式一：实现 Runnable（推荐，任务与线程解耦）
Thread t = new Thread(() -> System.out.println("working in " + Thread.currentThread().getName()));
t.start();                    // 注意是 start() 不是 run()：run() 只是当前线程直接调用
t.join();                     // 等它结束

// 方式二：Callable + Future（有返回值 / 可抛异常）
ExecutorService pool = Executors.newFixedThreadPool(4);
Future<Integer> fut = pool.submit(() -> heavyCompute());
Integer result = fut.get(3, TimeUnit.SECONDS);   // 带超时，≈ asyncio.wait_for
pool.shutdown();
```

| Python | Java |
|---|---|
| GIL：多线程不并行 CPU，适合 IO | **真多线程**，多核并行；代价是共享内存要自己同步 |
| `asyncio` 单线程事件循环为主流并发模型 | 主流是**线程池阻塞式**（每个请求一个线程，Spring MVC 默认模型）；WebFlux/虚拟线程(Java 21)才是异步模型 |
| `threading.Lock` | `synchronized` 关键字（方法/代码块级锁，JVM 内置） |
| 无语言级原子类型 | `AtomicInteger` 等 CAS 原子类；`ConcurrentHashMap` |
| 队列 `queue.Queue` | `BlockingQueue`（生产者消费者标准件） |

### 9.2 同步最小知识

```java
public class Counter {
    private int n;
    public synchronized void inc() { n++; }   // 实例方法加锁：同一实例串行
    // n++ 非原子：读-改-写三步，多线程下会丢更新——这是竞态条件的入门例子
}
```

初学阶段记住三件事：**共享可变状态是万恶之源**（能用局部变量/不可变对象就不用锁）；`synchronized` 是兜底手段；优先用 `java.util.concurrent` 现成组件而不是手写 wait/notify。

---

## 十、Maven 与 Spring Boot 生态对照

### 10.1 Maven：Java 的 pip + venv + pyproject.toml 三合一（ minus the venv）

`pom.xml` ≈ `pyproject.toml` 的依赖声明部分：

```xml
<dependencies>
  <dependency>
    <groupId>com.fasterxml.jackson.core</groupId>   <!-- 组织，≈ PyPI 包命名空间 -->
    <artifactId>jackson-databind</artifactId>        <!-- 包名 -->
    <version>2.13.5</version>                        <!-- 版本（无兼容的 ^/~ 语义，写死） -->
    <scope>test</scope>                              <!-- 仅测试期可见，≈ dev-dependencies -->
  </dependency>
</dependencies>
```

| Python 生态 | Java 生态 | 说明 |
|---|---|---|
| `pip install` | `mvn dependency:resolve` / IDE 自动 | 声明驱动，不裸装 |
| `requirements.txt` / `uv.lock` | `pom.xml` 直接写版本 + 依赖树仲裁 | Maven 默认「最近者优先」，无锁文件文化 |
| `site-packages` 每 venv 一份 | `~/.m2/repository` **全局共享** | Java 没有虚拟环境，依赖冲突靠坐标+版本仲裁 |
| `pip show` / `pipdeptree` | `mvn dependency:tree` | 排冲突的标准命令 |
| wheel/sdist | jar | 构件格式 |
| PyPI | Maven Central | 中央仓库 |

### 10.2 目录约定（强约束，非推荐）

```text
src/main/java/com/example/app/   生产代码（目录 = package 声明，违反编译报错）
src/main/resources/              配置文件（application.yml ≈ .env/settings）
src/test/java/...                测试代码（镜像主代码包结构）
target/                          构建产物（≈ dist/ + __pycache__，gitignore）
```

对比 Python「目录结构自由」，Maven 是「**约定优于配置**」的极端：目录放错，构建工具根本找不到你的代码。

### 10.3 Spring Boot ≈ FastAPI 的生态位

| FastAPI 概念 | Spring Boot 对应 | 练习工程已实证 |
|---|---|---|
| `@app.post("/faults")` | `@RestController` + `@PostMapping("/faults")` | |
| Pydantic schema + 自动校验 | DTO（POJO）+ Bean Validation（`@NotBlank`/`@Size`，Hibernate Validator） | ✅ pom 已引 hibernate-validator |
| `Depends(get_db)` | `@Autowired` 构造器注入（IoC 容器管理一切生命周期） | |
| `app.include_router` | 包扫描：`@Component` 注解的类自动注册 | |
| uvicorn 单进程起服务 | `SpringApplication.run(...)` 内嵌 Tomcat，打成一个可执行 jar | |
| 全局 exception handler | `@RestControllerAdvice` + `@ExceptionHandler` | |
| `Swagger UI` 自带 | 需 springdoc-openapi 插件 | |

最大心智差异：FastAPI 是「显式装配、函数式」，Spring 是「**注解驱动、容器托管**」——你写的类被框架扫描、实例化、注入、代理（AOP），代码流向由框架掌控（控制反转）。入门期最困惑的「我的对象是谁 new 出来的」问题的答案永远在容器里。

### 10.4 版本路线提醒

练习基座是 **Java 8 + Spring Boot 2.7（javax 命名空间）**。企业存量大量是这一代；新立项则常见 Java 17/21 + Boot 3（jakarta 命名空间、record、var、文本块、List.of 等）。本手册凡 Java 8 不可用的语法均已标注，升级语言版本时按标注回看即可。

---

## 十一、坑点汇总

1. **`==` 比较字符串**：`==` 比引用，`equals()` 比内容。`"ab" == "a" + "b"` 可能为 true（字面量常量池）而 `new String("ab") == "ab"` 必为 false——最阴险的是它对一半，靠运气写代码。Java 枚举例外：常量是单例，`==` 安全且是推荐写法。
2. **`null` 陷阱**：`str.equals("x")` 在 str 为 null 时 NPE。铁律：字面量在前 `"x".equals(str)`，或用 `Objects.equals(a, b)`；方法返回集合用空集合不用 null（`Collections.emptyList()`）。
3. **负数除法与取模**：`-7 / 2 == -3`（向零截断，Python 是 -4）、`-7 % 2 == -1`（符号跟被除数，Python 恒非负）。分页、取模散列要特别注意。
4. **整数溢出静默回绕**：`int * int` 超 2³¹-1 不报错直接变负数。大数场景显式 `long` 字面量（`100_000L * 100_000`）。
5. **浮点数不精确**：`0.1 + 0.2 != 0.3`（IEEE754，Python 同款问题，但 Java 业务代码更常撞金钱场景）。钱用 `BigDecimal` 或分为单位存 `long`。
6. **数组直接打印**：`System.out.println(arr)` 输出 `[I@1b6d3586`，必须 `Arrays.toString(arr)`；二维用 `Arrays.deepToString`。
7. **`Arrays.asList` 半可变**：返回的视图能 set 不能 add/remove（UnsupportedOperationException），想当 List 用要 `new ArrayList<>(Arrays.asList(...))`。
8. **遍历时修改集合**：`for (x : list) { list.remove(x); }` 抛 ConcurrentModificationException。用 `Iterator.remove()` 或 `list.removeIf(pred)`。
9. **只改 equals 不改 hashCode**：对象进 HashMap 后取不出来。两个永远一起重写。
10. **HashMap 键用可变对象**：put 之后改字段 → hash 变了 → 元素「失踪」。作键的类最好不可变（final 字段）。
11. **switch 忘 break 静默穿透**：是特性也是事故源头，每个分支显式 break 或刻意的 fallthrough 加注释。
12. **Lambda 捕获可变局部变量**：捕获后不能再改（编译报错），别在循环里改被闭包引用的变量。
13. **Stream 复用**：终端操作后再用同一 stream 抛 IllegalStateException，Stream 是一次性管道不是集合。
14. **`Thread.start()` 写成 `run()`**：run() 同步执行，「线程」无声失效，极难排查。
15. **受检异常 catch 后吞掉**：`catch (Exception e) {}` 空块 = 事故掩埋，至少记日志。
16. **Java 版本语法混用**：在 JDK 8 工程里写 `var`、`List.of`、文本块、switch 表达式，IDE 可能不拦（源码级别配置宽松时），CI 编译才爆——本手册所有「Java 8 不可用」标注即为防雷清单。
17. **文件名/public 类名不一致**：编译报错「类 XXX 是公共的，应在名为 XXX.java 的文件中声明」；一个 .java 只放一个 public 类是铁律。
18. **包声明与目录不符**：Python 放哪都能 import，Java 目录必须逐段对应 `package`，放错直接编译失败。
19. **catch 了 try 里抛不出的受检异常**：Java 编译器会检查 catch 可达性，try 体内没有任何语句能抛出该受检异常时，`catch (IOException e)` 直接编译报错（本文示例初稿就撞过此坑，javac 1.8 实测）；`catch RuntimeException/Error` 及其子类不受此限，因为它们可能从任意位置抛出。

---

## 十二、速查表

### 12.1 命令速查（Windows PowerShell）

| 操作 | 命令 |
|---|---|
| 查编译/运行版本 | `java -version` ; `javac -version` |
| 编译单文件 | `javac -encoding UTF-8 -d out Hello.java` |
| 运行 | `java -cp out Hello` |
| 编译带依赖 | `javac -cp "lib/*" -d out src/*.java` |
| 打 jar | `jar cfe app.jar com.example.Main -C out .` |
| 运行 jar | `java -jar app.jar` |
| 反编译看字节码 | `javap -c com.example.Main` |
| Maven 构建 | `mvn clean package`（≈ build + 打包） |
| Maven 测试 | `mvn test`（≈ pytest） |
| 依赖树 | `mvn dependency:tree`（≈ pipdeptree） |
| 强制刷新依赖 | `mvn -U clean install` |

### 12.2 语法差异快查

| 我想… | Python | Java |
|---|---|---|
| 定义常量 | `MAX = 100` 约定 | `static final int MAX = 100` 强制 |
| 打印 | `print(x)` | `System.out.println(x)`（IDE 缩写输入 `sout`/`sysout`） |
| 读输入 | `input()` | `new Scanner(System.in).nextLine()` |
| f-string | `f"{a}-{b}"` | `String.format("%s-%s", a, b)` 或 `a + "-" + b` |
| 三元 | `x if c else y` | `c ? x : y` |
| 判空合并 | `v or default` | `Objects.requireNonNullElse(v, default)`（Java 9+）→ Java 8 写 `v != null ? v : default` |
| 枚举遍历 | `for s in Status` | `for (Status s : Status.values())` |
| 类型注解 | `def f(x: int) -> str` | `public String f(int x)`（类型写在签名上） |
| 默认参数 | `def f(a=1)` | 重载两个方法 / Builder |
| 多返回值 | `(a, b)` tuple | 自定义小类/record（Java 16+）/ `Map.Entry` 凑 |
| `is None` | `x is None` | `x == null`（null 只能用 ==/!= 比） |
| isinstance | 同 | `if (obj instanceof User) { User u = (User) obj; }`（模式匹配 `instanceof User u` 是 Java 16+，Java 8 要手写强转） |
| with 语句 | `with open(...) as f` | `try (InputStream f = ...) { }` try-with-resources |
| 装饰器 | `@decorator` | 有注解 `@Override/@Autowired` 但**机制不同**：注解本身无行为，靠框架反射处理 |
| 生成器 yield | `yield` | 无等价物；用 `Iterator`/`Stream`（惰性）近似 |
| `__name__ == "__main__"` | 模块即入口 | `public static void main(String[] args)` 全工程唯一入口签名 |

### 12.3 常用类「身份」速查

| Java 类 | 一句话身份 | Python 熟脸 |
|---|---|---|
| `Objects` | equals/hash/requireNonNull 静态工具箱 | 内置函数散落在 `operator`/`typing` |
| `Arrays` | 数组的 sort/toString/fill/copyOf | 列表方法 + `len()` |
| `Collections` | 集合工厂/不可包装/算法 | `itertools` 部分 + 空容器 |
| `Optional` | 「可能没有」的类型化表达 | `x or None` 链条的显式版 |
| `StringBuilder` | 可变字符串 | list of str 攒完 join |
| `BigDecimal` | 精确十进制 | `decimal.Decimal` |
| `LocalDate/LocalDateTime` | Java 8 新日期 API（不可变） | `datetime.date/datetime` |
| `DateTimeFormatter` | 线程安全格式化 | `strftime` 但模式串不同（`yyyy-MM-dd`） |
| `Stream/Collectors` | 声明式集合管道 | 推导式 + `functools` + `itertools` |
| `ExecutorService` | 线程池 | `concurrent.futures.ThreadPoolExecutor` |
| `CompletableFuture` | 可编排异步链 | `asyncio` Future/Task 的线程版 |
| `Pattern/Matcher` | 正则 | `re` 模块，但**默认 Unicode 行为不同**且 `matches()` 是全匹配不是 search |
