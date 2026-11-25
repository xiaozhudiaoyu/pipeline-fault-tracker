package com.example.fault;

import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

/**
 * 故障 Repository —— 对照 crud.py 里对 PipelineFault 的操作。
 *
 * 自定义查询示例（Spring Data 方法名派生）：
 *   findByPipelineId(Long pipelineId)
 *   → SELECT * FROM pipeline_faults WHERE pipeline_id = ?
 *
 *   对照 Python: select(PipelineFault).where(PipelineFault.pipeline_id == pid)
 *   Java 不用写 SQL，方法名就是查询声明。
 */
public interface PipelineFaultRepository extends JpaRepository<PipelineFaultEntity, Long> {

    // 按流水线 ID 查其下所有故障（方法名 → SQL 自动生成）
    List<PipelineFaultEntity> findByPipelineId(Long pipelineId);

    // ---- 防 N+1：@EntityGraph 预加载 ----
    // 对照 Python: select(PipelineFault).options(selectinload(PipelineFault.pipeline))
    //
    // @EntityGraph(attributePaths={"pipeline"}) 告诉 Hibernate：
    //   "查故障时顺便把 pipeline 一起 JOIN 进来，别等访问时再懒加载。"
    //   生成的 SQL: SELECT f.*, p.* FROM pipeline_faults f LEFT JOIN pipelines p ON ...
    //   一条 SQL 搞定，而不是 1 + N 条。
    //
    // findAllBy() 是 Spring Data 的“查全部”变体（等价 findAll，但能贴 @EntityGraph）。
    @EntityGraph(attributePaths = {"pipeline"})
    List<PipelineFaultEntity> findAllBy();
}
