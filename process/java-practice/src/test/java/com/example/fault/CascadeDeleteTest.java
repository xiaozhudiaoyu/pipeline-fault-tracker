package com.example.fault;

import static org.junit.jupiter.api.Assertions.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;

/**
 * 第三层判定 #1（前半）：级联删除。
 *
 * 新概念：@DataJpaTest
 *   Spring Boot 的"切片测试"——只加载 JPA 相关 Bean（Entity + Repository），
 *   不加载 Controller / Service / Web 层。启动快、隔离好。
 *   默认用内嵌 H2，每个测试方法包在事务里、结束自动回滚。
 *
 *   对照 Python：conftest.py 里的 db_session fixture（内存 SQLite + 回滚）。
 *   区别：Python 要手动建 engine / create_all / yield session / rollback；
 *   Java 一个注解全搞定。
 *
 * 验证目标：
 *   删 Pipeline → 其下 PipelineFault 级联消失（orphanRemoval + CascadeType.ALL）
 *   对照 Python: cascade="all, delete-orphan" 的效果。
 */
@DataJpaTest
class CascadeDeleteTest {

    @Autowired
    private PipelineRepository pipelineRepo;

    @Autowired
    private PipelineFaultRepository faultRepo;

    @Test
    @DisplayName("基本 CRUD：save + findById 能存取")
    void saveAndFind() {
        PipelineEntity p = new PipelineEntity("LINE-A", "总装线A", null);
        pipelineRepo.save(p);

        assertNotNull(p.getId(), "save 后应回填自增 ID");

        Optional<PipelineEntity> found = pipelineRepo.findById(p.getId());
        assertTrue(found.isPresent());
        assertEquals("LINE-A", found.get().getCode());
    }

    @Test
    @DisplayName("级联持久化：pipeline.addFault + save → 故障自动入库")
    void cascadePersist() {
        PipelineEntity p = new PipelineEntity("LINE-B", "焊装线B", null);
        PipelineFaultEntity f = new PipelineFaultEntity(
                "3号工位", LocalDateTime.now().minusHours(1), "传送带卡顿");
        p.addFault(f);

        pipelineRepo.save(p);  // cascade=ALL → f 也跟着入库

        assertNotNull(f.getId(), "级联持久化后故障应有 ID");
        assertEquals(1, faultRepo.count());
    }

    @Test
    @DisplayName("级联删除：删 Pipeline → 其下故障全部消失")
    void cascadeDelete() {
        // 准备：1 条流水线 + 2 条故障
        PipelineEntity p = new PipelineEntity("LINE-C", "涂装线C", null);
        p.addFault(new PipelineFaultEntity("工位1", LocalDateTime.now(), "喷漆不均"));
        p.addFault(new PipelineFaultEntity("工位2", LocalDateTime.now(), "色差超标"));
        pipelineRepo.save(p);

        Long pipelineId = p.getId();
        assertEquals(2, faultRepo.findByPipelineId(pipelineId).size());

        // 执行：删流水线
        pipelineRepo.deleteById(pipelineId);
        pipelineRepo.flush();  // 强制刷 SQL（否则可能延迟到事务提交才执行）

        // 断言：故障级联消失
        List<PipelineFaultEntity> remaining = faultRepo.findByPipelineId(pipelineId);
        assertTrue(remaining.isEmpty(), "删流水线后其下故障应全部级联删除");
        assertEquals(0, faultRepo.count());
    }

    @Test
    @DisplayName("orphanRemoval：从集合移除故障 → 该行被删除")
    void orphanRemoval() {
        PipelineEntity p = new PipelineEntity("LINE-D", "检测线D", null);
        PipelineFaultEntity f1 = new PipelineFaultEntity("工位1", LocalDateTime.now(), "问题A");
        PipelineFaultEntity f2 = new PipelineFaultEntity("工位2", LocalDateTime.now(), "问题B");
        p.addFault(f1);
        p.addFault(f2);
        pipelineRepo.save(p);
        pipelineRepo.flush();

        // 从集合移除 f1（不是 delete，只是 remove）
        p.getFaults().remove(f1);
        pipelineRepo.save(p);
        pipelineRepo.flush();

        // orphanRemoval=true → 移除 = 删除
        assertEquals(1, faultRepo.count(), "移除一条后应只剩 1 条");
        assertEquals("问题B", faultRepo.findAll().get(0).getSymptom());
    }
}
