# backend.app 包入口。
#
# 本项目采用"扁平应用包"结构：app/ 下直接放 config/database/exceptions 等基础模块，
# 业务接入后新增 models/schemas/crud 与 routers/（见技能 SKILL.md「业务接入指南」）。
#
# 不在 __init__.py 里 re-export 符号，避免循环导入；各模块按需直接 from app.xxx import yyy。
