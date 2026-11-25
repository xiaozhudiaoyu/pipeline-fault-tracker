# backend.app 包入口。
#
# 本项目采用"扁平应用包"结构：app/ 下直接放 config/database/models/schemas/crud/exceptions，
# 路由放 app/routers/。
#
# 不在 __init__.py 里 re-export 业务符号，避免循环导入
# （database.py import models.py 的 Base；若 __init__ 再 import database，链条会绕回来）。
# 各模块按需直接 from app.xxx import yyy 即可。
