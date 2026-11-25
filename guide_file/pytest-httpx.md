# pytest + httpx 完整指令文档（通用手册 + 项目测试体系实战）

> 适用版本：以 **pytest 9.x** / **httpx 0.28.x** 为基准整理（2026-09），对应本项目 `backend/pyproject.toml` 的 dev 依赖组实测版本（`pytest>=9.1.1`、`httpx>=0.28.1`）；Python **≥3.11**（本项目 3.14.7）。异步测试用 **anyio 的 pytest 插件**（FastAPI/starlette 的传递依赖，无需另装 pytest-asyncio）。
> 定位：**通用手册 + 本项目测试体系实战（第七节）**——第一~六节为不绑定项目的 pytest / httpx 指令大全与「用 httpx 测 FastAPI」通法；第七节把本项目 `backend/tests/` 的四层测试体系按当前代码事实逐段解读为可复用范例。pytest / httpx 各自的官方 API 以 `pytest --help`、httpx 官方文档为最终依据。
> 可信度标注：「实测」= 本机执行验证过。**第七节项目代码为已入库的真实测试**（`backend/tests/` 五文件 + `conftest.py`，解读基于对源码的逐行核实；本会话未重跑，运行结果以本机 `uv run pytest` 为准）；第一~六节的通用指令为 **官方文档行为，未逐一实测**。凡涉及本项目已核实的版本事实（httpx 0.28 移除 `app=` 简写、anyio 后端、`[tool.pytest.ini_options]` 配置）均标注来源。
> 执行位置约定：**PowerShell** = Windows 终端（语句分隔用 `;` 不用 `&&`）；**bash** = WSL / Linux 内。本项目为 **uv 工作流**，测试命令统一以 `uv run pytest ...` 形式给出（在 `backend/` 目录执行）；文档内引用项目源码用相对路径代码格式（如 `backend/tests/conftest.py`）。

---

## 目录

