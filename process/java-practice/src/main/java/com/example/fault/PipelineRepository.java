package com.example.fault;

import org.springframework.data.jpa.repository.JpaRepository;

/**
 * 流水线 Repository —— 对照 crud.py 里对 Pipeline 的增删改查。
 *
 * 新概念：JpaRepository<T, ID>
 *   你只写一个【接口】，不写实现类。Spring Data 在运行时自动生成实现。
 *   继承即获得：save / findById / findAll / deleteById / count / existsById ...
 *
 *   对照 Python：crud.py 里每个操作都要手写 session.execute(select(...))；
 *   Java 这边零行实现代码，框架全帮你干了。
 *
 *   泛型参数：
 *     T  = 实体类型（PipelineEntity）
 *     ID = 主键类型（Long）
 *
 *   如果需要自定义查询，加方法签名即可（Spring Data 按方法名生成 SQL）：
 *     Optional<PipelineEntity> findByCode(String code);
 *     → SELECT * FROM pipelines WHERE code = ?
 *   本步暂不加，后面按需补。
 */
public interface PipelineRepository extends JpaRepository<PipelineEntity, Long> {
}
