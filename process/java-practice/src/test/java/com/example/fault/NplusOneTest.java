package com.example.fault;

import static org.junit.jupiter.api.Assertions.*;

import java.time.LocalDateTime;
import java.util.List;
import javax.persistence.EntityManager;
import org.hibernate.Session;
import org.hibernate.stat.Statistics;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

/**
 * 第三层判定 #3：N+1 问题与 @EntityGraph 修复。
 *
 * 对照 Python: crud.py 的 selectinload(PipelineFault.pipeline) 防 N+1。
 *
 * 什么是 N+1？
 *   查 3 条故障 → 1 条 SELECT（拿故障列表）
 *   访问每条故障的 pipeline.getName() → 触发 3 条额外 SELECT（懒加载）
 *   总共 1 + 3 = 4 条 SQL。故障越多越慢。
 *
 * @EntityGraph 修复后：
 *   查 3 条故障 → 1 条 SELECT ... LEFT JOIN pipelines（一次拿全）
 *   访问 pipeline.getName() → 不触发额外 SQL（已在内存）
 *   总共 1 条 SQL。
 *
 * 新 API：
 *   Hibernate Statistics —— 统计 SQL 执行次数。
 *     entityManager.unwrap(Session.class).getSessionFactory().getStatistics()
 *     stats.getPrepareStatementCount() → 本次统计周期内执行了多少条 SQL
 *
 *   对照 Python: 没有直接等价物（SQLAlchemy 用 echo=True 看日志，或 event.listen 计数）。
 *   Java 这边有内建统计 API，断言更精确。
 */
@DataJpaTest
class NplusOneTest {

    @Autowired
    private PipelineRepository pipelineRepo;

    @Autowired
    private PipelineFaultRepository faultRepo;

    @Autowired
    private TestEntityManager em;

    @Autowired
    private EntityManager entityManager;

    private Statistics stats;

    @BeforeEach
    void setUp() {
        // 准备数据：1 条流水线 + 3 条故障
        PipelineEntity p = new PipelineEntity("LINE-N", "N+1测试线", null);
        for (int i = 1; i <= 3; i++) {
            p.addFault(new PipelineFaultEntity(
                    "工位" + i, LocalDateTime.now(), "故障现象" + i));
        }
        pipelineRepo.save(p);
        em.flush();
        em.clear();  // 清缓存，确保后续查询走数据库

        // 开启 Hibernate 统计
        Session session = entityManager.unwrap(Session.class);
        stats = session.getSessionFactory().getStatistics();
        stats.setStatisticsEnabled(true);
    }

    @Test
    @DisplayName("N+1 复现：findAll + 逐条访问 pipeline → 1+3=4 条 SQL")
    void nPlusOneProblem() {
        stats.clear();

        // 查全部故障（LAZY，不 JOIN pipeline）
        List<PipelineFaultEntity> faults = faultRepo.findAll();
        assertEquals(3, faults.size());

        // 逐条访问 pipeline.getName() → 触发懒加载
        for (PipelineFaultEntity f : faults) {
            assertNotNull(f.getPipeline().getName());
        }

        long sqlCount = stats.getPrepareStatementCount();
        // 1（查故障列表）+ 3（每条故障懒加载 pipeline）= 4
        // 注意：3 条故障指向同一条 pipeline，Hibernate 一级缓存会去重，
        // 实际可能是 1+1=2（第二条起命中缓存）。但不同 pipeline 时就是真 N+1。
        // 这里断言 >= 2 即可证明有额外查询。
        assertTrue(sqlCount >= 2,
                "LAZY 加载应产生额外 SQL，实际: " + sqlCount);
        System.out.println("【N+1 复现】SQL 条数 = " + sqlCount);
    }

    @Test
    @DisplayName("@EntityGraph 修复：findAllBy → 1 条 SQL（JOIN 预加载）")
    void entityGraphFix() {
        stats.clear();

        // 用 @EntityGraph 方法查全部（JOIN FETCH pipeline）
        List<PipelineFaultEntity> faults = faultRepo.findAllBy();
        assertEquals(3, faults.size());

        // 逐条访问 pipeline.getName() → 不触发额外 SQL（已预加载）
        for (PipelineFaultEntity f : faults) {
            assertNotNull(f.getPipeline().getName());
        }

        long sqlCount = stats.getPrepareStatementCount();
        // 只有 1 条 SELECT ... LEFT JOIN
        assertEquals(1, sqlCount,
                "@EntityGraph 应只产生 1 条 SQL，实际: " + sqlCount);
        System.out.println("【@EntityGraph 修复】SQL 条数 = " + sqlCount);
    }
}
