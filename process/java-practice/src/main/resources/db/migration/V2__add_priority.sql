-- V2: 给 pipeline_faults 加 priority 列并回填存量行
-- 对照 Alembic b3e19c4d7a52_add_priority_to_pipeline_faults.py
--
-- Flyway 哲学：只向前、不回滚（没有 Alembic 的 downgrade）。
-- 写错了？只能再写 V3 修正，不能撤销 V2。
--
-- 本 SQL 用 VARCHAR（不是 PG 原生 ENUM TYPE），所以 H2/PG 通用，
-- 不会遇到 Python 侧 Alembic 的 "PG CREATE TYPE 顺序坑"。
-- 原因：JPA @Enumerated(STRING) 映射 VARCHAR，不用数据库枚举类型。
--
-- ★ 大小写坑：@Enumerated(STRING) 存的是枚举常量名（NORMAL），不是 value 字段（"normal"）。
--   Python SQLAlchemy Enum 存 .value（小写）；Java 存 .name()（大写）。
--   所以 SQL 里必须写 'NORMAL'，不能写 'normal'。

ALTER TABLE pipeline_faults
    ADD COLUMN priority VARCHAR(10) NOT NULL DEFAULT 'NORMAL';

-- 回填：存量行（V1 种子数据）统一设为 NORMAL
UPDATE pipeline_faults SET priority = 'NORMAL' WHERE priority IS NULL;
