package com.example.fault;

import static org.junit.jupiter.api.Assertions.*;

import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.TestPropertySource;

/**
 * 第三层判定 #2：Flyway 迁移。
 *
 * 对照 Alembic：
 *   Alembic: versions/843f28b00698_baseline.py + b3e19c4d7a52_add_priority.py
 *   Flyway:  db/migration/V1__create_tables.sql + V2__add_priority.sql
 *
 * 核心差异：
 *   Alembic: 有 upgrade() + downgrade()，可回滚。
 *   Flyway:  只向前（V1→V2→V3...），没有 downgrade。写错只能 V3 修正。
 *
 *   Alembic: Python 代码生成 DDL（op.add_column / op.create_table）。
 *   Flyway:  纯 SQL 文件，你手写 DDL。更透明，但要求你会 SQL。
 *
 * 本测试启用 Flyway（覆盖测试默认的 flyway.enabled=false）：
 *   V1 建表 + 种子数据 → V2 加 priority 列 + 回填 → Hibernate validate 校验映射。
 *   如果 validate 失败（实体与表结构不匹配），Spring 上下文直接起不来。
 *
 * 关于 PG 方言：
 *   本 SQL 用 VARCHAR 存枚举（不是 PG 原生 ENUM TYPE），H2/PG 通用。
 *   Python 侧 Alembic 的 "PG CREATE TYPE 顺序坑" 在这里不存在，
 *   因为 JPA @Enumerated(STRING) 根本不用数据库枚举类型。
 */
@DataJpaTest
@TestPropertySource(properties = {
        "spring.flyway.enabled=true",
        "spring.jpa.hibernate.ddl-auto=validate"
})
class FlywayMigrationTest {

    @Autowired
    private PipelineFaultRepository faultRepo;

    @Autowired
    private PipelineRepository pipelineRepo;

    @Autowired
    private UserRepository userRepo;

    @Autowired
    private TestEntityManager em;

    @Test
    @DisplayName("V2 回填：种子故障的 priority 应为 NORMAL（旧库升级场景）")
    void seedFaultBackfilled() {
        // V1 插入的种子故障（id=1），V2 回填 priority='normal'
        List<PipelineFaultEntity> all = faultRepo.findAll();
        assertFalse(all.isEmpty(), "V1 种子数据应存在");

        PipelineFaultEntity seed = all.get(0);
        assertEquals(FaultPriority.NORMAL, seed.getPriority(),
                "V2 应把存量行的 priority 回填为 normal");
        assertEquals("旧故障（升级前登记的）", seed.getSymptom());
    }

    @Test
    @DisplayName("Flyway + validate：新故障能正常存取（schema 匹配）")
    void newFaultWorksAfterMigration() {
        PipelineEntity p = pipelineRepo.findAll().get(0);  // 用种子流水线

        PipelineFaultEntity f = new PipelineFaultEntity(
                "新工位", LocalDateTime.now(), "迁移后新登记的故障");
        f.setPipeline(p);
        f.setPriority(FaultPriority.URGENT);
        faultRepo.save(f);
        em.flush();
        em.clear();

        PipelineFaultEntity reloaded = faultRepo.findById(f.getId()).orElse(null);
        assertNotNull(reloaded);
        assertEquals(FaultPriority.URGENT, reloaded.getPriority());
    }

    @Test
    @DisplayName("DDL 级 ON DELETE SET NULL：删用户不用手动清 FK（数据库自动干）")
    void databaseLevelSetNull() {
        // 准备
        UserEntity user = new UserEntity("flyway_user", "Flyway用户", FaultRole.USER);
        userRepo.save(user);

        PipelineEntity p = pipelineRepo.findAll().get(0);
        PipelineFaultEntity f = new PipelineFaultEntity(
                "工位X", LocalDateTime.now(), "测试DDL级SET NULL");
        f.setPipeline(p);
        f.setCreatedBy(user);
        f.setAssignee(user);
        faultRepo.save(f);
        em.flush();
        Long faultId = f.getId();

        // 清缓存后直接删用户（不手动清 FK！）
        // V1 DDL 里有 ON DELETE SET NULL → 数据库自动把 FK 置空
        em.clear();
        userRepo.deleteById(user.getId());
        em.flush();
        em.clear();

        // 验证：故障仍在，FK 被数据库自动置空
        PipelineFaultEntity reloaded = faultRepo.findById(faultId).orElse(null);
        assertNotNull(reloaded, "故障不应被删");
        assertNull(reloaded.getCreatedBy(), "DDL ON DELETE SET NULL 应自动置空");
        assertNull(reloaded.getAssignee(), "DDL ON DELETE SET NULL 应自动置空");
    }
}
