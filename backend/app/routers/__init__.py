# app.routers 包：存放各业务路由模块。
#
# 阶段 2 将在此添加：
#   pipelines.py —— /api/pipelines 流水线主数据接口
#   faults.py    —— /api/faults    故障记录接口（登记/查询/详情/状态流转）
#
# 每个路由模块用 APIRouter() 创建 router 对象，在 main.py 里 include_router 挂载。
# 与 python_learn/todo_api/routers/ 的组织方式一致。
