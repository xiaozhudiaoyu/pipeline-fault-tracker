# versions/ —— Alembic 迁移脚本目录

骨架阶段本目录为空：迁移脚本在业务模型接入后（继承 `app.database.Base`）再生成。

前置：确认 `alembic/env.py` 顶部已取消注释 `from app import models`，
让 autogenerate 能看到模型表结构。

## 场景 A：全新空库（推荐路径）

在 `backend/` 下执行：

```powershell
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "baseline initial schema"
.venv\Scripts\python.exe -m alembic upgrade head
```

autogenerate 对比模型与空库，自动生成完整 CREATE TABLE。

## 场景 B：老库接入（库已存在且表与模型一致）

autogenerate 对「已存在且与模型一致」的表不产出任何 CREATE，基线将为空——
换一台空库跑 `upgrade head` 就无法重建 schema。此时需**手写基线**：

1. 导出真实 DDL（如 SQLite：`sqlite_master` 表）作为列定义依据；
2. 手写 `upgrade()`：按外键依赖顺序 `op.create_table(...)`（先被引用的表，再引用它的表）；
3. `downgrade()` 按相反顺序 `op.drop_table(...)`（先删引用方，再删被引用方）；
4. 老库打标（只写版本号、不重跑 CREATE）：

   ```powershell
   .venv\Scripts\python.exe -m alembic stamp head
   ```

注意：模型中 ORM 层行为（`default=`、`onupdate=`）不进 DDL，照抄真实 DDL 即可，
不要「补全」；Enum 默认渲染为 VARCHAR（无 CHECK 约束，`create_constraint=False`）。

## 常用命令（均在 backend/ 下执行）

| 命令 | 作用 |
|---|---|
| `upgrade head` | 升级到最新版本 |
| `downgrade -1` | 回退一个版本 |
| `stamp <rev>` | 给现有库打标记（只写版本号，不执行迁移） |
| `history` | 查看迁移链 |
| `revision -m "..." --autogenerate` | 对比模型与库差异生成新迁移 |
