package com.example.fault;

import static org.junit.jupiter.api.Assertions.*;

import java.time.LocalDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

/**
 * 第三层判定 #1（后半）：删用户 → FK 置空，故障不删。
 *
 * 对照 Python: ForeignKey("users.id", ondelete="SET NULL")
 * 业务规则：故障不可删除（需求二.5），用户被删只清关联。
 *
 * 重要差异（Hibernate 5.6 的坑）：
 *   Python: ondelete="SET NULL" 一行声明，数据库自动干。
 *   Java 5.6: 没有声明式 SET NULL，必须应用层手动清 FK 再删用户。
 *   这就是真实 Java 项目的常见做法（Service 层写“删用户前清关联”逻辑）。
 *   3c Flyway 会补数据库级 DDL 约束作为双保险。
 *
 * 新 API：
 *   TestEntityManager.clear()  ≈ session.expunge_all()：清一级缓存。
 *   TestEntityManager.flush()  ≈ session.flush()：刷 SQL 到数据库。
 */
@DataJpaTest
class SetNullOnDeleteTest {

    @Autowired
    private UserRepository userRepo;

    @Autowired
    private PipelineRepository pipelineRepo;

    @Autowired
    private PipelineFaultRepository faultRepo;

    @Autowired
    private TestEntityManager em;

    @Test
    @DisplayName("删用户 → 故障的 createdBy/assignee 置 NULL，故障本身不删")
    void deleteUserSetsFkNull() {
        // 准备：用户 + 流水线 + 故障（创建人和负责人都是该用户）
        UserEntity user = new UserEntity("zhangsan", "张三", FaultRole.HANDLER);
        userRepo.save(user);

        PipelineEntity pipeline = new PipelineEntity("LINE-X", "测试线", null);
        pipelineRepo.save(pipeline);

        PipelineFaultEntity fault = new PipelineFaultEntity(
                "工位1", LocalDateTime.now(), "测试故障");
        fault.setPipeline(pipeline);
        fault.setCreatedBy(user);
        fault.setAssignee(user);
        faultRepo.save(fault);
        em.flush();

        Long faultId = fault.getId();
        Long userId = user.getId();

        // ★ 应用层 SET NULL：删用户前先清 FK 引用 ★
        // Hibernate 5.6 没有数据库级 ON DELETE SET NULL，必须手动干。
        // 对照 Python: 不需要这一步，数据库自动干。
        fault.setCreatedBy(null);
        fault.setAssignee(null);
        faultRepo.save(fault);
        em.flush();

        // 现在删用户（已无引用，不会报 FK 约束冲突）
        userRepo.deleteById(userId);
        em.flush();
        em.clear();  // 清一级缓存，迫使重新查库

        // 断言：故障仍在，FK 已空
        PipelineFaultEntity reloaded = faultRepo.findById(faultId).orElse(null);
        assertNotNull(reloaded, "故障不应被删除");
        assertNull(reloaded.getCreatedBy(), "createdBy 应被置 NULL");
        assertNull(reloaded.getAssignee(), "assignee 应被置 NULL");
        assertEquals("测试故障", reloaded.getSymptom(), "故障内容不变");
    }

    @Test
    @DisplayName("删用户不影响其他用户的故障")
    void deleteUserOnlyAffectsOwnFaults() {
        UserEntity userA = new UserEntity("a", "用户A", FaultRole.USER);
        UserEntity userB = new UserEntity("b", "用户B", FaultRole.HANDLER);
        userRepo.save(userA);
        userRepo.save(userB);

        PipelineEntity p = new PipelineEntity("LINE-Y", "线Y", null);
        pipelineRepo.save(p);

        PipelineFaultEntity f1 = new PipelineFaultEntity("工位1", LocalDateTime.now(), "故障1");
        f1.setPipeline(p);
        f1.setCreatedBy(userA);
        f1.setAssignee(userB);

        PipelineFaultEntity f2 = new PipelineFaultEntity("工位2", LocalDateTime.now(), "故障2");
        f2.setPipeline(p);
        f2.setCreatedBy(userB);
        f2.setAssignee(userB);

        faultRepo.save(f1);
        faultRepo.save(f2);
        em.flush();

        // 应用层 SET NULL：只清 f1 的 createdBy（指向 userA 的那个）
        f1.setCreatedBy(null);
        faultRepo.save(f1);
        em.flush();

        // 删 userA
        userRepo.deleteById(userA.getId());
        em.flush();
        em.clear();

        // f1: createdBy 置空，assignee(userB) 不受影响
        PipelineFaultEntity r1 = faultRepo.findById(f1.getId()).orElse(null);
        assertNotNull(r1);
        assertNull(r1.getCreatedBy());
        assertNotNull(r1.getAssignee(), "userB 没被删，assignee 应保留");
        assertEquals("用户B", r1.getAssignee().getDisplayName());

        // f2: 两个 FK 都指向 userB，完全不受影响
        PipelineFaultEntity r2 = faultRepo.findById(f2.getId()).orElse(null);
        assertNotNull(r2);
        assertNotNull(r2.getCreatedBy());
        assertNotNull(r2.getAssignee());
    }
}
