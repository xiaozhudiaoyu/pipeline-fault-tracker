# 模块：seed.py —— 开发/演示用模拟数据播种脚本。
#
# 运行（在 backend/ 目录、已 uv sync 的前提下）：
#     .venv\Scripts\python.exe seed.py
#
# 设计要点：
#   · 通过 crud 层写入（而非直接 db.add），让业务规则（唯一性校验等）真实生效；
#   · 幂等：已存在数据则跳过，避免重复播种（需重播请先删除数据库文件）；
#   · 只"加"不做删表/清库等破坏性操作。

from app import crud, schemas
from app.database import SessionLocal, init_models


def seed() -> None:
    """播种 4 条演示 Item，覆盖两种状态。幂等：已有数据则跳过。"""
    init_models()  # 表不存在则创建（可反复运行，不会改已存在的表）
    db = SessionLocal()
    try:
        # ---- 幂等保护：已有数据就跳过，避免重复插入 ----
        existing, _ = crud.list_items(db, page=1, size=1)
        if existing:
            print(f"[skip] 已存在数据，跳过播种（如需重播请先删除数据库文件）。")
            return

        crud.create_item(db, schemas.ItemCreate(name="示例项目A", description="演示用数据：active 状态"))
        crud.create_item(db, schemas.ItemCreate(name="示例项目B", description="演示用数据：active 状态"))
        crud.create_item(db, schemas.ItemCreate(name="示例项目C", description="演示用数据：archived 状态"))
        item_d = crud.create_item(db, schemas.ItemCreate(name="示例项目D", description="演示用数据：创建后归档"))
        crud.update_item(db, item_d.id, schemas.ItemUpdate(status="archived"))

        items, total = crud.list_items(db, page=1, size=100)
        by_status: dict[str, int] = {}
        for it in items:
            by_status[it.status.value] = by_status.get(it.status.value, 0) + 1
        print(f"[ok] 共 {total} 条演示数据，状态分布 {by_status}")
        print("[done] 播种完成。启动后端后可在 http://127.0.0.1:8000/docs 或前端页面查看。")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