1. [概览与核心概念](#一概览与核心概念)
2. [安装与配置](#二安装与配置)
3. [pytest 指令集](#三pytest-指令集)
4. [pytest CLI 命令全集](#四pytest-cli-命令全集)
5. [httpx 指令集](#五httpx-指令集)
6. [用 httpx 测 FastAPI（集成测试专章）](#六用-httpx-测-fastapi集成测试专章)
7. [本项目测试体系实战（pipeline-fault-tracker）](#七本项目测试体系实战pipeline-fault-tracker)
8. [坑点汇总](#八坑点汇总)
9. [命令速查表](#九命令速查表)

---

## 一、概览与核心概念

### 1.1 pytest 是什么

pytest 是 Python 事实标准的测试框架，相比标准库 `unittest` 的核心优势：

| 特性 | 说明 |
|---|---|
| **原生 assert** | 直接用 `assert x == y`，pytest 重写断言表达式，失败时自动展开左右值差异，无需记 `assertEqual` 家族 |
| **fixture 依赖注入** | 用函数参数名声明依赖，pytest 自动注入并管理生命周期（替代 setUp/tearDown） |
| **参数化** | `@pytest.mark.parametrize` 一个用例跑多组数据，每组独立报告 |
| **自动发现** | 按命名约定（`test_*.py` / `Test*` 类 / `test_*` 函数）递归收集用例 |
| **插件生态** | anyio/asyncio（异步）、cov（覆盖率）、xdist（并行）等按需装 |
| **兼容 unittest** | 能直接跑既有 `unittest.TestCase`，渐进迁移 |

### 1.2 httpx 是什么

httpx 是下一代 Python HTTP 客户端，API 与 `requests` 高度相似，但**原生支持异步（async/await）与 HTTP/2**：

- 同步用 `httpx.Client`，异步用 `httpx.AsyncClient`，方法名一致（`get/post/...`）；
- 关键差异能力：**`ASGITransport` / `WSGITransport`** —— 可以把请求直接「打」进一个 ASGI/WSGI 应用对象，**不经过真实网络、不起服务器**，这正是测 FastAPI 的利器（见第六节）；
- `Response` 对象提供 `.status_code` / `.json()` / `.text` / `.headers` / `.raise_for_status()` 等。

### 1.3 为什么是 pytest + httpx 这对组合

测一个 FastAPI（ASGI）应用，传统做法是「起 uvicorn 占端口 → requests 打真实 HTTP → 关服务器」，慢且脆。现代做法：

```
pytest（组织用例 + fixture 注入）
   └─ httpx.AsyncClient（发请求）
        └─ ASGITransport（把请求直连进 FastAPI app 对象，不走网络）
             └─ dependency_overrides（把数据库等依赖换成测试替身）
```

于是集成测试**无需起服务器、无需占端口、无需真实数据库**，一个进程内跑完整请求链路，快且隔离。本项目 `conftest.py` 就是这套（第七节详解）。

### 1.4 测试分层金字塔（本项目落地形态）

| 层 | 测什么 | 用什么 | 本项目文件 |
|---|---|---|---|
| 单元（底层） | Pydantic schema 的字段约束 | 纯构造 + `pytest.raises` | `test_schemas.py` |
| 单元 | crud 数据访问与业务规则 | 内存 SQLite + `db_session` fixture | `test_crud.py` |
| 集成（顶层） | HTTP 端点完整请求链路 | httpx `AsyncClient` + `ASGITransport` | `test_api_pipelines.py`、`test_api_faults.py` |

原则：**底层多而快（不碰 IO），顶层少而全（走真实链路）**。同一个业务规则（如「done 终态不可逆」）在 crud 层和 API 层各测一次——前者定位精确、后者验证端到端。

### 1.5 与 starlette TestClient 的关系

FastAPI 文档常用的 `from fastapi.testclient import TestClient` 是 **starlette 提供的同步封装，底层就是 httpx**。二者取舍：

| | `TestClient`（同步） | `httpx.AsyncClient` + `ASGITransport`（异步） |
|---|---|---|
| 写法 | `client.get(...)` | `await client.get(...)` |
| 需要的插件 | 无（内部用 anyio 跑） | `pytest.mark.anyio` / `pytest.mark.asyncio` |
| 适合 | 简单同步测试、快速上手 | 异步依赖、并发场景、要精细控制 transport |
| 本项目选择 | — | ✅ 异步（见 7.4 conftest） |

本项目选异步 `AsyncClient`：与 FastAPI 的 async 路由一致，且能显式掌控 `ASGITransport` 与依赖覆盖。

---

## 二、安装与配置

### 2.1 安装

```bash
# 本项目（uv 工作流，装进 dev 依赖组）
uv add --dev pytest httpx

# 传统 pip
pip install pytest httpx

# 验证
uv run pytest --version
```

> 依据：`backend/pyproject.toml` 的 `[dependency-groups] dev = ["httpx>=0.28.1", "pytest>=9.1.1"]`（已核实）。uv 的 dev 组默认在 `uv sync` / `uv run` 时安装，不进生产镜像（生产用 `uv sync --no-dev`）。

### 2.2 pyproject.toml 配置（本项目实例）

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]        # 只收集 tests/ 目录，避免误扫 alembic/、seed.py 等脚本
pythonpath = ["."]           # 把 backend/ 加入 sys.path，测试里 import app.* 才可解析
addopts = "-v --tb=short"    # 默认追加的 CLI 参数：逐条列用例名 + 精简回溯
```

三个键逐条说明：

- **`testpaths`**：限定收集范围。不写则从根目录递归扫全部 `test_*.py`，会把 `alembic/versions/*.py`、`seed.py`、`rollback_demo.py` 之类误当测试。
- **`pythonpath`**：把指定目录加入 `sys.path`。本项目 `[tool.uv] package = false`（应用不装成包），测试里 `from app.main import app` 需要 `backend/` 在 `sys.path` 上——`pythonpath = ["."]` 解决（相对 pyproject.toml 所在目录）。
- **`addopts`**：每次运行自动附加的命令行参数，等于默认帮你敲 `pytest -v --tb=short`。

> `pytest.ini` / `setup.cfg` / `tox.ini` 也能配 pytest，但本项目统一放 `pyproject.toml`（单一事实源）。

### 2.3 conftest.py：共享 fixture 的发现机制

`conftest.py` 是 pytest 的**目录级共享配置文件**，无需 import，pytest 自动加载：

- 放在某目录的 `conftest.py`，其中的 fixture / 钩子对**该目录及所有子目录**的测试可见；
- 可以有多个层级：根 `conftest.py`（全局）+ `tests/conftest.py`（测试专用）；
- 本项目 `backend/tests/conftest.py` 定义了 `db_session`、`client`、`anyio_backend` 三个 fixture，所有测试文件直接用参数名注入（第七节详解）。

### 2.4 测试发现规则（命名约定）

pytest 默认按以下约定递归收集：

| 对象 | 约定 | 备注 |
|---|---|---|
| 文件 | `test_*.py` 或 `*_test.py` | 本项目统一 `test_*.py` |
| 类 | `Test*` 开头、**且无 `__init__` 方法** | 有 `__init__` 会被跳过 |
| 函数/方法 | `test_*` 开头 | 类内方法同样 `test_` 前缀 |

本项目用 `class TestHappyPath / TestErrorPath / TestBoundary` 分组、方法名 `test_n1_* / test_e1_* / test_b1_*`（正常/异常/边界编号），既满足约定又自带分类语义（见 7.8）。

### 2.5 异步测试的后端插件

`async def` 测试函数需要插件驱动事件循环，两种主流方案：

**方案 A：anyio（本项目采用）** —— anyio 自带 pytest 插件，随 FastAPI/starlette 一起装，零额外依赖：

```python
import pytest
pytestmark = pytest.mark.anyio          # 模块级：本文件所有 async 测试走 anyio

# conftest.py 里声明后端
@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"                    # 或 "trio"；本项目跑 asyncio
```

**方案 B：pytest-asyncio** —— 需单独装，配置 `asyncio_mode`：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"                   # auto 模式下 async 测试免标记
```

```python
@pytest.mark.asyncio                    # strict 模式（默认）需逐个标记
async def test_xxx(): ...
```

> 本项目选 anyio 的理由：它是 FastAPI 的传递依赖（已随主依赖安装），无需再引入 pytest-asyncio，减少一个 dev 依赖。标记用模块级 `pytestmark = pytest.mark.anyio`，文件内所有 async 用例一次生效（见 `test_api_*.py`）。

---

## 三、pytest 指令集

### 3.1 fixture：依赖注入的核心

fixture 是 pytest 最强大的机制——把「测试需要的资源 / 前置对象」做成可复用、可注入、带生命周期管理的函数。测试函数只要在参数里写出 fixture 名，pytest 就自动构造并注入。

**定义与注入**：

```python
import pytest

@pytest.fixture
def sample_pipeline():
    return {"code": "LINE-A", "name": "总装线A"}

def test_use(sample_pipeline):        # 参数名 = fixture 名，自动注入
    assert sample_pipeline["code"] == "LINE-A"
```

**带 teardown（yield 模式）**：

```python
@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session          # yield 前 = setup，测试体拿到 session
    finally:
        session.close()        # yield 后 = teardown，无论用例成败都执行
```

本项目 `db_session` 正是这个模式：yield 前 `drop_all` + `create_all` 建干净表，finally 里 `close()` + `drop_all` 清理（见 7.3）。

**scope（生命周期）**：

| scope | 含义 | 典型用途 |
|---|---|---|
| `function`（默认） | 每个测试函数重建一次 | 需要隔离的 db session |
| `class` | 每个测试类一次 | 类内共享的中等成本资源 |
| `module` | 每个 `.py` 文件一次 | 模块级只读数据 |
| `package` | 每个包一次 | |
| `session` | 整个测试会话一次 | 昂贵且只读的资源（如 `anyio_backend`） |

```python
@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
```

scope 越大越省，但有一条硬约束：**高 scope fixture 不能依赖低 scope fixture**（`session` 级不能注入 `function` 级），否则报 `ScopeMismatch`。

**fixture 依赖 fixture**（链式）：

```python
@pytest.fixture
def client(db_session):        # client 依赖 db_session，pytest 自动按依赖序构造
    ...
```

本项目 `client(db_session)` 就是链式依赖——先建好测试 session，再据它造 httpx 客户端（见 7.4）。

**autouse（自动应用，无需声明参数）**：

```python
@pytest.fixture(autouse=True)
def _reset_env():
    os.environ["MODE"] = "test"
    yield
```

每个测试自动跑。慎用——隐式依赖不好追踪，本项目未用（改用显式注入 + conftest 顶部环境变量覆盖）。

**内置 fixture 速览**：

| fixture | 用途 |
|---|---|
| `tmp_path` | 每个测试唯一的临时目录（`pathlib.Path`），自动清理 |
| `tmp_path_factory` | session 级临时目录工厂 |
| `monkeypatch` | 临时改环境变量 / 属性 / 函数，测试后自动还原 |
| `capsys` | 捕获 stdout / stderr |
| `caplog` | 捕获日志记录 |
| `request` | 访问测试上下文（间接参数化、动态 skip 用） |
| `pytestconfig` | 访问配置对象与命令行参数 |

`monkeypatch` 示例（改完自动还原，比手写 `os.environ` 安全）：

```python
def test_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(module, "attr", "new_value")
    monkeypatch.delenv("SECRET", raising=False)
```

> 本项目 conftest 未用 monkeypatch 覆盖 `DATABASE_URL`，而是**在 import app 之前直接 `os.environ[...] = ...`**——因为 settings 是模块级单例，必须在导入瞬间就是测试值，monkeypatch 的「测试内才生效」时机太晚（原因详见 7.2）。

### 3.2 参数化：一个用例跑多组数据

**基础形态**：

```python
@pytest.mark.parametrize("note", [None, "", "     "])
def test_done_requires_note(db_session, note):
    with pytest.raises(HandlingNoteRequiredError):
        crud.transition_fault(db_session, f.id, FaultStatus.done, note)
```

三组数据 → 生成 3 个独立用例，报告里各占一行、各自 pass/fail。本项目 `test_crud.py` 用它一次覆盖「note 为 None / 空串 / 纯空格都被拒」（见 7.6）。

**多参数**（元组解包）：

```python
@pytest.mark.parametrize("a,b,expected", [(1, 2, 3), (0, 0, 0), (-1, 1, 0)])
def test_add(a, b, expected):
    assert a + b == expected
```

**自定义用例 id（`ids=`）**，让报告可读：

```python
@pytest.mark.parametrize("params",
    [{"page": 0}, {"size": 999}, {"status": "archived"}],
    ids=["page0", "size999", "badstatus"])
```

**堆叠参数化**（笛卡尔积）：

```python
@pytest.mark.parametrize("x", [1, 2])
@pytest.mark.parametrize("y", ["a", "b"])
def test_combo(x, y): ...        # 生成 2×2 = 4 个用例
```

**间接参数化（`indirect`）**：把值传给**同名 fixture** 而非测试函数，用于「参数决定如何构造资源」：

```python
@pytest.fixture
def user(request):
    return create_user(request.param)     # request.param 拿到参数化传入的值

@pytest.mark.parametrize("user", ["alice", "bob"], indirect=True)
def test_x(user): ...                     # user 是经 fixture 构造的对象
```

### 3.3 marker：给用例打标签

**内置 marker**：

| marker | 作用 |
|---|---|
| `@pytest.mark.skip(reason=...)` | 无条件跳过 |
| `@pytest.mark.skipif(条件, reason=...)` | 条件满足则跳过 |
| `@pytest.mark.xfail(reason=...)` | 预期失败（失败 = xfail 不算错，意外通过 = xpass） |
| `@pytest.mark.parametrize(...)` | 参数化（见 3.2） |
| `@pytest.mark.usefixtures("f1", "f2")` | 应用 fixture 但不注入到参数（只需其副作用时） |
| `@pytest.mark.anyio` / `@pytest.mark.asyncio` | 异步测试（见 2.5） |

**模块级 `pytestmark`**：一次给整个文件所有用例打标记，避免逐个装饰：

```python
pytestmark = pytest.mark.anyio          # 本项目 test_api_*.py 用它
# 也可给列表：pytestmark = [pytest.mark.anyio, pytest.mark.slow]
```

**自定义 marker + 注册**（不注册会有 `PytestUnknownMarkWarning`）：

```toml
[tool.pytest.ini_options]
markers = [
    "slow: 慢速用例",
    "integration: 集成测试",
]
```

```python
@pytest.mark.slow
def test_heavy(): ...
```

**按 marker 过滤运行**（`-m` 支持布尔表达式）：

```bash
uv run pytest -m "not slow"            # 排除 slow
uv run pytest -m integration           # 只跑 integration
uv run pytest -m "fast and not flaky"  # 组合
```

### 3.4 断言与异常

**原生 assert + 自动重写**：失败时 pytest 展开左右值差异，无需自定义消息也能定位：

```python
assert resp.status_code == 201          # 失败打印：实际值 vs 期望值
assert data["code"] == "LINE-A"
assert [p["code"] for p in items] == ["LINE-A", "LINE-B"]   # 列表逐项 diff
assert x == y, "自定义失败说明"          # 需要时补一句上下文
```

**`pytest.raises`：断言代码抛出指定异常**：

```python
with pytest.raises(PipelineNotFoundError):
    crud.get_pipeline(db_session, 999)
```

本项目 `test_crud.py` 大量用它把业务异常变成断言（见 7.6）。

**匹配异常信息（`match=`，正则 `re.search`）**：

```python
with pytest.raises(ValueError, match="must be positive"):
    compute(-1)
```

**拿异常对象做进一步断言（`as exc_info`）**：

```python
with pytest.raises(ValidationError) as exc_info:
    FaultCreate(**payload)
assert ("symptom",) in {e["loc"] for e in exc_info.value.errors()}
```

本项目 `test_schemas.py` 用这招断言「报错的正是这个字段」而非只看抛没抛（见 7.5）。

**浮点近似比较**：

```python
assert 0.1 + 0.2 == pytest.approx(0.3)
```

### 3.5 组织：class 分组、skip、xfail

**class 分组**（本项目风格，纯命名空间）：

```python
class TestHappyPath:                    # Test* 开头、无 __init__
    def test_n1_xxx(self, db_session): ...
    def test_n2_xxx(self, db_session): ...

class TestErrorPath:
    def test_e1_xxx(self, db_session): ...

class TestBoundary:
    def test_b1_xxx(self, db_session): ...
```

class 只作分组（报告里按类聚合），fixture 照常按参数注入；也可在类里放 class 级共享 fixture。

**skip / skipif / xfail**：

```python
@pytest.mark.skip(reason="待后端支持该端点")
def test_future(): ...

@pytest.mark.skipif(sys.platform == "win32", reason="仅 POSIX")
def test_posix_only(): ...

@pytest.mark.xfail(reason="已知 bug #123，修复后应变 xpass")
def test_known_bug(): ...
```

**setup/teardown vs fixture**：老式 `setup_method` / `teardown_method` 仍兼容，但**一律优先 fixture**（可组合、可复用、scope 灵活、依赖清晰）。

### 3.6 异步测试与异步 fixture

```python
pytestmark = pytest.mark.anyio          # 声明本文件异步用例的后端插件

async def test_list(client):            # async 测试函数：直接 await
    resp = await client.get("/api/pipelines")
    assert resp.status_code == 200

@pytest.fixture
async def client(db_session):           # async fixture：yield 前后可 await / async with
    async with httpx.AsyncClient(transport=..., base_url="http://testserver") as ac:
        yield ac
```

要点：async fixture 用 `async with ... yield ...` 管理异步资源的进入与退出；本项目 `client` 正是此形态（见 7.4）。

---

## 四、pytest CLI 命令全集

> 本项目为 uv 工作流，命令统一以 `uv run pytest` 开头（在 `backend/` 目录执行）；非 uv 项目把 `uv run pytest` 换成 `pytest` 或 `python -m pytest` 即可。`pyproject.toml` 的 `addopts = "-v --tb=short"` 会自动附加，下述示例不重复写。

### 4.1 基本运行与目标选择

```bash
uv run pytest                                   # 跑 testpaths 配置的全部（本项目=tests/）
uv run pytest tests/test_crud.py                # 跑单个文件
uv run pytest tests/test_crud.py::TestFaultHappy               # 跑单个类
uv run pytest tests/test_crud.py::TestFaultHappy::test_n6_get_fault   # 跑单个方法
uv run pytest tests/test_api_faults.py::TestErrorPath::"test_e9_query_param_out_of_range[page0]"  # 单个参数化用例（节点 id 带方括号）
uv run pytest tests/test_crud.py tests/test_schemas.py         # 多个目标
```

**节点 id（node id）语法**：`文件路径::类名::方法名[参数化 id]`，层层用 `::` 分隔。`--collect-only` 可列出全部节点 id（见 4.5）。

### 4.2 按条件筛选用例

```bash
uv run pytest -k "fault and not done"    # 按【名称】关键字表达式（and/or/not，匹配路径+类+函数名）
uv run pytest -k "e1 or e2"              # 跑编号 e1/e2 的用例
uv run pytest -m "not slow"              # 按【marker】表达式（见 3.3）
uv run pytest --lf                       # 只跑上次失败的（--last-failed）
uv run pytest --ff                       # 先跑上次失败的，再跑其余（--failed-first）
uv run pytest --nf                       # 先跑新增/上次未跑过的（--new-first）
uv run pytest --stepwise                 # 从上次失败处继续，遇错即停（逐步修复）
```

`-k` 匹配的是**名称**（可用 `pipeline`、`test_n1` 等子串），`-m` 匹配的是 **marker**，两者常配合用。

### 4.3 输出与回溯控制

```bash
uv run pytest -v                    # 详细：逐条列出用例名与结果（本项目已默认）
uv run pytest -q                    # 安静：只汇总
uv run pytest -s                    # 不捕获 stdout（等价 --capture=no，调试 print 时用）
uv run pytest --tb=short            # 回溯精简（本项目默认）
uv run pytest --tb=long             # 回溯完整
uv run pytest --tb=line             # 每个失败只一行
uv run pytest --tb=no               # 不显示回溯
uv run pytest -ra                   # 末尾摘要列出除 passed 外所有用例（含 skip/xfail 原因）
uv run pytest -rA                   # 末尾摘要列出【全部】用例
uv run pytest --no-header           # 不打印 pytest 版本头
uv run pytest --color=no            # 关闭彩色（CI 日志采集）
```

`--tb` 取值：`auto`（默认）/ `long` / `short` / `line` / `native` / `no`。`-r` 后跟字符集：`f`失败 `E`错误 `s`跳过 `x`预期失败 `X`意外通过 `p`通过 `a`/`A`汇总。

### 4.4 失败处理与调试

```bash
uv run pytest -x                    # 首个失败立即停（--exitfirst）
uv run pytest --maxfail=3           # 累计 3 个失败后停
uv run pytest --pdb                 # 失败处自动进入 pdb 调试器
uv run pytest --trace               # 每个用例一开始就进 pdb
uv run pytest -x --lf --pdb         # 组合：只跑上次失败、首错即停并进调试
uv run pytest --strict-markers      # 用到未注册 marker 直接报错（配合 3.3 注册）
uv run pytest --strict-config       # 配置文件有未知键就报错
```

### 4.5 收集、耗时、版本

```bash
uv run pytest --collect-only        # 只收集不运行，列出将执行哪些用例（--co）
uv run pytest --co -q               # 精简列出节点 id（排查「为什么没跑到某用例」）
uv run pytest --setup-show          # 显示每个 fixture 的 setup/teardown 时序（排查 fixture 依赖）
uv run pytest --durations=10        # 结束后列出最慢的 10 个用例/fixture 耗时
uv run pytest --version             # 版本
uv run pytest -o addopts=""         # 临时覆盖 ini 里的 addopts（-o/--override-ini）
```

`--collect-only` 是排查「测试没被发现」的第一工具：命名不符约定、class 带了 `__init__`、被 `testpaths` 排除，都能在这里看出来。

### 4.6 覆盖率与并行（需额外插件）

```bash
# 以下需先装插件，本项目 dev 组当前【未含】，按需 uv add --dev pytest-cov / pytest-xdist
uv run pytest --cov=app --cov-report=term-missing   # pytest-cov：覆盖率 + 未覆盖行号
uv run pytest --cov=app --cov-report=html           # 生成 htmlcov/ 可视化报告
uv run pytest -n auto                               # pytest-xdist：按 CPU 核数并行
uv run pytest -n 4 --dist loadgroup                 # 4 进程，按组分发
```

> 引入这两个插件属新增 dev 依赖，需按项目规则先确认再装、并同步 `pyproject.toml` / `uv.lock` 与依赖台账。

### 4.7 缓存机制

pytest 在根目录维护 `.pytest_cache/`，记录上次失败用例（`--lf`/`--ff` 的数据源）：

```bash
uv run pytest --cache-clear         # 本次运行前清空缓存
uv run pytest --cache-show          # 查看缓存内容
uv run pytest -p no:cacheprovider   # 完全禁用缓存插件（不写 .pytest_cache）
```

`.pytest_cache/` 应加入 `.gitignore`（与 `__pycache__/` 同类的本地产物）。

---

## 五、httpx 指令集

### 5.1 两种客户端：顶层函数 vs Client / AsyncClient

```python
import httpx

# 形态 A：顶层快捷函数（一次性，每次新建连接，适合脚本里偶尔请求）
resp = httpx.get("https://example.com/api")

# 形态 B：Client（复用连接池 + 统一 base_url/headers/timeout，推荐）
with httpx.Client(base_url="https://example.com") as client:
    r1 = client.get("/api/a")
    r2 = client.get("/api/b")          # 复用同一连接池

# 形态 C：AsyncClient（异步，测试 FastAPI 用它）
async with httpx.AsyncClient(base_url="http://testserver") as client:
    resp = await client.get("/api/pipelines")
```

测试里**优先用 Client/AsyncClient**（`with` 管理生命周期），可统一设 `base_url` 后只写相对路径。本项目 `client` fixture 用 `async with httpx.AsyncClient(...)`（见 7.4）。

### 5.2 请求方法

`Client` / `AsyncClient` 与顶层函数都提供同名方法，对应 HTTP 动词：

```python
client.get(url, ...)
client.post(url, ...)
client.put(url, ...)
client.patch(url, ...)
client.delete(url, ...)
client.head(url, ...)
client.options(url, ...)
client.request("GET", url, ...)      # 通用形态，method 作字符串
# 异步版全部加 await：await client.post(...)
```

### 5.3 请求参数（发送数据）

```python
client.get("/api/faults", params={"status": "done", "page": 1})   # → 查询字符串 ?status=done&page=1
client.get("/api/faults", params=[("tag", "a"), ("tag", "b")])       # 多值 → ?tag=a&tag=b

client.post("/api/pipelines", json={"code": "LINE-A", "name": "总装线A"})   # 自动序列化 + Content-Type: application/json
client.post("/login", data={"user": "a", "pwd": "b"})              # 表单编码 application/x-www-form-urlencoded
client.post("/raw", content=b"bytes...")                            # 原始 body（bytes/str/迭代器）
client.post("/upload", files={"file": open("f.png", "rb")})          # multipart/form-data

client.get(url, headers={"X-Token": "abc"})                        # 请求头（与 client 级合并）
client.get(url, cookies={"sid": "123"})                            # cookie
client.get(url, auth=("user", "pass"))                             # Basic 认证（或 httpx.BasicAuth/自定义）
client.get(url, timeout=10.0)                                      # 单次超时（秒）
client.get(url, follow_redirects=True)                             # 跟随重定向（默认 False）
```

| 参数 | 作用 |
|---|---|
| `params` | 查询字符串（dict / list of tuple） |
| `json` | JSON body，自动 `json.dumps` + 设 Content-Type |
| `data` | 表单 body |
| `content` | 原始字节/字符串 body |
| `files` | multipart 上传 |
| `headers` / `cookies` / `auth` | 请求头 / cookie / 认证 |
| `timeout` | 超时（float 或 `httpx.Timeout`） |
| `follow_redirects` | 是否跟随 3xx |

> `json=` 与 `data=`/`content=` 互斥，一次请求只用一种 body 形式。本项目集成测试全部用 `json=` 传请求体（见 `test_api_*.py` 的 `client.post(..., json=...)`）。

### 5.4 Response 对象

```python
resp = client.get("/api/pipelines/1")

resp.status_code          # 200（int）
resp.json()               # 解析 JSON body → dict/list（本项目断言主力）
resp.text                 # body 文本（str）
resp.content              # body 原始字节（bytes）
resp.headers              # 响应头（大小写不敏感的字典）；resp.headers["Location"]
resp.cookies              # 响应 cookie
resp.url                  # 最终 URL（含重定向后）
resp.history              # 重定向链
resp.elapsed              # 耗时（timedelta）
resp.reason_phrase        # "OK"

resp.raise_for_status()   # 4xx/5xx 时抛 httpx.HTTPStatusError，2xx 直接过
resp.is_success           # 2xx 为 True
resp.is_redirect          # 3xx
resp.is_client_error      # 4xx
resp.is_server_error      # 5xx
```

本项目集成测试的断言三件套：`resp.status_code`（状态码）+ `resp.json()`（结构体）+ `resp.headers["Location"]`（创建资源的路径头），见 7.7。

> `raise_for_status()` 在测试里慎用：本项目**不用 `raise_for_status`**，而是显式断言具体状态码（如 `assert resp.status_code == 409`），因为错误路径本身就是被测目标。

### 5.5 传输层 Transport（测试的关键）

Transport 决定请求「怎么发出去」。测试时用它能绕过真实网络：

```python
# ASGITransport：把请求直接打进 ASGI 应用（FastAPI/Starlette），不起服务器
transport = httpx.ASGITransport(app=app)
async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
    resp = await client.get("/api/pipelines")

# WSGITransport：同理打进 WSGI 应用（Flask/Django）
transport = httpx.WSGITransport(app=wsgi_app)

# MockTransport：用自定义 handler 返回伪造响应（测客户端逻辑/隔离外部依赖）
def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"hello": "world"})
client = httpx.Client(transport=httpx.MockTransport(handler))

# HTTPTransport：真实网络（可配重试/代理/证书）
transport = httpx.HTTPTransport(retries=3, proxy="http://localhost:8080")
```

`base_url="http://testserver"` 里的 `testserver` 是个**占位主机名**（不会真去连）——ASGITransport 不看 host，只把请求交给 app；但 httpx 要求 URL 合法，故给个占位。本项目用同一写法（见 7.4）。

### 5.6 超时、SSL、代理、事件钩子

```python
# 细粒度超时（连接/读/写/池）
timeout = httpx.Timeout(10.0, connect=5.0)
client = httpx.Client(timeout=timeout)

# SSL / 证书
client = httpx.Client(verify=False)                 # 关证书校验（仅测试）
client = httpx.Client(cert="/path/cert.pem")        # 客户端证书

# 代理
client = httpx.Client(proxy="http://localhost:8080")

# 事件钩子（统一记录请求/响应，如加鉴权头、打日志）
def log_request(request: httpx.Request):
    print(f">> {request.method} {request.url}")
client = httpx.Client(event_hooks={"request": [log_request]})
```

### 5.7 异步并发

```python
import asyncio, httpx

async def main():
    async with httpx.AsyncClient() as client:
        # 多个请求并发，一个事件循环里同时飞
        r1, r2 = await asyncio.gather(
            client.get("https://example.com/a"),
            client.get("https://example.com/b"),
        )
```

`AsyncClient` 可安全地在多个协程间共享（同一 `async with` 块内）；`asyncio.gather` 并发发请求是它相对同步 `requests` 的核心优势。

---

## 六、用 httpx 测 FastAPI（集成测试专章）

### 6.1 核心思路：不起服务器，进程内直连 app

传统「起 uvicorn + requests 打真实端口」的问题：慢、占端口、并发测试互相干扰、CI 里端口冲突。httpx 的 `ASGITransport` 让请求在**同一进程内**直接交给 FastAPI 的 ASGI app 处理，走完真实的「路由 → 依赖 → 校验 → 序列化」链路，但不碰网络、不占端口。

### 6.2 httpx 0.28 破坏性变更（务必知道）

httpx 0.28.0 起**移除了** `Client(app=...)` / `AsyncClient(app=...)` 的 `app` 快捷参数，旧教程写法已失效：

```python
# ❌ 0.27 及更早（0.28 已移除，会 TypeError）
async with httpx.AsyncClient(app=app, base_url="http://testserver") as client: ...

# ✅ 0.28+（本项目采用）
transport = httpx.ASGITransport(app=app)
async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client: ...
```

本项目 `backend/pyproject.toml` 钉 `httpx>=0.28.1`，`conftest.py` 用的正是 `ASGITransport` 形态（已核实）。

### 6.3 最小可运行示例

```python
# test_demo.py
import httpx, pytest
from app.main import app

pytestmark = pytest.mark.anyio

@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

### 6.4 依赖覆盖：dependency_overrides

FastAPI 的依赖注入系统允许在测试时把某个依赖（如 `get_db`、`get_current_user`）整体替换成测试替身：

```python
from app import database

def _override_get_db():
    yield test_session            # 换成绑定内存库的测试 session

app.dependency_overrides[database.get_db] = _override_get_db
# ... 跑测试 ...
app.dependency_overrides.clear()  # 用完清理，避免污染其他测试
```

- key 是**原依赖函数对象**，value 是**替换函数**（可以是生成器函数）；
- 本项目用它把 `get_db` 换成绑定内存库的 `db_session`，让「请求链路」与「测试断言」操作**同一个内存库会话**（见 7.4）；
- 典型用途：换数据库、绕过真实鉴权、mock 外部服务。

### 6.5 lifespan 与建表时机（重要陷阱）

**`ASGITransport` 默认不触发 ASGI lifespan 事件**（startup/shutdown）。也就是说 FastAPI 里 `lifespan` 上下文或 `@app.on_event("startup")` 做的建表、初始化**不会自动执行**。三种应对：

| 方式 | 做法 | 本项目 |
|---|---|---|
| 手动建表 | fixture 里显式 `Base.metadata.create_all(engine)` | ✅ 采用（见 7.3） |
| LifespanManager | 装 `asgi-lifespan`，用 `LifespanManager(app)` 包住触发 lifespan | ✗（多一个依赖） |
| starlette TestClient | `with TestClient(app) as c:` 默认触发 lifespan | ✗（本项目走异步） |

本项目选**手动建表**，反而更可控——表何时建、何时清由测试说了算，不依赖 app 启动副作用（`conftest.py` 注释原话，已核实）。

### 6.6 同步 TestClient 对照写法

不想引入异步插件时，可用 starlette 的同步 `TestClient`（底层仍是 httpx）：

```python
from fastapi.testclient import TestClient

def test_health():
    with TestClient(app) as client:        # with 触发 lifespan
        resp = client.get("/api/health")   # 无 await
        assert resp.status_code == 200
```

`TestClient` 自动处理 lifespan，`dependency_overrides` 用法一致。适合纯同步项目；本项目为与 async 路由对齐选了 `AsyncClient`（1.5 已对比）。

### 6.7 可复用的集成测试骨架

综合以上，一个带数据库隔离的 FastAPI 集成测试骨架（本项目 `conftest.py` 的精简版，完整逐段解读见第七节）：

```python
# conftest.py
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"   # ① 必须早于 import app

import httpx, pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app                             # ② env 已就位再导入
from app import database
from app.models import Base

engine = create_engine("sqlite:///:memory:",
                       connect_args={"check_same_thread": False},
                       poolclass=StaticPool)          # ③ 内存库共享同一连接
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

@pytest.fixture
def db_session():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)                  # ④ 每个用例重建干净表
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)

@pytest.fixture
async def client(db_session):
    def _override_get_db():
        yield db_session
    app.dependency_overrides[database.get_db] = _override_get_db   # ⑤ 依赖覆盖
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
```

五处编号 ①~⑤ 正是本项目 conftest 的五个关键设计点，第七节逐一展开其与「为什么这么写」。

---

## 七、本项目测试体系实战（pipeline-fault-tracker）

> 本节把 `backend/tests/` 的真实代码按当前事实逐段解读为可复用范例。所有代码引用均来自对源码的逐行核实；**本会话未重跑测试**，运行结果以本机 `cd backend; uv run pytest` 为准。解读顺序：先看全景（7.1），再拆地基 `conftest.py`（7.2–7.4），然后自底向上过四层用例（7.5–7.7），最后收敛为组织规范（7.8）与运行方式（7.9）。

### 7.1 现状基线：五个文件、四层结构

`backend/tests/` 目录当前五个文件，行数与职责如下（已核实）：

| 文件 | 层 | 行数 | 测什么 | 关键手法 |
|---|---|---|---|---|
| `conftest.py` | 地基 | 95 | 环境隔离 + 4 个共享 fixture | 环境变量前置覆盖、内存库、依赖覆盖 |
| `test_schemas.py` | 第 1 层（单元） | 158 | Pydantic 字段约束 | 纯构造 + `pytest.raises(ValidationError)` |
| `test_crud.py` | 第 2 层（单元） | 240 | crud 数据访问 + 业务规则 | 内存库 `db_session` + 领域异常 |
| `test_api_pipelines.py` | 第 3+4 层（集成） | 63 | `/api/pipelines` 端点链路 | `client` + `ASGITransport` |
| `test_api_faults.py` | 第 3+4 层（集成） | 225 | `/api/faults` 端点链路 | `client` + 统一错误体断言 |

**依赖与配置**（来自 `backend/pyproject.toml`，已核实）：

```toml
[dependency-groups]
dev = ["httpx>=0.28.1", "pytest>=9.1.1"]   # 只有两个 dev 依赖，异步测试靠 anyio（FastAPI 传递依赖）

[tool.pytest.ini_options]
testpaths = ["tests"]        # 只收集 tests/，不误扫 alembic/、seed.py、rollback_demo.py
pythonpath = ["."]           # backend/ 入 sys.path，import app.* 才可解析（因 package = false）
addopts = "-v --tb=short"    # 默认逐条列用例名 + 精简回溯
```

**四层设计意图**：同一条业务规则（如「done 终态不可逆」）会在 crud 层和 API 层各测一次——

- **crud 层**（`test_crud.py`）：直接调 `crud.transition_fault(...)`，断言抛 `InvalidTransitionError`。定位精确、跑得快（不序列化、不走 HTTP），失败时一眼看出是业务规则问题。
- **API 层**（`test_api_faults.py`）：经 `PATCH /api/faults/{id}/transition` 走完整链路，断言 `409` + `code == "invalid_transition"`。验证「异常 → HTTP 状态码 + 统一错误体」的端到端映射没接错。

两层不是重复，而是**分工**：底层保规则正确，顶层保「规则正确地被翻译成 HTTP 契约」。金字塔形态——底层用例多而快，顶层用例少而全。

### 7.2 conftest.py ①：环境隔离必须早于 `import app`

这是整个测试体系最关键、也最容易踩坑的一步。`conftest.py` 开头（已核实）：

```python
import os

# ---- ① 环境隔离：必须先于任何 app.* 导入 ----
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DB_ECHO"] = "false"

from app import database  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
```

**为什么环境变量必须写在 `import app.*` 之前？**（`conftest.py` 注释已说明，此处展开）

1. `app/config.py` 的 `settings` 是**模块级单例**——`settings = Settings()` 在模块第一次被 import 时就执行，此刻读取 `.env` 与环境变量并**固化**，之后再改 `os.environ` 也不会重新加载。
2. `app/database.py` 的 `engine` 同样是**模块级创建**——`engine = create_engine(settings.DATABASE_URL, ...)` 在 import 时就用当时 `settings` 里的 URL 建好连接池。
3. pydantic-settings 的取值优先级是 **环境变量 > `.env` 文件 > 字段默认值**（注释标注「已核实 config.py」）。所以在 import 前设 `os.environ["DATABASE_URL"]`，能让 `settings.DATABASE_URL` 读到内存库地址，`engine` 随之绑定内存库。

**顺序错了会怎样**：若先 `import app.main` 再设环境变量，`settings` 与 `engine` 已经用 `.env` 里的开发库地址（`fault_tracker.db`）固化，测试就会**读写真实开发库**——污染数据、且结果不可重复。这是本项目测试隔离的第一道防线。

**`# noqa: E402` 是什么**：E402 是 flake8/ruff 的「module level import not at top of file」告警。因为这里故意把 import 放在 `os.environ[...] = ...` 之后（语句不在文件最顶部），静态检查会报 E402，用 `# noqa: E402` 逐行抑制。这是「环境前置覆盖」这一必要手法的代价，属有意为之。

> 注意注释里的细节：`from app import database` 导入后，`database.engine` 也指向内存库（因为 env 已覆盖），**但测试并不用它**——测试另建 `test_engine`（见 7.3），`database` 模块只是用来拿到 `get_db` 这个函数对象做依赖覆盖（见 7.4）。

### 7.3 conftest.py ②③④：测试专用 engine 与 `db_session`

环境隔离好了，接着建**测试专用**的 engine 与 session 工厂（已核实）：

```python
test_engine: Engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)
```

**为什么另建 `test_engine`，不直接用 `app.database.engine`？**（注释已答，展开）

SQLite 的 `:memory:` 库有个反直觉特性：**每个连接持有各自独立的一份内存数据**。默认连接池（`QueuePool`）会按需发放多个连接——建表的连接与查询的连接若不是同一个，就会「建了表却查不到」「插了数据另一个连接看不见」。

三个参数各解一个问题：

| 参数 | 作用 |
|---|---|
| `poolclass=StaticPool` | **强制所有 session 复用同一个连接**，共享同一份内存数据——解决「多连接数据不互通」 |
| `connect_args={"check_same_thread": False}` | 允许该连接被多个线程使用（pytest 与 anyio 的事件循环可能跨线程）——否则 SQLite 报「connection created in a different thread」 |
| `"sqlite:///:memory:"` | 纯内存库，测试结束即销毁，绝不碰磁盘上的 `fault_tracker.db` |

**`db_session` fixture：每个用例一套干净表**（已核实）：

```python
@pytest.fixture
def db_session() -> Iterator[Session]:
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(test_engine)
```

逐段拆解这个 `yield` fixture 的生命周期：

1. **yield 前（setup）**：`drop_all` 再 `create_all`——先清后建，保证拿到的是**空表**。因为 `StaticPool` 让内存库在整个会话期间是同一个连接、数据会累积，所以每个用例开始必须先 `drop_all` 抹掉上个用例的残留。
2. **yield**：把 `session` 交给测试体。测试里 `crud.create_pipeline(db_session, ...)` 等直接用这个 session 读写内存库。
3. **finally（teardown）**：`session.close()` + 再 `drop_all`——无论用例成功还是抛异常都执行，双重保证不留脏数据。

**这套设计换来的性质**（注释原话：「测试可重复跑、无脏数据残留」）：任何测试看到的都是空库，**不依赖执行顺序**，单跑 / 乱序跑 / 全量跑结果一致。这是 `function` 级 scope（默认）+ drop/create 组合的价值。

> `expire_on_commit=False` 与 `autoflush=False` 与 `app.database.SessionLocal` 的参数保持一致（注释已核实）。`expire_on_commit=False` 让 commit 后对象属性仍可读（否则 commit 后访问属性会触发 refresh，在内存库/已关闭场景易报错）；测试里 `_make_pipeline` 造数后还能 `assert p.code == "LINE-A"` 就靠它。

**这里呼应第六节的陷阱**：`ASGITransport` 不触发 lifespan，所以 app 里靠 `lifespan`/`init_models` 自动建表的逻辑在测试中不会执行——建表完全由 `db_session` 的 `create_all` 显式完成，「表何时建、何时清，测试自己说了算」（注释原话）。

### 7.4 conftest.py ⑤：`client` fixture（集成测试入口）

最上层是集成测试用的 `client`，它**依赖 `db_session`**（fixture 注入 fixture），把「HTTP 请求链路」和「测试断言」绑到同一个内存库会话（已核实）：

```python
@pytest.fixture
async def client(db_session: Session) -> AsyncIterator[httpx.AsyncClient]:
    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[database.get_db] = _override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
```

六个关键点逐一说明：

1. **`async def` + 参数 `db_session`**：这是异步 fixture（因为要 yield `AsyncClient`）。参数里的 `db_session` 由 pytest 自动注入——于是 `client` 与 `db_session` **共享同一套内存表**。测试里既能用 `client` 发请求，理论上也能直接查 `db_session`，看到的是同一份数据。
2. **`_override_get_db`**：一个生成器函数，`yield db_session`——把 app 的 `get_db` 依赖整体替换成「返回测试 session」。这样请求处理链路里 `Depends(get_db)` 拿到的就是内存库 session，而非开发库。
3. **`app.dependency_overrides[database.get_db] = _override_get_db`**：key 是**原依赖函数对象** `database.get_db`，value 是替换函数。这是 FastAPI 官方推荐的测试替身机制（第六节 6.4 已讲通法）。
4. **`httpx.ASGITransport(app=app)`**：把请求直连进 app 对象，不起 uvicorn、不占端口（httpx 0.28+ 的正确写法，`app=` 简写已移除）。
5. **`base_url="http://testserver"`**：占位域名——因为不走真实网络，这个 host 不会真的解析，只是让 `client.get("/api/pipelines")` 这样的相对路径能拼成完整 URL。
6. **`async with ... yield ac` + `dependency_overrides.clear()`**：`async with` 确保 `AsyncClient` 用完正常关闭（连接资源释放）；fixture 结束时 `clear()` 清空覆盖表，**避免污染下一个测试**——否则覆盖会残留到别的用例。

> `anyio_backend` fixture（`scope="session"`，返回 `"asyncio"`）是配套的第四个 fixture：anyio 的 pytest 插件要求显式声明异步后端，`session` 级因为整个测试会话用同一个后端即可，无需每个用例重建（呼应 3.1 scope 约束与 2.5 异步插件）。

至此，`conftest.py` 的四个 fixture（`db_session`、`client`、`anyio_backend` 三个显式 + 环境隔离这一隐式地基）构成完整测试地基：**环境隔离保证不碰开发库，内存库 + StaticPool 保证数据互通，drop/create 保证用例隔离，依赖覆盖 + ASGITransport 保证集成测试走真实链路却不起服务器**。

---

### 7.5 第 1 层：`test_schemas.py`——把 Pydantic 约束变成回归网

这一层**不碰数据库、不走 HTTP**，纯粋地构造 Pydantic 模型并断言其校验行为。两个辅助函数是本层的灵魂（已核实）：

```python
def _fault_payload(**overrides):
    """合法的 FaultCreate 输入基底；overrides 覆盖单字段制造非法用例。"""
    data = {
        "pipeline_id": 1,
        "location": "3号工位传送带",
        "occurred_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        "symptom": "传送带异响并卡死",
    }
    data.update(overrides)
    return data


def _error_fields(exc: ValidationError) -> set[tuple]:
    """提取 ValidationError 里所有出错字段的 loc，便于断言“错的正是这个字段”。"""
    return {err["loc"] for err in exc.errors()}
```

**手法一：造数基底 + 单字段覆盖**。`_fault_payload()` 先给一份**全合法**的输入，再用 `**overrides` 只改其中一字段把它变非法。好处：每个异常用例只关心自己那一个字段，其余字段固定合法，失败时定位无歧义。

**手法二：`pytest.raises` + `_error_fields` 精确定位**。不只断言「抛了 ValidationError」，还要断言「错的正是这个字段」（已核实）：

```python
@pytest.mark.parametrize("missing", ["pipeline_id", "location", "occurred_at", "symptom"])
def test_e1_missing_required_field(self, missing):
    payload = _fault_payload()
    del payload[missing]
    with pytest.raises(ValidationError) as exc_info:
        FaultCreate(**payload)
    assert (missing,) in _error_fields(exc_info.value)
```

这里两个要点：① `as exc_info` 把异常对象捕到手，`exc_info.value` 就是 `ValidationError` 实例；② `parametrize` 把四个必填字段的缺失拆成四个独立用例，每个都验证 `loc` 指向正确字段。比写四个几乎一样的函数简洁得多（呼应 3.2 参数化）。

**手法三：边界成对断言**。边界值不是只测「该拒的拒」，而是**该拒的拒 + 该过的过成对出现**，防止约束写偏（已核实）：

```python
def test_b2_symptom_length(self):
    with pytest.raises(ValidationError):
        FaultCreate(**_fault_payload(symptom="异响了"))          # 4 字 < 5 拒
    assert FaultCreate(**_fault_payload(symptom="x" * 5))       # 恰好 5 字过
    assert FaultCreate(**_fault_payload(symptom="x" * 1000))    # 恰好 1000 字过
    with pytest.raises(ValidationError):
        FaultCreate(**_fault_payload(symptom="x" * 1001))       # 1001 > 1000 拒
```

`min_length=5` 的四个关键点（4/5/1000/1001）全覆盖：下界内/外、上界内/外。这是边界测试的标准姿势——卡在约束的两侧各一个值。

**手法四：时态健壮性**。`test_b4_occurred_at_clock_skew_tolerance` 同时测 naive 与 aware 两种时态（已核实）：

```python
naive = datetime.now() + timedelta(seconds=30)          # naive：未来 30s，60s 容差内→放行
assert FaultCreate(**_fault_payload(occurred_at=naive.isoformat()))
aware = datetime.now(timezone.utc) + timedelta(seconds=30)  # aware（UTC）：同样放行
assert FaultCreate(**_fault_payload(occurred_at=aware.isoformat()))
aware_far = datetime.now(timezone.utc) + timedelta(seconds=120)  # 超容差→拒绝
with pytest.raises(ValidationError):
    FaultCreate(**_fault_payload(occurred_at=aware_far.isoformat()))
```

意义：证明 validator 的 aware/naive 换算不炸——时区感知与不感知的时间都能正确比较「是否超 60s 容差」。这类时态边界是日期字段最容易遗漏、也最容易出隐性 bug 的地方。

### 7.6 第 2 层：`test_crud.py`——业务规则与状态机

这一层用 `db_session` fixture 操作内存库，直接调 `crud` 层函数，验证**数据访问 + 业务规则**。三个造数辅助函数保持用例本体简洁（已核实）：

```python
def _make_pipeline(db, code="LINE-A", name="总装线A"):
    return crud.create_pipeline(db, schemas.PipelineCreate(code=code, name=name))

def _make_fault(db, pipeline_id, minutes_ago=60, symptom="传送带异响并卡死"):
    return crud.create_fault(db, schemas.FaultCreate(
        pipeline_id=pipeline_id, location="3号工位传送带",
        occurred_at=datetime.now() - timedelta(minutes=minutes_ago), symptom=symptom,
    ))

def _to_done(db, fault_id, note="更换皮带并复测正常"):
    """把故障推到 done 终态（先 processing 再 done），供锁定/不可逆类用例复用。"""
    crud.transition_fault(db, fault_id, FaultStatus.processing, None)
    return crud.transition_fault(db, fault_id, FaultStatus.done, note)
```

**手法一：正例测副作用，不只测返回值**。`test_n3_create_fault_forces_pending` 不是只看「创建成功」，而是逐项验证副作用（已核实）：

```python
def test_n3_create_fault_forces_pending(self, db_session):
    p = _make_pipeline(db_session)
    f = _make_fault(db_session, p.id)
    assert f.status is FaultStatus.pending   # 初始状态强制 pending
    assert f.pipeline.code == "LINE-A"       # 返回对象含预加载 pipeline
    assert f.handling_note is None
    assert f.closed_at is None
```

注意 `f.status is FaultStatus.pending` 用 `is` 而非 `==`——枚举成员是单例，`is` 更严谨。`f.pipeline.code` 能直接访问证明返回对象已预加载关联（否则会是 lazy load）。

**手法二：`pytest.raises` 领域异常**。异常路径断言的是**具体领域异常**（非笼统的 `Exception`），已核实的异常类型有：`PipelineNotFoundError`、`FaultNotFoundError`、`PipelineCodeDuplicateError`、`InvalidTransitionError`、`HandlingNoteRequiredError`、`HandlingNoteLockedError`：

```python
def test_e4_duplicate_code(self, db_session):
    _make_pipeline(db_session, code="LINE-A")
    with pytest.raises(PipelineCodeDuplicateError):
        _make_pipeline(db_session, code="LINE-A", name="另一条线")
```

**手法三：状态机全覆盖用 parametrize**。「done 终态不可逆」需要验证 done → 三个目标状态全部被拒，`parametrize` 一行展开三个用例（已核实）：

```python
@pytest.mark.parametrize("target", [FaultStatus.pending, FaultStatus.processing, FaultStatus.done])
def test_e6_done_is_terminal(self, db_session, target):
    p = _make_pipeline(db_session)
    f = _make_fault(db_session, p.id)
    _to_done(db_session, f.id)
    with pytest.raises(InvalidTransitionError):
        crud.transition_fault(db_session, f.id, target, "试图复活已完成记录")
```

同样手法用于 `test_e5_same_status_transition`（同状态流转 3 种）、`test_e7_done_requires_note`（`@pytest.mark.parametrize("note", [None, "", "     "])` ——不传/空串/纯空格三种都拒）。这比手写三个函数更能表达「这是一组等价类」的意图（呼应 3.2 参数化、 3.4 raises）。

### 7.7 第 3+4 层：`test_api_*.py`——HTTP 端点集成

最顶层用 `client` fixture 发真请求，走完整「路由 → 依赖 → 校验 → 业务 → 序列化」链路。两个文件开头都有 `pytestmark = pytest.mark.anyio`（模块级标记，文件内所有 async 用例一次生效，见 2.5）。

**手法一：从入口造数**（`_seed_pipeline` / `_seed_fault`）。集成测试不直接用 crud 插数据，而是经 API 造（已核实）：

```python
async def _seed_pipeline(client, code="LINE-A") -> int:
    """经 API 造一条流水线，返回 id（集成测试从入口造数，链路更真）。"""
    resp = await client.post("/api/pipelines", json={"code": code, "name": f"名称-{code}"})
    assert resp.status_code == 201
    return resp.json()["id"]
```

为何不直接 `crud.create_pipeline`？因为集成测试的价值在于「走真实链路」——从 HTTP 入口造数，能顺带验证 POST 端点本身可用，造数与被测链路一致。

**手法二：统一错误体断言**（`_assert_error_shape`）。本项目所有错误响应都是 `{code, message, details}` 结构，用一个辅助函数集中断言（已核实）：

```python
def _assert_error_shape(payload, code):
    """断言统一错误结构 ErrorOut：{code, message, details}，details 为列表。"""
    assert payload["code"] == code
    assert isinstance(payload["message"], str) and payload["message"]
    assert isinstance(payload["details"], list)
```

**手法三：状态码 + 业务码 + 字段路径三重断言**。异常用例不只断言 HTTP 状态码，还断言业务 `code` 与 `details` 里的字段路径（已核实）：

```python
async def test_e2_create_unknown_pipeline(self, client):
    resp = await client.post("/api/faults", json=_fault_body(999))
    assert resp.status_code == 404
    _assert_error_shape(resp.json(), "pipeline_not_found")
    assert resp.json()["details"][0]["field"] == "body.pipeline_id"
```

三重断言的价值：状态码对了不够，还要保证错误码（`pipeline_not_found`）与出错字段位置（`body.pipeline_id`）都对——前端靠这些精确提示用户哪个字段错。

**手法四：正例断言响应头与嵌套结构**。`test_n1_create_fault` 验证 201 响应带 `Location` 头、嵌套 `pipeline`、初始状态（已核实）：

```python
async def test_n1_create_fault(self, client):
    pid = await _seed_pipeline(client)
    resp = await client.post("/api/faults", json=_fault_body(pid))
    assert resp.status_code == 201
    assert resp.headers["Location"] == f"/api/faults/{resp.json()['id']}"
    data = resp.json()
    assert data["status"] == "pending"            # 初始状态由后端强制
    assert data["pipeline"]["code"] == "LINE-A"   # 嵌套 pipeline
```

**手法五：查询参数越界用 parametrize**。`test_e9` 把多个非法查询参数归为一个等价类（已核实）：

```python
@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"size": 999}, {"status": "archived"}, {"pipeline_id": 0}],
)
async def test_e9_query_param_out_of_range(self, client, params):
    resp = await client.get("/api/faults", params=params)
    assert resp.status_code == 422
    _assert_error_shape(resp.json(), "validation_error")
```

四个越界参数（page=0 下溢、size=999 上溢、status 非法枚举、pipeline_id=0）共享同一预期：422 + `validation_error`。用 parametrize 表达「这四个属同一类错误」，新增一个越界参数只需往列表里加一项。

### 7.8 测试组织规范（可复用清单）

从五个文件抽出贯穿全文的组织惯例，可直接搬到其他项目：

1. **验收标准清单先行**：每个测试文件开头用注释写出【正常/异常/边界】三类验收标准并编号（N1/N2…、E1/E2…、B1/B2…），**先定标准再落测试**。用例名与清单一一对应（`test_n1_*`/`test_e1_*`/`test_b1_*`），任何人看用例名就知道它验证哪条标准。
2. **class 三分组**：用 `TestHappyPath`/`TestErrorPath`/`TestBoundary`（或 crud 层的 `TestPipelineHappy`/`TestFaultError` 等）把用例按正常/异常/边界分类，报告层次清晰。
3. **下划线辅助函数造数**：`_make_*`/`_seed_*`/`_*_payload` 把造数细节收进辅助函数，用例本体只留「造数 → 执行 → 断言」三行，可读性极高。
4. **断言辅助函数收敛重复**：`_error_fields`/`_assert_error_shape` 把多处重复的断言逻辑集中一处，错误体结构变了只改一处。
5. **分层不越界**：schema 层不碰 db，crud 层不走 HTTP，API 层从入口造数。每层只验证自己职责内的事，不跨层損益。
6. **命名 id 化**：用 `parametrize` 时关注 `ids` 可读性（本项目多用枚举/字典列表，pytest 自动生成的 id 已够清晰；必要时可显式传 `ids=`，见 3.2）。

### 7.9 运行与预期

在 `backend/` 目录执行（PowerShell 用 `;` 分隔，不用 `&&`）：

```powershell
cd backend

uv run pytest                              # 全量跑（addopts 已带 -v --tb=short）
uv run pytest tests/test_schemas.py        # 只跑第 1 层
uv run pytest tests/test_crud.py           # 只跑第 2 层
uv run pytest tests/test_api_faults.py     # 只跑故障 API 集成
uv run pytest -k "e5 or e6"               # 只跑状态机相关异常用例
uv run pytest -m anyio                     # 只跑异步（集成）用例
```

**预期行为**：

- 全程走内存库，**不碰磁盘上的 `fault_tracker.db`**——跑完测试开发库数据不变（由 7.2 环境隔离 + 7.3 内存库保证）。
- 用例**不依赖执行顺序**，单跑/乱序跑/全量跑结果一致（由 `db_session` 的 drop/create 保证）。
- 集成测试**不起 uvicorn、不占端口**（由 `ASGITransport` 保证）。

> 声明：本会话**未实际重跑测试**，上述「预期行为」基于对 `conftest.py` 隔离机制的源码核实推导，非本次执行结果。实际通过情况以本机 `uv run pytest` 输出为准（呼应 4.2 验证须给证据）。

---

## 八、坑点汇总

把全文与本项目实战中遇到的坑集中成一张「现象 → 原因 → 解法」表，标★者为**本项目已核实**的特有坑，其余为 pytest/httpx 官方文档行为。

### 8.1 环境与隔离

| 现象 | 原因 | 解法 | 出处 |
|---|---|---|---|
| ★ 测试意外读写开发库 `fault_tracker.db` | `settings`/`engine` 是模块级单例，import 时就固化了 URL | 在 `import app.*` **之前** `os.environ["DATABASE_URL"]="sqlite:///:memory:"` | 7.2 |
| ★ `monkeypatch.setenv` 对 `DATABASE_URL` 无效 | monkeypatch 在测试函数内才生效，而单例 import 时已固化 | 改用模块顶部直接赋值 `os.environ[...]` | 7.2 |
| ★ 建了表却查不到 / 数据互相看不见 | SQLite `:memory:` **每个连接一份独立数据** | `poolclass=StaticPool` 强制复用同一连接 | 7.3 |
| ★ SQLite 报「connection created in a different thread」 | 事件循环/测试跨线程使用连接 | `connect_args={"check_same_thread": False}` | 7.3 |
| ★ flake8/ruff 报 E402 | import 故意放在 `os.environ` 赋值之后（不在顶部） | 逐行 `# noqa: E402` 抑制 | 7.2 |

### 8.2 fixture 与异步

| 现象 | 原因 | 解法 | 出处 |
|---|---|---|---|
| `ScopeMismatch` 报错 | 高 scope fixture 依赖了低 scope（如 session 注入 function） | 拉齐 scope，或把低scope资源改为高scope | 3.1 |
| `async def` 测试被跳过/报「async def functions are not natively supported」 | 没装/没标记异步插件 | `pytestmark = pytest.mark.anyio` + `anyio_backend` fixture（或 pytest-asyncio） | 2.5 |
| ★ 集成测试表未建/报错 | `ASGITransport` **不触发 lifespan**，app 的 startup 建表不执行 | 在 `db_session` 里显式 `Base.metadata.create_all(...)` | 6.5 / 7.3 |
| 用例间数据污染 | `dependency_overrides` 未清理，残留到下个用例 | fixture 结束时 `app.dependency_overrides.clear()` | 7.4 |
| commit 后访问对象属性报错/触发多余查询 | `expire_on_commit=True`（默认）使 commit 后属性过期 | 测试 session 设 `expire_on_commit=False` | 7.3 |
| `Test*` 类里的用例没被收集 | 类定义了 `__init__` 方法 | 去掉 `__init__`，用 fixture 注入代替构造 | 2.4 |

### 8.3 httpx 与集成测试

| 现象 | 原因 | 解法 | 出处 |
|---|---|---|---|
| `AsyncClient(app=app)` 报 `TypeError` | httpx **0.28.0 起移除了 `app=` 快捷参数** | `transport=httpx.ASGITransport(app=app)` 再传给 `AsyncClient` | 6.2 |
| 请求报 URL 不合法/host 无法解析 | `AsyncClient` 未设 `base_url`，相对路径无法拼完整 URL | `base_url="http://testserver"`（占位 host，不真连） | 6.7 / 7.4 |
| 响应体读取乱码/类型不对 | 混淆了 `.text`（str）与 `.json()`（dict） | JSON 接口用 `.json()`；需原始文本才用 `.text` | 5.4 |
| 连接资源未释放警告 | `AsyncClient` 未正常关闭 | 用 `async with httpx.AsyncClient(...) as ac:` 管理生命周期 | 5.1 / 7.4 |

### 8.4 断言与参数化

| 现象 | 原因 | 解法 | 出处 |
|---|---|---|---|
| 异常用例「假阳性」（抛了别的异常也通过） | `pytest.raises(Exception)` 太宽泛 | 精确到具体异常类型（如 `InvalidTransitionError`） | 3.4 / 7.6 |
| 只知报错不知错哪个字段 | 只断言了「抛没抛」 | `as exc_info` + 断言 `exc_info.value.errors()` 的 `loc` | 3.4 / 7.5 |
| `parametrize` 传空列表用例消失 | 空参数列表会生成 0 个用例（或报 skip） | 确保参数列表非空；必要时显式 `ids=` 提高可读性 | 3.2 |
| 浮点断言时而失败 | `==` 对浮点不精确 | `pytest.approx(...)` | 3.4 |
| 枚举断言不稳定 | 用 `==` 比较可能与同值不同类型混淆 | 枚举成员用 `is`（单例） | 7.6 |

---

## 九、命令速查表

本项目统一用 **uv 工作流**，命令均在 `backend/` 目录执行；PowerShell 语句分隔用 `;` 不用 `&&`。

### 9.1 pytest 运行与筛选

| 命令 | 作用 |
|---|---|
| `uv run pytest` | 全量跑（addopts 已带 `-v --tb=short`） |
| `uv run pytest tests/test_crud.py` | 只跑指定文件 |
| `uv run pytest tests/test_crud.py::TestFaultError` | 只跑指定类 |
| `uv run pytest "tests/test_crud.py::TestFaultError::test_e6_done_is_terminal"` | 只跑单个用例（节点 id） |
| `uv run pytest -k "transition"` | 按关键字筛选用例名 |
| `uv run pytest -k "e5 or e6"` | 多关键字组合 |
| `uv run pytest -m anyio` | 按 marker 筛选（只跑异步用例） |
| `uv run pytest -m "not slow"` | 排除某 marker |
| `uv run pytest --collect-only` | 只列出将运行的用例，不执行 |

### 9.2 pytest 输出与失败控制

| 命令 | 作用 |
|---|---|
| `uv run pytest -v` / `-q` | 更详细 / 更简洁输出 |
| `uv run pytest -s` | 不捕获 stdout（看 `print` 输出） |
| `uv run pytest --tb=long` / `short` / `line` | 回溯详细度 |
| `uv run pytest -rA` | 末尾汇总所有用例（含通过）的简短信息 |
| `uv run pytest -x` | 遇第一个失败就停 |
| `uv run pytest --maxfail=3` | 最多 3 个失败后停 |
| `uv run pytest --pdb` | 失败时自动进入调试器 |
| `uv run pytest --durations=10` | 列出最慢的 10 个用例 |

### 9.3 pytest 重跑与缓存

| 命令 | 作用 |
|---|---|
| `uv run pytest --lf` | 只跑上次失败的（last-failed） |
| `uv run pytest --ff` | 先跑上次失败的，再跑其余（failed-first） |
| `uv run pytest --nf` | 只跑新增的用例（new-first） |
| `uv run pytest --stepwise` | 从上次失败处逐步往下跑 |
| `uv run pytest --cache-clear` | 清缓存后再跑 |

### 9.4 插件扩展（需先装）

| 命令 | 作用 | 安装 |
|---|---|---|
| `uv run pytest --cov=app --cov-report=term-missing` | 覆盖率报告（含未覆盖行号） | `uv add --dev pytest-cov` |
| `uv run pytest -n auto` | 多进程并行（按 CPU 核数） | `uv add --dev pytest-xdist` |

> 本项目 dev 依赖组当前**只有 `pytest` 与 `httpx`**（已核实），未装 cov/xdist；上表为可选扩展，装前请遵循依赖台账规范（说明装什么/为何装，装后补 `DEPENDENCIES.md`）。

### 9.5 httpx 代码速查

| 场景 | 写法 |
|---|---|
| 同步请求 | `with httpx.Client(base_url=...) as c: c.get("/x")` |
| 异步请求 | `async with httpx.AsyncClient(...) as c: await c.get("/x")` |
| 测 FastAPI（0.28+） | `transport=httpx.ASGITransport(app=app)` |
| 发 JSON | `c.post("/x", json={...})` |
| 查询参数 | `c.get("/x", params={"page": 1})` |
| 表单/文件 | `c.post("/x", data={...})` / `files={...}` |
| 自定义头/超时 | `c.get("/x", headers={...}, timeout=5.0)` |
| 读响应 | `r.status_code` / `r.json()` / `r.text` / `r.headers` |
| 状态码抛错 | `r.raise_for_status()`（非 2xx 抛 `HTTPStatusError`） |
| 并发请求 | `await asyncio.gather(c.get("/a"), c.get("/b"))` |

### 9.6 本项目常用组合

```powershell
cd backend

uv run pytest                              # 全量回归
uv run pytest tests/test_schemas.py        # 第 1 层：Pydantic 约束
uv run pytest tests/test_crud.py           # 第 2 层：crud + 业务规则
uv run pytest tests/test_api_faults.py     # 第 3+4 层：故障 API 集成
uv run pytest tests/test_api_pipelines.py  # 第 3+4 层：流水线 API 集成
uv run pytest -k "e5 or e6"                # 只跑状态机相关异常
uv run pytest --lf                         # 只重跑上次失败的
```

---
