# D2 迁移验证辅助脚本（临时，本地保留不入库）。
# 用法：.venv\Scripts\python.exe verify_d2_check.py [数据库文件路径]
# 默认查 fault_tracker.db；传入路径可验证临时/备份库。
# 输出：自定义索引列表 / alembic_version 内容 / 两张表行数 / 表名列表，
# 供 upgrade/downgrade 每一步之后独立实测。
import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "fault_tracker.db"
con = sqlite3.connect(db_path)

indexes = [
    r[0]
    for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'ix_%'"
    )
]
version = con.execute("SELECT * FROM alembic_version").fetchall()
pipelines = con.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0]
faults = con.execute("SELECT COUNT(*) FROM pipeline_faults").fetchone()[0]

print("数据库:", db_path)
print("表:", [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")])
print("索引:", indexes)
print("alembic_version:", version)
print("行数: pipelines =", pipelines, ", pipeline_faults =", faults)
