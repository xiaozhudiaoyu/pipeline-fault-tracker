# app.routers 包：存放各业务路由模块。
#
# 每个路由模块用 APIRouter(prefix="/api/xxx", tags=["xxx"]) 创建 router 对象，
# 在 main.py 里 include_router 挂载；tags 必须与 main.py 的 openapi_tags 一字不差。
#
# 新增实体示例：
#   1. 复制 items.py 为新文件并重命名符号；
#   2. 在 main.py import 并 include_router 挂载；
#   3. 在 main.py 的 openapi_tags 补一条分组说明。
