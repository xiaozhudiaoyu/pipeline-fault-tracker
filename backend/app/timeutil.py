# 模块：业务时间口径的唯一源头 —— 把"业务时间"与"进程所在机器的时区"解耦。
#
# 为什么要单独一个文件：
#   created_at/updated_at/closed_at 的写入走 datetime.now()，occurred_at 的"不得晚于当前"
#   判定走 naive.astimezone() —— 两者都隐含读取【进程时区】。开发机是北京时间（+08:00）
#   时看不出问题，backend 容器默认 UTC，同一句代码就差了 8 小时：
#     · 用户在北京时间 16:26 登记"此刻"，前端发无偏移的北京墙钟，旧 validator 按 UTC 解释
#       → 判成未来 8 小时 → 422「故障发生时间不得晚于当前时间」；
#     · models._local_now() 取到 UTC 墙钟 → 详情/时间线里的登记时间比业务时间早 8 小时。
#   口径集中到本模块后，进程时区不再参与业务时间，改一个配置即可整体切换。
#
# 口径（与 models.py 里不带时区的 DateTime 列一致，落库都是 naive 墙钟）：
#   · 库存【业务时区墙钟】，不存 UTC、不存 tzinfo；
#   · 入参 naive 一律按业务时区解释（前端 el-date-picker 的 value-format 不带偏移）；
#   · 入参 aware 按其自带偏移换算到业务时区再取墙钟（+08:00 与 Z 两种写法等价入库）。
#
# 已知代价与边界：
#   · 用固定 UTC 偏移而不是 zoneinfo 具名时区：tzdata 在本项目只是 psycopg 的 win32
#     传递依赖（未写进 pyproject 直接依赖），容器与 CI 镜像也不保证带系统时区库，
#     固定偏移零依赖、跨平台一致。中国无夏令时，够用；将来若要部署到 DST 地区，
#     改用 zoneinfo 并把 tzdata 显式声明为直接依赖（规则 2.5 走确认）。
#   · 存量数据不修补：切口径之前落库的 created_at 是 UTC 墙钟，会比新数据早 8 小时
#     （开发库演示数据，沿用 models.py 文件头"不修补"的既有裁定）。


from datetime import datetime, timedelta, timezone

from .config import settings


def business_tz() -> timezone:
    """业务时区（固定偏移，取自 settings.business_utc_offset_hours）。"""
    return timezone(timedelta(hours=settings.business_utc_offset_hours))


def business_now() -> datetime:
    """业务时区的"此刻"墙钟（naive，供 ORM default/onupdate 与 closed_at 使用）。"""
    return datetime.now(business_tz()).replace(tzinfo=None)


def to_business_naive(value: datetime) -> datetime:
    """任意时态 → 业务时区 naive 墙钟：naive 按业务时区解释，aware 按自带偏移换算。

    注意这里不能用 astimezone() 处理 naive 输入：Python 会给它补【进程时区】，
    容器（UTC）里就等于把北京时间当成了 UTC 时间，正是本模块要消除的缺陷。
    """
    aware = value if value.tzinfo is not None else value.replace(tzinfo=business_tz())
    return aware.astimezone(business_tz()).replace(tzinfo=None)
