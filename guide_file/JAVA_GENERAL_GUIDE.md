# Java 通用完整手册

> 适用版本：**JDK 1.8**（本机 `C:\Program Files\java\jdk1.8.0_121`，文中所有 Java 8 代码示例已经本机 `javac 1.8` 编译验证）。凡 JDK 9+ 才引入的语法与 API 均标注引入版本，未标注即 Java 8 可直接使用。
> 定位：不预设任何编程语言背景的 Java 完整学习手册——语言核心、面向对象、集合、函数式、IO、并发、工程化全景。面向 Python 开发者的对照速成版见 [JAVA_GUIDE.md](JAVA_GUIDE.md)。
> 可信度标注：「实测」= 已用本机 JDK 1.8 编译验证；其余为 Java 语言规范与官方文档行为。盲区补齐新增小节（3.4、4.6、7.2、11.5、16.4、19.5 及 18.2/21 节新增段落）的示例已经本机 JDK 1.8 编译**并运行**验证（含 final 重赋值编译报错、assert 默认关闭两项负向验证）。

---

## 目录

1. [Java 是什么，为什么长这样](#一java-是什么为什么长这样)
2. [环境与工具链](#二环境与工具链)
3. [程序的基本构造](#三程序的基本构造)
4. [类型系统与运算符](#四类型系统与运算符)
5. [流程控制](#五流程控制)
6. [数组](#六数组)
7. [面向对象](#七面向对象)
8. [继承、多态与抽象](#八继承多态与抽象)
9. [枚举、接口进阶与内部类](#九枚举接口进阶与内部类)
10. [异常处理](#十异常处理)
11. [集合框架](#十一集合框架)
12. [泛型](#十二泛型)
13. [Lambda 与函数式接口](#十三lambda-与函数式接口)
14. [Stream API](#十四stream-api)
15. [Optional 与空值安全](#十五optional-与空值安全)
16. [字符串与文本处理](#十六字符串与文本处理)
17. [日期时间（java.time）](#十七日期时间javatime)
18. [文件与 IO](#十八文件与-io)
19. [并发编程](#十九并发编程)
20. [模块化与包管理：Maven](#二十模块化与包管理maven)
21. [测试：JUnit](#二十一测试junit)
22. [生态导航：从 SE 到企业开发](#二十二生态导航从-se-到企业开发)
23. [语言版本演进速览（8→21）](#二十三语言版本演进速览821)
24. [坑点汇总](#二十四坑点汇总)
25. [速查表](#二十五速查表)

---

## 一、Java 是什么，为什么长这样

### 1.1 一次编译，到处运行

Java 源码（`.java`）先被编译器 `javac` 编译成**字节码**（`.class`），字节码不面向任何具体 CPU，而是面向 **JVM（Java 虚拟机）**。哪个平台装了 JVM，同一份字节码就能在哪跑——这就是「Write Once, Run Anywhere」的实现机制：不是操作系统直接懂 Java，而是**每个平台各有一个 JVM 说同一种字节码语言**。

对你实际的意义：

- 项目里出现的 `java`（运行）与 `javac`（编译）是两个不同的程序，别混淆；
- 字节码跑起来后由 JVM 的 JIT 编译器即时翻译成机器码，性能接近原生，且有**垃圾回收器**自动管理内存——你不需要手动释放任何对象。

### 1.2 静态强类型

每个变量在声明时就定死类型，之后只能存放该类型的值；类型不匹配是**编译错误**，根本到不了运行阶段。好处是绝大多数低级错误在写代码时就被拦下，坏处是要多写声明。后文会看到 `var`（Java 10+）等形式上的简化，但静态类型的本质从未改变。

### 1.3 语法风格

Java 采用 C 系家族语法：语句以分号结尾、代码块用大括号 `{}` 包裹、关键字为小写英文单词。**缩进不产生语义**（只影响可读性），这一点与「靠缩进划分代码块」的语言截然不同。

### 1.4 版本号地图（先记住三档）

| 档位 | 代表 | 现状 |
|---|---|---|
| Java 8（2014） | Lambda/Stream 诞生 | **存量企业项目霸主**，大量系统至今停在 8 |
| Java 11 / 17 | 首批两个 LTS | 新建项目主流，17 是当前企业最常见 LTS |
| Java 21（2023） | 最新流行 LTS，虚拟线程 | 新项目升级目标 |

本手册以 **Java 8 为已验证基线**，新语法逐一标注引入版本（详见第二十三节演进速览）。

---

## 二、环境与工具链

### 2.1 JDK / JRE / JVM

| 名词 | 含义 | 你需要装哪个 |
|---|---|---|
| JVM | 执行字节码的虚拟机 | 随 JDK 附带 |
| JRE | JVM + 核心类库（只能运行，不能编译） | 已停发独立版（Java 11 起），不用管 |
| JDK | 开发全家桶：编译器 + 工具 + JRE | **装这个** |

Java 8 常见免费发行版：Amazon Corretto、Eclipse Temurin、Oracle JDK（开发用途免费）。发行版之间跑同一份字节码行为一致，选主流任意一家即可。

### 2.2 安装与验证（Windows）

1. 下载 JDK 8 ZIP 或安装包（如 Corretto 1.8）；
2. 设置环境变量 `JAVA_HOME` 指向 JDK 目录，把 `%JAVA_HOME%\bin` 加入 `Path`；
3. 新开终端验证：

```powershell
java -version    # openjdk version "1.8.0_xxx"
javac -version   # javac 1.8.0_xxx
```

本机实测存在：`C:\Program Files\java\jdk1.8.0_121`（主用）与 `C:\Users\<you>\.jdks\corretto-1.8.0_392`（IDE 自动下载）。

### 2.3 最小编译运行闭环

在 `Hello.java` 中写入（**文件名必须与 public 类名完全一致**，这是编译器强制的）：

```java
public class Hello {
    public static void main(String[] args) {
        System.out.println("Hello, Java");
    }
}
```

两步走：

```powershell
javac -encoding UTF-8 -d out Hello.java   # 编译：源码 -> out/Hello.class
java -cp out Hello                        # 运行：指定类路径 + 类名（不带 .class 后缀）
```

`-encoding UTF-8` 在源码含中文时必须加（Java 8 的 javac 默认跟随系统区域编码，中文 Windows 上是 GBK，会乱码或报错）；`-cp`（classpath）告诉 JVM 去哪里找类。

### 2.4 IDE

实际开发几乎不会裸用 javac。主流选择：**IntelliJ IDEA**（社区版免费，事实标准）、Eclipse（存量项目多）、VS Code + Java 扩展包（轻量）。IDE 负责：增量编译、错误即时提示、依赖同步、重构、调试。本手册的语法知识与 IDE 无关。

---

## 三、程序的基本构造

### 3.1 包与 import

```java
package com.example.app;        // 声明包：必须与目录结构逐段对应
import java.util.List;          // 导入单个类
import java.util.*;             // 通配导入（省 keystroke，大型项目慎用）
```

- `package` 是第一行（注释之后）的语句；`com/example/app/` 目录必须真实存在，放错直接编译失败。
- 包名倒写域名是行业惯例（`com.example.xxx`），作用是全局防重名。
- `java.lang` 包（String、System、Math 等）自动导入，无需书写。

### 3.2 标识符与命名惯例

- 合法标识符：字母/`_`/`$`/数字开头（数字不能在首位），区分大小写，关键字保留。
- 社区铁律级惯例：**类名** `PascalCase`、**方法与变量** `camelCase`、**常量** `UPPER_SNAKE_CASE`、**包名**全小写。违反不会报错，但会让所有 Java 同事侧目。

### 3.3 注释与入口

```java
// 单行注释
/* 块注释 */
/** Javadoc：给工具生成 API 文档用，写在类/方法上方 */
```

每个可运行程序都有一个 `public static void main(String[] args)`——JVM 启动后调用它作为起点，`args` 接收命令行参数。

### 3.4 注解与可变参数

**注解（Annotation）**是以 `@` 开头的元数据标记，本身不执行任何逻辑，给编译器或框架「读」：

```java
@Override                          // 告诉编译器：校验我确实覆盖了父类/接口方法，拼错即报错
public String toString() { return "..."; }

@FunctionalInterface               // 声明「这是函数式接口」，编译器校验恰好一个抽象方法（第十三节）
interface Task { void run(); }
```

注解分两类去向：**编译期**被编译器消费后丢弃（`@Override`、`@SuppressWarnings`）；**运行期**保留在字节码里，由框架反射读取驱动行为（Spring 的 `@Service`、JUnit 的 `@Test`，见第二十一、二十二节）——「注解怎么就生效了」的答案永远在「谁在读它」。自定义注解用 `@interface` 声明，入门期会读会用即可。

**可变参数（varargs）**让方法接受「零到多个」同类型实参，写法是类型后跟 `...`：

```java
static int sum(int... nums) {      // 编译器把 nums 当 int[] 处理
    int total = 0;
    for (int n : nums) total += n;
    return total;
}
sum();                             // 0 个实参也行
sum(1, 2, 3);                      // 等价于 sum(new int[]{1, 2, 3})
String.format("%s-%d", name, 42);  // format 的第二个参数就是 Object...，所以能跟任意多个值
```

规则：一个方法**最多一个**可变参数，且必须放在参数列表**最后一位**。

---

## 四、类型系统与运算符

### 4.1 八种基本类型

| 类型 | 位宽 | 范围/精度 | 默认值（字段） | 包装类 |
|---|---|---|---|---|
| `byte` | 8 | -128~127 | 0 | Byte |
| `short` | 16 | ±32767 | 0 | Short |
| `int` | 32 | 约 ±21 亿 | 0 | Integer |
| `long` | 64 | ±9.2×10¹⁸ | 0L | Long |
| `float` | 32 | 约 7 位有效数字 | 0.0f | Float |
| `double` | 64 | 约 15 位有效数字 | 0.0d | Double |
| `char` | 16 | 一个 UTF-16 码元 | '\u0000' | Character |
| `boolean` | — | true / false | false | Boolean |

选择惯例：整数用 `int`，超范围或时间戳用 `long`；小数一律 `double`（`float` 几乎不用）；字符 `'c'` 单引号，字符串是 `String` 类（**不是基本类型**，大写 S）。

字面量后缀：`long big = 100_000L;`（下划线分隔符 Java 7+）、`float f = 1.5f;`（不加 f 则 1.5 按 double 处理，编译报错）。

### 4.2 引用类型与 null

除八种基本类型外，一切（数组、字符串、自定义类）都是**引用类型**：变量存的不是对象本身，而是「指向堆上对象的引用」。引用变量可以是 `null`（什么都不指向），对 null 调用方法会抛 `NullPointerException`——Java 最常见的运行时异常，第十五节专门讲防御手段。基本类型不可能为 null（`int x = null` 编译不过，只能赋给 `Integer`）。

### 4.3 类型转换

```java
int a = 7;
long autoWiden = a;              // 小 -> 大：自动提升，安全
int back = (int) 3.99;           // 大 -> 小：强制转换，直接截断为 3（不四舍五入）
double r = (double) 7 / 2;       // 3.5：先转再除

int parsed = Integer.parseInt("42");        // 字符串 -> 数字（各包装类各有 parseXxx）
double d = Double.parseDouble("3.14");
String s1 = String.valueOf(42);             // 数字 -> 字符串
String s2 = 42 + "";                        // 也能行但不专业
long t = 5L * Integer.MAX_VALUE;            // long 参与运算才不溢出；int*int 先溢出再赋值就晚了
```

### 4.4 运算符要点

| 类别 | 要点 |
|---|---|
| 算术 | 两个 int 相除结果仍是 int（`7 / 2 == 3`，截断向零）；取模 `%` 结果**符号跟随被除数**（`-7 % 2 == -1`） |
| 比较 | `==`/`!=` 用于基本类型比值，用于引用比**是否同一对象**；字符串等内容比较必须 `.equals()`（坑点 1） |
| 逻辑 | `&&` `\|\|` 短路（左边定胜负就不算右边）；`&` `|` 不短路，日常几乎只用短路版 |
| 三元 | `cond ? x : y`，Java 没有「and/or 返回操作数」的写法，判断真值只能用 boolean，`if (str)` 非法，必须 `if (str != null)` |
| 自增 | `i++` 后置取值再自增，`++i` 先自增；独立成句时二者等价，混在大表达式里尽量用 `++i` 少绕脑 |
| 溢出 | 整型运算超范围**静默回绕**不报错；怀疑溢出用 `Math.addExact`（Java 8+，超范围抛异常）探测 |
| 优先级 | 记不全就加括号，Java 的 `+`（拼接）与 `==` 优先级差异会制造 `1 + 2 == 3` 为 true 这类意外 |

### 4.5 布尔与条件

Java 的条件表达式**必须是 boolean**，不存在「0/空串/空集合算假」的隐式真值。判空串要写 `!s.isEmpty()`，判空集合 `!list.isEmpty()`——这条纪律消灭了一大类隐蔽 bug。

### 4.6 自动装箱与拆箱

基本类型与对应包装类（4.1 表格最后一列）之间的自动转换：**装箱** = 基本类型 → 包装类对象，**拆箱** = 反向。编译器在需要时自动插入转换代码：

```java
Integer boxed = 42;                // 自动装箱：等价于 Integer.valueOf(42)
int unboxed = boxed;               // 自动拆箱：等价于 boxed.intValue()
List<Integer> list = new ArrayList<>();
list.add(1);                       // 泛型只装引用类型（第十二节），int 自动装箱成 Integer 才能进集合
int x = list.get(0);               // 取出时自动拆箱
```

三个必须知道的代价与坑：

- **性能**：装箱每次可能创建对象，循环里大量 `Integer` 累加是隐蔽的性能坑，热点路径用基本类型或 `IntStream`（第十四节）。
- **拆箱 NPE**：`Integer n = null; int x = n;` 运行时抛 NullPointerException——包装类可为 null（4.2），拆箱瞬间爆。
- **`==` 缓存陷阱**：`Integer.valueOf` 对 -128~127 缓存复用同一对象，所以 `Integer a = 127, b = 127; a == b` 为 true，换成 128 就是 false——比较内容一律 `.equals()`（与坑点 1 同源）。

---

## 五、流程控制

```java
// if / else if / else —— 条件必须带括号
if (score >= 90)      { grade = 'A'; }
else if (score >= 60) { grade = 'B'; }
else                  { grade = 'C'; }

// while / do-while
while (queue.peek() != null) { work(queue.poll()); }
do { attempt++; } while (attempt < 3 && !success);

// for 三段式：初始化; 条件; 步进 —— i 的作用域仅限循环体
for (int i = 0; i < n; i++) { ... }
for (int i = n - 1; i >= 0; i--) { ... }          // 倒序标准写法

// 增强 for（for-each）：遍历数组或任何可迭代对象，拿不到下标
for (String name : names) { System.out.println(name); }

// 标签 + break/continue：跳出多层循环（低频但必要时的正解，用则加注释）
outer:
for (int i = 0; i < m; i++)
    for (int j = 0; j < n; j++)
        if (hit(i, j)) break outer;
```

### switch（传统形式）

```java
switch (day) {
    case 1: case 2: case 3:            // 穿透：多个 case 共享一段逻辑
        meeting(); break;              // 每个分支末尾的 break 不能忘（坑点 11）
    case 4:
        report(); break;
    default:
        rest();
}
```

支持 `byte/short/int/char/String`（String 自 Java 7）/枚举。**case 必须是编译期常量**。switch 表达式（`case A -> ...` 箭头语法、可取值）是 Java 14 标准化的新形态，Java 8 不可用，详见第二十三节。

---

## 六、数组

数组是**定长**的同类型容器，创建后长度不可改变：

```java
int[] arr = new int[5];              // 长度 5，元素自动填默认值 0
int[] nums = {3, 1, 4, 1, 5};        // 声明即初始化的简写
nums.length                          // 长度是属性不是方法（无括号）
nums[0]; nums[4] = 9;                // 下标从 0；越界抛 ArrayIndexOutOfBoundsException

Arrays.sort(nums);                   // 原地升序 -> [1, 1, 3, 4, 5]
Arrays.toString(nums);               // 转可读字符串；直接打印数组得到 "[I@1b6d3586"（坑点 6）
Arrays.fill(arr, -1);                // 全部填充
Arrays.equals(a, b);                 // 按内容比较（== 只比是不是同一个数组对象）
int[] grown = Arrays.copyOf(nums, 10);   // 扩容=复制到新数组

int[][] grid = new int[3][4];        // 二维数组 = 数组的数组，每行列数可不同
```

实务定位：数组性能最好但太原始——长度不可变、没有集合操作。**业务代码默认用 `ArrayList`（第十一节）**，数组留给「确定长度、追求性能、与方法签名/底层 API 打交道」的场合。

---

## 七、面向对象

### 7.1 一个完整的类

```java
public class User {
    private String name;                  // 字段：必须先声明（类型 + 名字 + 访问修饰符）
    private int age;
    private static int count = 0;         // 静态字段：属于类，所有实例共享一份

    public User(String name) {            // 构造器：方法名 = 类名，无返回类型
        this(name, 0);                    // 调用同类另一构造器（必须放第一行）
        this.name = name;
    }

    public User(String name, int age) {   // 重载：同名不同参数列表
        this.name = name;
        this.age = age;
        count++;
    }

    public String getName() { return name; }        // getter 惯例
    public void setName(String name) { this.name = name; }  // setter 惯例

    public boolean isAdult() {            // 实例方法
        return age >= 18;
    }

    public static int getCount() { return count; }  // 静态方法：不依赖实例，用类名调用

    @Override
    public String toString() {            // 所有类都从 Object 继承的「自我介绍」方法
        return "User(name=" + name + ", age=" + age + ")";
    }
}
```

使用：

```java
User u = new User("Alice", 20);   // new 在堆上创建对象，u 持有引用
User.count                        // 不建议，走 getCount()
```

要点：

- **字段声明在类顶部**，不能在使用处随手创建；`this` 指当前实例（可省略，同名遮蔽时必须写）。
- **访问修饰符**：`private` 仅本类、（不写）包内可见、`protected` 子类+包内、`public` 处处可见。封装的标准姿势：字段 private + 公开 getter/setter。
- Java **没有属性语法**（`u.name` 直读字段），一切访问走方法。样板代码量大，IDE 一键生成或 Lombok（`@Data`）消除，见第二十二节。
- **类级常量**写 `public static final int MAX = 100;`——`static` 与 `final` 各管什么，见下一小节 7.2。

### 7.2 static 与 final：两个「归属/不可变」修饰符

**`static` = 属于类本身，不属于任何实例**：

- 静态字段全类共享一份（7.1 的 `count`），静态方法不依赖实例、用类名直接调（`User.getCount()`）；
- 静态上下文（静态方法/静态块）里**没有 `this`**，不能直接访问实例字段与方法——「为什么静态方法里不能调普通方法」的答案就在这；
- 静态块在类加载时执行一次（7.4）。

**`final` = 「到此为止，不许再变」**，可修饰三种东西：

| 修饰对象 | 含义 | 例子 |
|---|---|---|
| 变量/字段 | 只能赋值一次，之后不能重新赋值 | `final int x = 10; x = 20;` 编译报错 |
| 方法 | 子类不能覆盖（override）它 | 8.1 要点 |
| 类 | 不能被继承 | `String` 就是 final 类 |

```java
final int x = 10;
x = 20;                            // 编译错误：cannot assign a value to final variable x

final List<String> list = new ArrayList<>();
list.add("a");                     // 合法！final 锁的是引用，不是对象内容
list = new ArrayList<>();          // 编译错误：不能再指向别的对象

public static final int MAX = 100; // 类级常量标准写法：static 全局一份 + final 值不可改 + 命名 UPPER_SNAKE_CASE（3.2）
```

两个推论：`final` 字段声明时没赋值（空白 final）就**必须在构造器里完成赋值**（8.1 的 `dept` 正是此用法）；Java 没有 `const` 关键字（保留字但未启用），常量机制就是上面这套组合拳。后文 13.3 的「effectively final」、19.1 的「不可变（final 字段）」都建立在「引用只能赋值一次」这条语义上。

### 7.3 对象相等：equals 与 hashCode

`==` 比引用（是否同一个对象），**内容相等要靠重写 `equals()`**，且必须同时重写 `hashCode()`（契约：equals 相等的两个对象 hashCode 必须相等，否则放进 HashMap/HashSet 会发生「存进去取不出来」）。两者都由 IDE 按字段生成，手写极易出错。

### 7.4 代码块与初始化顺序

```java
static { /* 静态块：类加载时执行一次，做重型初始化 */ }
{ /* 实例初始化块：每次 new 时在构造器之前执行 */ }
```

执行顺序：父静态 → 本静态 →（每次 new）父实例块与构造器 → 本实例块 → 本构造器。实例块实战很少用，读懂存量代码即可。

---

## 八、继承、多态与抽象

### 8.1 继承

```java
public class AdminUser extends User {
    private final String dept;

    public AdminUser(String name, String dept) {
        super(name);                 // 显式调父类构造器（必须在第一行）
        this.dept = dept;
    }

    @Override                        // 注解让编译器帮你校验「确实覆盖了父类方法」
    public String toString() {
        return "Admin" + super.toString();   // super 调父类版本
    }
}
```

- **单继承**：一个类只能有一个直接父类（没有多继承的菱形 ambiguity 问题）。所有类最终都继承 `Object`。
- 子类自动获得父类非 private 成员；构造器**不被继承**；静态方法随类存在、不参与多态（隐藏而非覆盖）。
- `final` 类不可继承（如 String），`final` 方法不可覆盖。

### 8.2 多态

```java
User u = new AdminUser("Bob", "ops");   // 向上转型：自动、安全
String s = u.toString();                 // 运行时按「实际类型」分发 -> "AdminUser(name=Bob..."
AdminUser a = (AdminUser) u;             // 向下转型：必须显式，错了抛 ClassCastException
if (u instanceof AdminUser) {            // 转之前先检查（Java 16+ 可写 instanceof AdminUser a 模式匹配）
    AdminUser safe = (AdminUser) u;
}
```

多态的价值在解耦：方法参数、集合元素声明为父类型/接口，就能接受任意实现——`List<String> list = new ArrayList<>();` 是同一思想的日常体现。**声明看左侧（编译期类型），执行看右侧（运行时对象）**。

### 8.3 抽象类与接口

| | 抽象类 `abstract class` | 接口 `interface` |
|---|---|---|
| 关键字 | `extends`（单继承） | `implements`（可多实现） |
| 构造器 | 有 | 无 |
| 字段 | 任意，可带实例状态 | 只能 `public static final` 常量 |
| 方法 | 抽象 + 具体混合 | 抽象；Java 8 起可有 `default`（带实现）与 `static` 方法 |
| 用途 | 「是什么」：共享状态与骨架 | 「能做什么」：能力契约 |

```java
public interface Payable {
    BigDecimal pay(BigDecimal amount);       // 抽象方法（public abstract 可省略）
    default boolean supportsRefund() {       // Java 8+：默认实现，实现类可覆盖
        return true;
    }
}
```

选择：只约定行为不带状态 → 接口；需要共享字段/构造逻辑 → 抽象类。多个接口含同签名 default 方法时，实现类**必须重写消歧**（`X.super.m()` 语法可指名调用）。

---

## 九、枚举、接口进阶与内部类

### 9.1 枚举是一等公民

枚举不是「带名字的整数」那么简单——**每个枚举常量是该枚举类的唯一实例**，可以带字段、构造器、方法：

```java
public enum OrderStatus {
    PENDING("pending", false),
    PAID("paid", true),
    CLOSED("closed", true);               // 最后一个常量后是分号

    private final String code;            // 枚举可以有实例字段
    private final boolean finalState;

    OrderStatus(String code, boolean finalState) {   // 构造器隐式 private，不能 public
        this.code = code;
        this.finalState = finalState;
    }

    public String getCode() { return code; }
    public boolean isFinalState() { return finalState; }

    public static OrderStatus fromCode(String code) {   // 按业务码反查要手写
        for (OrderStatus s : values()) {
            if (s.code.equals(code)) return s;
        }
        throw new IllegalArgumentException("Unknown code: " + code);
    }
}
```

常用成员：`values()`（全部常量数组）、`name()`（声明名）、`ordinal()`（声明序号，**别把它当业务值存库**，重排即错位）、`valueOf("PENDING")`（按名反查，拼错抛异常）。枚举可用 `==` 安全比较（单例），可用于 switch。实现接口即可承载多态逻辑（每个常量各自实现方法，替代大段 if/switch 的进阶手法）。

### 9.2 内部类速览

| 形态 | 声明位置 | 典型用途 |
|---|---|---|
| 成员内部类 | 类内 | 与外部类强耦合的辅助类型（持有外部实例引用） |
| 静态嵌套类 | 类内 + static | 只是命名空间上的嵌套，无外部引用（Builder 常这么写） |
| 局部类 | 方法内 | 几乎绝迹，被匿名类/Lambda 取代 |
| 匿名内部类 | 表达式处 `new Runnable() { ... }` | 一次性实现接口；Java 8 后大多可被 Lambda 替代 |
| Lambda | — | 严格说不是内部类：经 invokedynamic 实现，不生成匿名内部类的 class 文件；语法糖见第十三节 |

### 9.3 record、sealed 等新版类型（提示）

数据载体类 `record Point(int x, int y)`（Java 16 正式）、受限继承 `sealed interface Shape permits Circle, Square`（Java 17）能大幅削减样板，Java 8 不可用——见第二十三节。

---

## 十、异常处理

### 10.1 语法骨架

```java
try {
    String line = readFirstLine("in.txt");        // 该方法声明 throws IOException
    int n = Integer.parseInt(line);               // 可能抛 NumberFormatException
    handle(n);
} catch (NumberFormatException e) {               // 按类型分别处理，子类在前
    log.warn("bad number", e);
} catch (IOException | RuntimeException e) {      // multi-catch（Java 7+）
    throw new IllegalStateException("wrap", e);   // 包装重抛：cause 链保留现场
} finally {
    release();                                    // 无论正常返回还是异常都执行（清理资源）
}

try (FileInputStream in = new FileInputStream(f)) {   // try-with-resources（Java 7+）
    ...                                              // 块结束自动 close，嵌套多个资源用分号分隔
}
```

能进入 `catch (X e)` 的前提是 try 体内**确实可能抛出 X**（对受检异常编译器会检查，catch 一个抛不出的受检异常直接编译报错）；`RuntimeException` 及其子类不受此限。

### 10.2 异常体系与「受检」这一 Java 特色

```text
Throwable
 ├── Error                     虚拟机级灾难（OutOfMemoryError）——不捕获不处理
 └── Exception
      ├── 受检异常（checked）  IOException、SQLException 等：编译器强制你表态（catch 或 throws）
      └── RuntimeException     NPE、参数非法、越界、ClassCast 等：unchecked，不强制声明
```

**受检异常**是 Java 区别于主流语言的独有设计：把「可恢复的外部失败」编码进方法签名，调用方不可能无察觉。代价是代码噪音，业界趋势是少用（Spring 把 JDBC 受检异常全部包装成 RuntimeException）。实用准则：

- 编程错误（null 传进不该 null 的参数、状态机跳错）→ 抛 `IllegalArgumentException` / `IllegalStateException`（unchecked）；
- 调用方真能恢复的外部失败（文件缺失可换路径）→ 才考虑受检；
- 自定义业务异常：继承 `RuntimeException`，带错误码字段，由 Web 层全局异常处理器统一转响应。

### 10.3 好习惯

- 别 `catch (Exception e) {}` 吞异常——至少记日志，否则事故无从溯源；
- `finally` 里不要 return（会吞掉 try 中的返回值与异常）；
- 尽早、具体地捕获；转抛时永远带上 cause（`new XxxException(msg, e)`）；
- 异常对象创建代价高（要抓栈），不用它做流程控制。

---

## 十一、集合框架

### 11.1 全家福与选型

```text
Collection（接口）
 ├── List  有序、可重复、可按下标访问
 │    ├── ArrayList    默认选择：随机访问 O(1)，中间插删 O(n)
 │    └── LinkedList   双端链表：头尾操作 O(1)，按下标反而慢——几乎总被 ArrayList/ArrayDeque 替代
 ├── Deque/Queue 队列与栈
 │    └── ArrayDeque  当栈、当队列都用它（比老旧的 Stack 类好）
 └── Set   不重复
      ├── HashSet        默认选择：无序，增删查 O(1)
      ├── LinkedHashSet  保留插入顺序
      └── TreeSet        红黑树：元素有序，支持范围查询

Map（键值对，不属于 Collection）
 ├── HashMap       默认选择：O(1)
 ├── LinkedHashMap 保留插入顺序
 └── TreeMap       按键排序，支持 firstKey/floorKey 等
```

选型三问：**要键值对吗？要保序吗（插入序→Linked 系，排序→Tree 系）？要判重吗（要→Set）**。答不出来就用 `ArrayList` + `HashMap`。

### 11.2 基本操作

```java
List<String> names = new ArrayList<>();
names.add("tom");                       // 尾部追加
names.add(0, "first");                  // 按下标插入（O(n)，频繁头部插入换 LinkedList/ArrayDeque）
names.get(0);                           // 越界抛 IndexOutOfBoundsException
names.remove("tom");                    // 按值删（返回 boolean）；names.remove(0) 是按下标删
names.set(0, "jerry");
names.size();  names.isEmpty();
names.contains("x");                    // O(n) 线性找；频繁判存在应换 Set

Map<String, Integer> ages = new HashMap<>();
ages.put("tom", 18);
ages.get("bob");                        // 不存在返回 null——危险，见下
ages.getOrDefault("bob", 0);            // 安全读取（Java 8+）
ages.putIfAbsent("bob", 20);            // 不存在才放
Map<String, List<String>> groups = new HashMap<>();
groups.computeIfAbsent("group1", k -> new ArrayList<>()).add("x");   // 分组初始化神器：键不存在先建列表再追加（Java 8+）
for (Map.Entry<String, Integer> e : ages.entrySet()) { ... }      // 遍历键值
for (String k : ages.keySet()) { ... }                            // 只遍历键

names.sort(Comparator.naturalOrder());          // 原地排序（Java 8 起 List 自带 sort）
Collections.unmodifiableList(names);            // 只读视图
List<String> fixed = new ArrayList<>(Arrays.asList("a", "b"));    // 从数组建「可增删」列表（坑点 7）
```

### 11.3 遍历与修改

```java
// 遍历时删除的唯一安全姿势之一：removeIf（Java 8+）
names.removeIf(n -> n.isEmpty());
// 或走迭代器
Iterator<String> it = names.iterator();
while (it.hasNext()) { if (bad(it.next())) it.remove(); }
// 直接 for-each 中调 names.remove(...) 会抛 ConcurrentModificationException（坑点 8）
```

### 11.4 老集合的避雷名单

`Vector`、`Hashtable`、`Stack` 是 JDK 1.0 时代的同步遗留类，性能差且设计过时：**一律不用**，并发场景对应物是 `java.util.concurrent` 包（第十九节）与 `Collections.synchronizedList` 包装。

### 11.5 支撑集合的两个协议：迭代器与比较器

**Iterable / Iterator**：第五节说 for-each 能遍历「任何可迭代对象」，背后的协议就是这两个接口——`Iterable` 只有一个 `iterator()` 方法（集合都实现了它，所以能被 for-each）；`Iterator` 是遍历器本身，提供 `hasNext()/next()/remove()` 三件套（11.3 的安全删除用的就是它）。自己写的类想被 for-each，实现 `Iterable` 即可。

**Comparable / Comparator**：排序与有序容器（TreeSet/TreeMap、`Collections.sort`、Stream 的 `sorted`）都靠这两个接口之一提供「谁大谁小」的规则：

| | Comparable | Comparator |
|---|---|---|
| 定义位置 | 类**自己**实现（`compareTo` 方法） | **外部**独立对象，不改原类 |
| 语义 | 自然序（类的「默认」排序） | 定制序，可任意多套 |
| 典型 | String/Integer 都实现了，所以 `naturalOrder()` 直接能用 | `Comparator.comparing(User::getAge)` 按字段现造 |

```java
names.sort(Comparator.naturalOrder());                     // 用元素自身的 Comparable（自然序）
users.sort(Comparator.comparing(User::getAge));            // 按字段定制序（方法引用见 13.2）
users.sort(Comparator.comparing(User::getDept)
        .thenComparing(User::getAge).reversed());          // 多级排序 + 倒序
```

没有比较规则的类放进 TreeSet/TreeMap 或调 `sort()` 会抛 ClassCastException；第十七节「日期比较用 compareTo」正是因为 java.time 类都实现了 Comparable。

---

## 十二、泛型

### 12.1 是什么

泛型 = **给容器贴类型标签**：`List<String>` 声明「这个列表只装 String」。编译器据此拦截 `add(1)`，取值 `get(0)` 免强转。没有泛型的年代（Java 4 及以前）集合装一切，取出全靠手动转型，错误延迟到运行时才爆——泛型把这类错误提前到编译期。

```java
List<String> box = new ArrayList<>();     // 右侧 <> 是类型推断简写（Java 7+ diamond）
Map<String, List<Integer>> index = new HashMap<>();   // 可以嵌套

class Pair<A, B> {                        // 自定义泛型类
    private final A first;
    private final B second;
    Pair(A first, B second) { this.first = first; this.second = second; }
    A getFirst() { return first; }
}
```

### 12.2 规则清单

- **类型参数只能是引用类型**：`List<int>` 非法，写 `List<Integer>`（自动装箱让你用起来几乎无感，但 `Integer` 可为 null、有对象开销）。
- 同一泛型类的不同参数化类型是**同一个类**：`List<String>` 与 `List<Integer>` 运行时都是 `java.util.ArrayList`。
- **类型擦除**：泛型只存在于编译期，字节码里类型参数被擦成 Object/边界类型。由此推出——不能 `new T()`、不能 `T.class`、不能声明 `List<String>[]`、`instanceof List<String>` 非法（只能 `instanceof List`）。

### 12.3 通配符与方法签名上的泛型

```java
void printAll(List<?> list) { }                  // 任意元素类型，只能读不能写（除 null）
double sumAll(List<? extends Number> list) { }   // Number 或其子类：可读作 Number，add 被禁
void fill(List<? super Integer> list) { }        // Integer 或其父类型容器：可写 Integer
// 口诀 PECS：Producer(只读) 用 extends，Consumer(只写) 用 super

public static <T> List<T> repeat(T item, int n) { ... }   // 方法级类型参数：<T> 写在返回值前
```

通用准则（官方建议）：**方法能自己推断就把通配符用在参数上、返回值用具体类型参数；别在返回类型上写 `?`**（调用方拿到没法用）。

---

## 十三、Lambda 与函数式接口

### 13.1 Lambda 语法

Lambda（Java 8+）是「**把代码当值传递**」的语法糖，但它必须站在接口的肩膀上——目标类型必须是**函数式接口**（恰好一个抽象方法的接口）：

```java
Runnable r1 = new Runnable() {                     // Lambda 之前的写法（匿名内部类）
    @Override public void run() { System.out.println("hi"); }
};
Runnable r2 = () -> System.out.println("hi");      // 同一件事的 Lambda 形态

(int x, int y) -> x + y            // 完整形态
(x, y) -> x + y                    // 类型可推断，常省略
x -> x * 2                         // 单参数可去括号
(String s) -> {                    // 多语句要 {} 且显式 return
    String t = s.trim();
    return t.toUpperCase();
}
```

常用函数式接口（都在 `java.util.function`，背下这五个够用九成场景）：

| 接口 | 抽象方法 | 语义 | 基本类型特化（避免装箱） |
|---|---|---|---|
| `Function<T,R>` | `R apply(T t)` | 一进一出转换 | `IntFunction`、`Function<T,Integer>`… |
| `Predicate<T>` | `boolean test(T t)` | 判断 | `IntPredicate` |
| `Consumer<T>` | `void accept(T t)` | 只消费不返回 | `IntConsumer`、`BiConsumer` |
| `Supplier<T>` | `T get()` | 只生产不输入 | `IntSupplier` |
| `BinaryOperator<T>` | `T apply(T,T)` | 两进一出同类型 | `IntBinaryOperator` |

### 13.2 方法引用

现成方法恰好匹配接口时，可用 `::` 进一步压缩：

```java
names.forEach(System.out::println);        // 实例方法引用   ≈ n -> System.out.println(n)
users.sort(Comparator.comparing(User::getAge));  // getter 引用
List<User> us = names.stream().map(User::new).collect(Collectors.toList());  // 构造器引用 ≈ n -> new User(n)
Function<String, Integer> f = Integer::parseInt;    // 静态方法引用
Function<String, Integer> len = String::length;     // 特定类型任意对象的实例方法引用 ≈ s -> s.length()
```

### 13.3 变量捕获规则

Lambda 只能捕获**事实上不变（effectively final）**的局部变量——即没写 `final` 但从未被重新赋值的变量（`final` 语义见 7.2）：捕获后再对它赋值会编译报错。要跨 Lambda 累积状态，用字段、数组元素或原子类（`AtomicInteger`），别对着循环变量硬编。

---

## 十四、Stream API

### 14.1 心智模型

Stream（Java 8+）是**声明式的数据处理管道**：数据源 → 0 或多个中间操作（惰性，不执行）→ 一个终端操作（触发计算）。它不存储数据、不修改源头、只消费一次。命令式的「怎么循环」被替换成声明式的「要什么结果」。

```java
List<String> result = users.stream()          // 源
        .filter(u -> u.getAge() >= 18)        // 中间：过滤
        .sorted(Comparator.comparing(User::getName))   // 中间：排序
        .map(User::getName)                   // 中间：转换
        .distinct()                           // 中间：去重
        .limit(10)                            // 中间：截断
        .collect(Collectors.toList());        // 终端：收束成 List
```

### 14.2 常用操作清单

| 需求 | 写法 |
|---|---|
| 计数/最值 | `.count()` `.max(cmp)` `.min(cmp)`（最值返回 Optional） |
| 匹配 | `.anyMatch(p)` `.allMatch(p)` `.noneMatch(p)` |
| 查找 | `.findFirst()` `.findAny()`（并行流语义） |
| 聚合 | `.mapToInt(x -> x.getValue()).sum()`；`.reduce(seed, (a,b) -> a+b)` |
| 分组 | `.collect(Collectors.groupingBy(User::getDept))`；分组+计数 `groupingBy(cls, counting())` |
| 分区 | `.collect(Collectors.partitioningBy(p))` → Map<Boolean, List> |
| 拼接字符串 | `.map(String::valueOf).collect(Collectors.joining(", ", "[", "]"))` |
| 转 Map | `.collect(Collectors.toMap(K::keyOf, V::valueOf))`（键冲突要给 merge 函数） |
| 拍平一层 | `.flatMap(list -> list.stream())`（一对多展开，处理「列表的列表」必备） |
| 装箱/拆箱 | `intStream.boxed()`；`.mapToDouble(f)` 避免 Integer 中转 |
| 惰性副作用调试 | `.peek(System.out::println)`（仅限调试，别依赖它执行逻辑） |

### 14.3 边界与禁忌

- Stream 只能用一次，复用抛 `IllegalStateException`；需要多次遍历就 `collect` 回集合。
- 并行流 `parallelStream()` 不免费：任务可分割、无共享可变状态、数据量够大才值得，默认串行。
- 管道里不要修改外部集合/变量（副作用会让并行与未来维护双双翻车）。
- 简单三层循环能写清的东西别硬上 Stream；可读性优先。

---

## 十五、Optional 与空值安全

`Optional<T>`（Java 8+）是「这个值可能不存在」的**类型化表达**，目的是把 NPE 从运行时提前到编译期的约定层面：

```java
Optional<User> u = findUserById(id);              // 方法声明返回 Optional<User>，调用方被迫正视「可能没有」

String name = u.map(User::getName)                // 存在则变换
               .orElse("anonymous");              // 否则给默认值
u.ifPresent(x -> welcome(x));                     // 存在则消费
User or = u.orElseGet(() -> createDefault());     // 惰性默认（orElse 的参数总会被求值）
User need = u.orElseThrow(() -> new NotFoundException(id));  // 没有就抛
Optional<String> city = u.filter(x -> x.getAge() > 18).map(User::getCity);  // 链式条件收窄
```

三条纪律：**别调 `get()`**（裸奔回 NPE 原点，用 orElseThrow 表达意图）；**别把 Optional 用作字段、方法参数、集合元素**（它不是序列化友好也不是线程安全的设计，只用于**返回值**）；判断存在用 `isPresent()` 不如直接走链式 API。配套工具：`Objects.requireNonNull(x, "参数名")` 在入口拦截 null；字符串比较用 `"literal".equals(var)` 防 null（坑点 2）。

---

## 十六、字符串与文本处理

### 16.1 String 基础

字符串**不可变**：任何「修改」都返回新对象，原串不动。内容比较必须 `.equals()`，`==` 比引用（坑点 1）。null 安全比较：`Objects.equals(a, b)`。

```java
int n = s.length();                    // 长度（数组是 .length，集合是 .size()，字符串是 .length()，三种都别记错）
char c = s.charAt(0);
String sub = s.substring(1, 4);        // [1,4) 左闭右开
boolean has = s.contains("xyz");       // 是否包含（子串）
String[] parts = s.split(",");         // 按分隔符切；分隔符按【正则】解释："a.b.c".split(".") 切不出东西
String joined = String.join("-", parts);          // 拼接列表（Java 8+）
String trimmed = s.trim();             // 去首尾 ASCII 空白；要处理全角/Unicode 空白用 Java 11 的 strip()
String rep = s.replaceAll("\\d+", "#");           // replace 是字面量替换，replaceAll 才是正则
String up = s.toUpperCase(Locale.ROOT);           // 大小写：跨语言场景务必显式给 Locale（坑点 17）
int idx = s.indexOf('@');              // 找不到返回 -1（不是异常）
String fmt = String.format("%s 共 %d 件，%.2f 元", name, cnt, price);   // %s %d %f %%，%n 换行
```

### 16.2 拼接的正确工具

循环里 `str += x` 每次都造一个新 String，量大即性能事故。循环拼接用 `StringBuilder`（单线程可变大buffer，链式 `append`）：

```java
StringBuilder sb = new StringBuilder();
for (String p : parts) { sb.append(p).append(','); }
String out = sb.deleteCharAt(sb.length() - 1).toString();
// 多文本块拼接：Java 8 没有文本块（Java 15+ 的 """ 三引号），只能 "+ \n +" 或 join
```

### 16.3 正则（java.util.regex）

```java
boolean ok = input.matches("\\d{3}-\\d{4}");     // matches 是【整串】匹配，找子串用 Pattern.compile(re).matcher(s).find()
Matcher m = Pattern.compile("(\\d+)-(\\d+)").matcher(src);
while (m.find()) { m.group(1); m.group(2); }     // 循环提取全部匹配
```

注意：Java 字符串字面量里反斜杠要双写（`\\d` 代表正则 `\d`）；`matches()` 与常见语言「find 语义」的 `match` 不同，是隐藏考点（坑点 16）。

### 16.4 BigDecimal：精确十进制（金额必用）

`double` 是二进制浮点，`0.1 + 0.2 != 0.3`（坑点 5）；`BigDecimal` 用十进制精确表示，是金额与精确计算的标准答案：

```java
BigDecimal a = new BigDecimal("0.1");              // 必须字符串构造！new BigDecimal(0.1) 会继承 double 误差
BigDecimal b = new BigDecimal("0.2");
BigDecimal sum = a.add(b);                         // 0.3，精确；四则运算全是方法：add/subtract/multiply/divide
BigDecimal avg = sum.divide(new BigDecimal("3"), 2, RoundingMode.HALF_UP);   // 除法必须给精度与舍入模式，否则除不尽抛异常
boolean eq = a.compareTo(b) < 0;                   // 比大小用 compareTo；别用 equals（它还比精度，1.0 与 1.00 不相等）
```

不可变（任何运算返回新对象，与 String 同风格）；另一条等价路线是以「分」为单位存 `long` 整数，彻底避开小数。

---

## 十七、日期时间（java.time）

Java 8 引入的新日期 API（JSR-310），不可变、线程安全，彻底取代老旧的 `Date`/`Calendar`/`SimpleDateFormat`（后者可变且非线程安全，存量代码才见）：

```java
LocalDate d = LocalDate.now();                  // 日期（无时区）：2026-11-19
LocalDateTime dt = LocalDateTime.now();         // 日期+时间（无时区）
LocalTime t = LocalTime.of(9, 30);
Instant ins = Instant.now();                    // 时间线上的点（UTC，存库/跨系统用它）
ZonedDateTime zdt = ZonedDateTime.of(dt, ZoneId.of("Asia/Shanghai"));   // 带时区

LocalDate next = d.plusDays(1).withYear(2027);            // 修改返回新对象（不可变风格）
Duration between = Duration.between(dt, otherDt);          // 时长差
Period p = Period.between(d, endDate);                     // 日期差（年月日）

DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
String text = dt.format(fmt);                               // 格式化
LocalDateTime parsed = LocalDateTime.parse("2026-11-19 09:30:00", fmt);   // 解析

// 模式字母：yyyy MM dd HH(24h) mm ss SSS——不是 JS/Python 的 YYYY-MM-DD 小写风格，YYYY 是「周年份」另有含义
```

选型：带时区的业务时刻用 `ZonedDateTime`/`Instant`，日历概念（生日、账期）用 `LocalDate`，数据库持久化对齐 JDBC 类型（`LocalDateTime`/`Instant`），比较一律用 `isEqual/isBefore/isAfter` 或 `compareTo`（实现了 Comparable），别拿字符串比时间。

---

## 十八、文件与 IO

### 18.1 NIO.2：现代文件操作首选

```java
Path base = Paths.get("data", "sub");             // 路径组装（构造器式 join）
List<String> lines = Files.readAllLines(Paths.get("a.txt"), StandardCharsets.UTF_8);   // 小文件一把读
byte[] raw = Files.readAllBytes(Paths.get("a.bin"));
Files.write(Paths.get("out.txt"), "done\n".getBytes(StandardCharsets.UTF_8));          // 覆盖写
Files.writeString(path, text, StandardCharsets.UTF_8,                                 // Java 11+
        StandardOpenOption.CREATE, StandardOpenOption.APPEND);                          // 追加写

try (Stream<String> big = Files.lines(Paths.get("huge.txt"))) {   // 大文件惰性逐行（用完即关，必须套 try）
    long n = big.filter(l -> !l.trim().isEmpty()).count();
}
Files.exists(p); Files.isDirectory(p); Files.createDirectories(p); Files.delete(p);
Files.copy(src, dst, StandardCopyOption.REPLACE_EXISTING);
```

显式传 `StandardCharsets.UTF_8` 是好习惯——Java 8 平台默认编码随操作系统（中文 Windows 是 GBK），不写就会「在我机器上好好的」。

### 18.2 流体系（读懂存量代码 + 精细控制时用）

四条抽象基类：字节流 `InputStream/OutputStream`（图片、音频等万物），字符流 `Reader/Writer`（纯文本）。日常从不直接裸用，而是**装饰器层层包装**：

```java
try (BufferedReader br = new BufferedReader(
         new InputStreamReader(new FileInputStream("in.txt"), StandardCharsets.UTF_8))) {
    String line;
    while ((line = br.readLine()) != null) { process(line); }
}   // try-with-resources 自动逐层 close；缓冲区由 BufferedReader 提供，别手写单层 FileReader 循环读
```

**序列化** = 把内存对象转成可存储/传输的字节流（反序列化则反向还原）。Java 原生方案要求类实现 `Serializable` 标记接口（无任何方法，纯资格声明），再用 `ObjectOutputStream` 写出；`transient` 修饰的字段会被跳过（密码、缓存等不宜落盘的字段用它排除）。因安全与兼容性问题，新项目已普遍改用 JSON（Jackson/Gson，第二十二节）——文本可读、跨语言、不依赖 Java 类版本，原生序列化了解即可、谨慎选用。

---

## 十九、并发编程

### 19.1 线程基础

Java 天然多线程（多核真并行，不存在单核锁式的全局解释器瓶颈）。创建线程的本质是「把任务交给线程执行」：

```java
// 任务：实现 Runnable（推荐，任务与执行机制解耦）
Runnable task = () -> System.out.println("running in " + Thread.currentThread().getName());
Thread t = new Thread(task);
t.start();          // 启动新线程执行 run() —— 误写 t.run() 会在当前线程同步执行，「开了个寂寞」（坑点 14）
t.join();           // 等待该线程结束

// 需要返回值/异常的任务：Callable + Future（通常经线程池提交）
```

线程安全的最小模型：`n++` 是「读-改-写」三步复合操作，多线程并发会丢更新。对策依次为：不共享（线程封闭/局部变量）→ 不可变（final 字段，见 7.2）→ 无锁原子（`AtomicInteger` 等 CAS 类）→ 加锁（`synchronized`）→ 并发容器（`ConcurrentHashMap`）。

```java
public class Counter {
    private int n;
    public synchronized void inc() { n++; }     // 同一实例的调用串行化：最朴素的正确性保障
}
```

### 19.2 线程池（生产标准件，别裸 new Thread）

```java
ExecutorService pool = Executors.newFixedThreadPool(8);            // 简单场景可用；生产建议手工 new ThreadPoolExecutor 定参数
Future<Integer> fut = pool.submit(() -> heavyCompute());           // 提交 Callable
Integer r = fut.get(3, TimeUnit.SECONDS);                          // 取结果，可限时；超时抛 TimeoutException
pool.shutdown();                                                    // 停止接收新任务，跑完已有任务
```

`Executors` 的快捷工厂各有暗坑（`newFixedThreadPool`/`newSingleThreadExecutor` 队列无界可能堆积 OOM，`newCachedThreadPool` 线程数无上限），《阿里巴巴 Java 开发手册》强制要求用 `ThreadPoolExecutor` 构造器显式给核心数、队列容量与拒绝策略——新写线程池照此办理。

### 19.3 协作与异步编排

```java
BlockingQueue<Job> queue = new ArrayBlockingQueue<>(100);   // 生产者-消费者标准件：队满 put 阻塞、队空 take 阻塞
queue.put(job);  Job j = queue.poll(1, TimeUnit.SECONDS);

CompletableFuture
    .supplyAsync(() -> queryDb(), pool)                     // 异步执行
    .thenApplyAsync(rows -> transform(rows), pool)          // 完成后接着做（可指定池）
    .exceptionally(ex -> fallback())                        // 异常兜底
    .thenAccept(result -> notify(result));
CompletableFuture.allOf(f1, f2, f3).join();                 // 聚合多任务
```

### 19.4 知道边界在哪

`volatile` 只保证可见性不保证原子；`wait/notify`、AQS、`ReadWriteLock` 属于进阶工具箱，入门期把「共享可变状态尽量消灭、锁尽量粗粒度短持有、优先用 j.u.c 现成组件」三句记住即可。虚拟线程（Java 21）会把「一请求一线程」模型翻新，届时本手册第二十三节是接口。

### 19.5 volatile 与 CAS：两个术语的最小解释

19.1 的对策链里出现了两个未展开的术语，这里补上最小定义：

- **可见性问题**：一个线程改了共享变量，另一个线程可能一直读到旧值（CPU 缓存/编译器优化所致）。`volatile` 修饰字段后，写立即对所有线程可见——但它**只解决可见性，不解决原子性**：`volatile int n; n++` 照样丢更新（读-改-写仍是三步），所以它只适合「一写多读的状态标志」，计数还得靠原子类或锁。
- **CAS（Compare-And-Swap，比较并交换）**：一条 CPU 原子指令——「若当前值等于预期旧值，就换成新值，否则失败重试」。`AtomicInteger.incrementAndGet()` 内部就是 CAS 自旋：不加锁也能保证 `n++` 不丢更新，竞争不激烈时比 `synchronized` 轻；竞争激烈时自旋空转反而浪费 CPU，这是它的边界。

---

## 二十、模块化与包管理：Maven

### 20.1 项目结构（约定即法律）

```text
src/main/java/com/example/app/     生产代码（目录与 package 声明逐段对应）
src/main/resources/                配置资源（application.yml 等，classpath 资源）
src/test/java/...                  测试代码（镜像主代码包结构）
target/                            构建产物（不入库，进 .gitignore）
pom.xml                            项目对象模型：坐标 + 依赖 + 插件 + 构建配置
```

### 20.2 pom.xml 关键概念

```xml
<groupId>com.example</groupId>            <!-- 组织坐标 -->
<artifactId>my-app</artifactId>           <!-- 模块名 -->
<version>1.0.0-SNAPSHOT</version>         <!-- -SNAPSHOT 开发版；发布去后缀 -->

<properties>
    <maven.compiler.source>1.8</maven.compiler.source>
    <maven.compiler.target>1.8</maven.compiler.target>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
</properties>

<dependency>
    <groupId>com.fasterxml.jackson.core</groupId>
    <artifactId>jackson-databind</artifactId>
    <version>2.13.5</version>
    <scope>test</scope>                   <!-- compile(默认)/test/provided/runtime -->
</dependency>
```

依赖从 **Maven Central** 下载到本地仓库 `~/.m2/repository` **全局共享**（没有虚拟环境概念）；版本写死（无兼容范围语法），冲突时按「最短路径优先、先声明优先」仲裁，排查用 `mvn dependency:tree`。

### 20.3 命令与生命周期

| 命令 | 干什么 |
|---|---|
| `mvn clean package` | 清理 → 编译 → 测试 → 打 jar |
| `mvn test` | 只跑测试 |
| `mvn install` | 把产物装进本地仓库供其他项目依赖 |
| `mvn dependency:tree` | 看依赖树排冲突 |
| `mvn -U clean verify` | 强制更新快照并走完整校验 |

`clean`/`default`/`site` 三条生命周期，default 内阶段有序：`compile → test → package → verify → install → deploy`，执行靠后的自动带上靠前的。另一主流构建工具 **Gradle**（`build.gradle`，Groovy/Kotlin DSL）增量构建更快、Android 标配，概念与 Maven 一一对应，先精通一个。

---

## 二十一、测试：JUnit

事实标准 JUnit 5（Jupiter）。测试类放 `src/test/java`，包结构与主代码镜像：

```java
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;

class OrderServiceTest {
    private OrderService svc;

    @BeforeEach
    void setUp() { svc = new OrderService(); }        // 每个用例前执行（用例间相互隔离）

    @Test
    void paidOrderShouldEnterFinalState() {
        Order o = svc.create("sku-1");
        svc.pay(o, 100);
        assertTrue(o.getStatus().isFinalState());
        assertEquals(OrderStatus.PAID, o.getStatus());
    }

    @Test
    void negativeAmountShouldFail() {
        Order o = svc.create("sku-1");
        assertThrows(IllegalArgumentException.class, () -> svc.pay(o, -1));   // 断言异常
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "x"})
    void blankSkuRejected(String sku) {                                     // 参数化（JUnit 5）
        assertThrows(IllegalArgumentException.class, () -> svc.create(sku));
    }
}
```

要点：测试方法无需 public（JUnit 5 起）；**一个用例验证一件事**，命名把行为写成人话；断言库可叠加 AssertJ（流式断言更可读）；Mock 依赖用 Mockito；覆盖率 JaCoCo。跑测试：`mvn test` 或 IDE 点击。

顺带澄清一个易混关键字：Java 自带的 `assert` 语句（`assert x > 0 : "说明";`）是**语言级断言**，与 JUnit 的 `assertXxx` 断言方法无关；且 JVM **默认关闭** assert（要 `-ea` 参数才生效），生产代码里写了等于没写——参数校验用 `Objects.requireNonNull`/显式抛异常（第十五节），测试断言用 JUnit，别依赖它。

---

## 二十二、生态导航：从 SE 到企业开发

| 领域 | 事实标准 | 一句话定位 |
|---|---|---|
| Web 框架 | **Spring Boot** | 注解驱动 + 内嵌服务器，打成一个可执行 jar 直接部署；约定优于配置 |
| ORM | Spring Data JPA / **MyBatis** | 对象-关系映射；MyBatis 在国内存量项目占绝对主流 |
| JSON | Jackson | 对象⇄JSON 序列化，注解微调（如 `@JsonValue` 控制枚举输出） |
| 参数校验 | Bean Validation（Hibernate Validator） | DTO 上 `@NotBlank/@Size` 声明约束，框架自动拦截 |
| 日志 | SLF4J + Logback | 门面 + 实现，别直接调 `System.out` |
| 样板消除 | Lombok | `@Data/@Builder` 注解期生成 getter/构造器（IDE 需装插件） |
| 构建 | Maven / Gradle | 第二十节 |
| 容器化 | Docker + 可执行 jar | 后端产物自包含，镜像化部署是当下默认 |

Spring 心智一句话：你写的 `@Component/@Service/@RestController` 类不被你 new，而是被**IoC 容器**扫描、实例化、按依赖注入、以代理增强（事务/切面）——「对象是谁创建的」这个困惑的标准答案永远在容器里。入门路线建议：先本手册语言核心 → 用原生 JDBC 摸一次数据库 → 再上 Spring Boot，控制反转的魔法感会小很多。

---

## 二十三、语言版本演进速览（8→21）

> 本手册基线 Java 8。下表用于读懂新代码与规划升级；标 ★ 的是日常高频。

| 版本 | 特性 | 示例/说明 |
|---|---|---|
| 8 | Lambda/Stream/Optional/java.time/接口 default | 本手册主体 |
| 9 | 模块化 JPMS、`List.of()`★、try-with-resources 增强 | 不可变集合工厂 |
| 10 | `var` 局部变量推断★ | `var list = new ArrayList<String>();` 仅限局部变量 |
| 11 | 私有接口方法、`try (var …)` | |
| 14 | **switch 表达式**★（箭头分支、有值）、`instanceof` 模式匹配预览 | `int n = switch (c) { case 'a' -> 1; default -> 0; };` |
| 15 | 文本块 `"""..."""`★（多行字符串）、sealed 预览 | 内嵌 SQL/JSON 不再拼接 |
| 16 | **record**★（不可变数据载体一行搞定）、模式匹配 instanceof 转正 | `record Point(int x, int y) {}` 自带构造器/equals/toString |
| 17 | **sealed 类型**（受控继承）正式、上下文关键字 switch 持久化 | `sealed interface Shape permits Circle, Square` |
| 18 | UTF-8 成为默认字符集★（本手册反复叮嘱的编码坑从根上治了） | |
| 19/20 | 结构化并发、模式匹配分派——预览期 | 生产别用 |
| 21 | **虚拟线程**★、序列集合 `SequencedCollection`、switch 模式匹配正式 | `Thread.ofVirtual()`；高并发吞吐模型重写 |

LTS 节奏：8 → 11 → 17 → 21 → 25。升级断点主要在**平台侧**（javax→jakarta 命名空间迁移属于 Spring Boot 3/EE 9 那一跳，语言侧源码基本兼容）。

---

## 二十四、坑点汇总

1. **`==` 比较字符串内容**：`==` 比引用。`"ab" == "a" + "b"` 可能为 true（编译期常量合并进字符串池），`new String("ab") == "ab"` 必为 false——它对一半错一半，比全错更危险。内容一律 `.equals()` 或 `Objects.equals()`；枚举例外（单例，`==` 是推荐写法）。
2. **null 解引用**：`str.equals("x")` 在 str 为 null 时 NPE。铁律：字面量在前 `"x".equals(str)`；方法返回集合用 `Collections.emptyList()` 不用 null；入口用 `Objects.requireNonNull`。
3. **整数除法**：`7 / 2 == 3`。要 3.5 先转 `(double) a / b`；负数除法向零截断、`%` 符号随被除数，分页/取模散列时重点自查。
4. **整数溢出静默回绕**：`int * int` 超 2³¹-1 直接变负数不报错。大数显式 `long` 字面量（`100_000L * 100_000`）或用 `Math.multiplyExact` 主动探测。
5. **浮点数不精确**：`0.1 + 0.2 != 0.3`（IEEE 754 固有）。金额用 `BigDecimal`（且必须**字符串构造**：`new BigDecimal("0.1")`，double 构造继承误差）或以「分」为单位存整数。
6. **直接打印数组**：得到 `[I@1b6d3586`。用 `Arrays.toString`（多维用 `deepToString`）。
7. **`Arrays.asList` 是半可变视图**：能 set 不能 add/remove（抛 UnsupportedOperationException）。要可变列表：`new ArrayList<>(Arrays.asList(...))`。
8. **遍历时直接改集合**：`for (x : list) list.remove(x)` 抛 ConcurrentModificationException。用 `removeIf` 或 `Iterator.remove()`。
9. **只重写 equals 不重写 hashCode**：对象进 HashMap/HashSet 后取不出来。两个方法永远成对生成（IDE 一键）。
10. **可变对象做 HashMap 键**：put 之后字段变了 → hash 变了 → 元素「失踪」。作键的类应当不可变。
11. **switch 忘 break 静默穿透**：是特性也是事故源头；刻意的穿透写注释，或改用上表 Java 14 的 switch 表达式。
12. **受检异常 catch 不可达**：try 体内不可能抛出的受检异常，catch 它直接编译报错（RuntimeException/Error 不受此限）。写 multi-catch 前先确认 try 里真会抛。
13. **空 catch 块**：吞异常等于掩埋事故现场，最低限度记日志。
14. **`Thread.run()` 当成 `start()`**：run() 只是普通方法调用，线程没开、逻辑照跑，极难排查。
15. **循环里 `String +=`**：n 次拼接产生 n 个中间对象，性能塌方。用 `StringBuilder`。
16. **`split` 参数是正则**：`s.split(".")` 返回空数组（`.` 匹配任意字符），点要写 `"\\."`；`matches()` 是整串匹配不是 find。
17. **大小写的 locale 陷阱**：土耳其 locale 下 `"I".toLowerCase()` 不是 `"i"`。对标识符/协议串做大小写转换时显式 `Locale.ROOT`。
18. **SimpleDateFormat 当静态字段共享**：非线程安全，并发下解析出错。新代码一律 java.time；不得不用旧 API 时 `ThreadLocal<SimpleDateFormat>`。
19. **日期模式串写 `YYYY`**：那是「基于周的年」，跨年周会差一年。日常用 `yyyy`。
20. **`Executors` 快捷工厂直接上生产**：无界队列/无界线程池的 OOM 风险，手工 `new ThreadPoolExecutor` 显式定参。
21. **文件名与 public 类名不一致、package 与目录不符**：都是编译错误，且报错信息对新用户不友好——先记住「一个 .java 一个 public 类，目录逐段对应包名」。
22. **Java 8 工程里写了新语法**：`var`、`List.of`、record、文本块、switch 表达式——源码级别配置宽松时 IDE 可能不拦，CI 才爆。对照第二十三节标注引入版本再动手。

---

## 二十五、速查表

### 25.1 命令速查（Windows PowerShell）

| 操作 | 命令 |
|---|---|
| 查版本 | `java -version` ; `javac -version` |
| 编译单文件 | `javac -encoding UTF-8 -d out Hello.java` |
| 运行 | `java -cp out Hello` |
| 编译带依赖 | `javac -cp "lib/*" -d out src/*.java` |
| 打 jar | `jar cfe app.jar com.example.Main -C out .` |
| 运行 jar | `java -jar app.jar` |
| 反编译看签名/字节码 | `javap -c com.example.Main` |
| Maven 全量构建 | `mvn clean package` |
| Maven 只跑测试 | `mvn test` |
| 依赖树排冲突 | `mvn dependency:tree` |
| 强制更新依赖 | `mvn -U clean install` |

### 25.2 长度三件套与高频 API

| 对象 | 取长度 | 常用操作 |
|---|---|---|
| 数组 `int[]` | `.length` | `Arrays.sort/toString/copyOf/fill` |
| `String` | `.length()` | `charAt/substring/split/replace/contains/format` |
| 集合 `List/Set/Map` | `.size()` | `add/get/remove/put/containsKey/removeIf/sort` |

### 25.3 「我想做 X」快查

| 我想… | Java 8 写法 |
|---|---|
| 打印 | `System.out.println(x)` |
| 读控制台 | `new Scanner(System.in).nextLine()` |
| 格式化字符串 | `String.format("%s-%d", a, b)` |
| 字符串转数字 | `Integer.parseInt(s)`（失败抛 NumberFormatException） |
| 判两串相等 | `"a".equals(b)` |
| 遍历 Map | `for (Map.Entry<K,V> e : m.entrySet())` |
| 列表按字段排序 | `list.sort(Comparator.comparing(X::getY))`（`.reversed()` 倒序） |
| 过滤+转换+收集 | `stream().filter(...).map(...).collect(toList())` |
| 安全取可能为空的值 | `opt.map(F::get).orElse(def)` |
| 分组 | `Collectors.groupingBy(Classifier)` |
| 读整个文本文件 | `Files.readAllLines(path, UTF_8)` |
| 逐行处理大文件 | `try (Stream<String> s = Files.lines(path)) { ... }` |
| 当前时间 | `LocalDateTime.now()`；UTC 瞬间 `Instant.now()` |
| 日期格式化 | `dt.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))` |
| 线程池提交任务 | `pool.submit(() -> work()); fut.get(timeout, unit)` |
| 断言测试 | JUnit5 `assertEquals/assertThrows` |
| 不可变列表 | `Collections.unmodifiableList(src)`（`List.of` 是 Java 9+） |
| 常量 | `public static final int MAX = 100;` |

### 25.4 常用类身份卡

| 类 | 一句话 |
|---|---|
| `Objects` | equals/hash/requireNonNull 静态工具箱 |
| `Arrays` | 数组的 sort/toString/fill/copyOf |
| `Collections` | 集合工厂、不可变包装、老算法 |
| `Optional` | 「可能没有」的类型化表达，只用于返回值 |
| `StringBuilder` | 可变大段拼接 |
| `Math` / `StrictMath` | 数学函数与常量 |
| `BigDecimal` | 精确十进制（金额），注意构造用字符串 |
| `LocalDate/LocalDateTime/Instant/ZonedDateTime` | java.time 四件套 |
| `Stream` / `Collectors` | 声明式数据管道及其收束器工厂 |
| `Comparator` | 比较器：`comparing/thenComparing/reversed/naturalOrder` |
| `Pattern/Matcher` | 正则 |
| `ExecutorService` / `Future` / `CompletableFuture` | 线程池与异步结果三件套 |
| `ConcurrentHashMap` / `AtomicInteger` / `BlockingQueue` | 并发容器与同步基础件 |
| `Files` / `Path` / `Paths` | NIO.2 文件操作 |

### 25.5 低频关键字身份卡（读懂即可，几乎不用手写）

| 关键字 | 一句话 | 详见 |
|---|---|---|
| `transient` | 序列化时跳过该字段 | 18.2 |
| `assert` | 语言级断言，JVM 默认关闭（-ea 才生效），别用于生产校验 | 第二十一节 |
| `native` | 声明方法由非 Java 代码（C/C++，JNI）实现，无方法体 | — |
| `strictfp` | 强制严格浮点运算（跨平台一致），现代硬件下几乎无意义 | — |
| `const` / `goto` | 保留字但**未启用**，写了编译报错；常量用 `static final`（7.2） | 7.2 |
