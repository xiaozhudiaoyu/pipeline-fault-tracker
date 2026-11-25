package com.example.fault;

import javax.persistence.*;
import java.time.LocalDateTime;

/**
 * 故障记录实体 —— 对照 models.py 的 PipelineFault(Base)。
 * 本步（3a）只含核心字段 + Pipeline FK；User FK 在 3b 补。
 *
 * 新概念：
 *   @ManyToOne       ≈ relationship("Pipeline", back_populates="faults")
 *                      多端持有 FK 列，是关系的"拥有者"。
 *   @JoinColumn      ≈ ForeignKey("pipelines.id", ondelete="CASCADE")
 *                      name = 库里的列名；nullable = 是否允许 NULL。
 *   @Enumerated      ≈ Enum(FaultStatus)：把 Java 枚举存成字符串。
 *                      EnumType.STRING = 存 "pending"（推荐）
 *                      EnumType.ORDINAL = 存 0/1/2（不推荐，加枚举值会错位）
 *
 * 对照 Python 的关键差异：
 *   · SQLAlchemy 的 FK 列（pipeline_id）和关系（pipeline）是【两个独立属性】；
 *     JPA 里 @ManyToOne + @JoinColumn 合成一个字段，Hibernate 自动管理 FK 列。
 *     你不需要手动写 pipelineId 字段——Hibernate 从 pipeline.getId() 推导。
 *   · 但本项目 Python 侧同时暴露 pipeline_id 和 pipeline（BUG-C 的根因），
 *     Java 侧如果也暴露两个入口就会重演同样的坑——3d 会专门体会。
 *
 * 无参构造器：同 PipelineEntity，Hibernate 反射必需。
 */
@Entity
@Table(name = "pipeline_faults")
public class PipelineFaultEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // ---- 外键：多端 ----
    // 对照: pipeline_id = mapped_column(ForeignKey("pipelines.id", ondelete="CASCADE"))
    //       pipeline = relationship(back_populates="faults")
    // JPA 把这两行合成一个字段：
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "pipeline_id", nullable = false)
    private PipelineEntity pipeline;

    @Column(name = "location", length = 200, nullable = false)
    private String location;

    @Column(name = "occurred_at", nullable = false)
    private LocalDateTime occurredAt;

    @Column(name = "symptom", columnDefinition = "TEXT", nullable = false)
    private String symptom;

    // 枚举存字符串（对照 Enum(FaultStatus) 在 SQLite 上渲染 VARCHAR）
    @Enumerated(EnumType.STRING)
    @Column(name = "status", length = 30, nullable = false)
    private FaultStatus status = FaultStatus.PENDING;

    @Enumerated(EnumType.STRING)
    @Column(name = "priority", length = 10, nullable = false)
    private FaultPriority priority = FaultPriority.NORMAL;

    @Column(name = "handling_note", columnDefinition = "TEXT")
    private String handlingNote;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @Column(name = "closed_at")
    private LocalDateTime closedAt;

    // ---- 创建人 / 负责人 FK（第三阶段，3b 补）----
    // 对照 Python: ForeignKey("users.id", ondelete="SET NULL")
    // 删用户时不删故障，只把 FK 置空。
    //
    // 重要差异：Hibernate 5.6 没有声明式 ON DELETE SET NULL！
    //   Python SQLAlchemy: ForeignKey(ondelete="SET NULL") 一行搞定（标准 API）。
    //   Java 标准 JPA: @JoinColumn 没有 onDelete 属性。
    //   Hibernate 5.6: @OnDelete 只支持 CASCADE，不支持 SET_NULL（6.2+ 才加）。
    //   解法：应用层在删用户前手动清 FK（见 SetNullOnDeleteTest），
    //         或通过 Flyway DDL 加数据库级约束（3c 补）。
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "created_by_id")
    private UserEntity createdBy;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "assignee_id")
    private UserEntity assignee;

    // Hibernate 反射用
    protected PipelineFaultEntity() {}

    // 业务构造器
    public PipelineFaultEntity(String location, LocalDateTime occurredAt, String symptom) {
        this.location = location;
        this.occurredAt = occurredAt;
        this.symptom = symptom;
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    // ---- getter / setter ----
    public Long getId() { return id; }
    public PipelineEntity getPipeline() { return pipeline; }
    public void setPipeline(PipelineEntity pipeline) { this.pipeline = pipeline; }
    public String getLocation() { return location; }
    public LocalDateTime getOccurredAt() { return occurredAt; }
    public String getSymptom() { return symptom; }
    public FaultStatus getStatus() { return status; }
    public void setStatus(FaultStatus status) { this.status = status; }
    public FaultPriority getPriority() { return priority; }
    public void setPriority(FaultPriority priority) { this.priority = priority; }
    public String getHandlingNote() { return handlingNote; }
    public void setHandlingNote(String handlingNote) { this.handlingNote = handlingNote; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public LocalDateTime getClosedAt() { return closedAt; }
    public void setClosedAt(LocalDateTime closedAt) { this.closedAt = closedAt; }
    public UserEntity getCreatedBy() { return createdBy; }
    public void setCreatedBy(UserEntity createdBy) { this.createdBy = createdBy; }
    public UserEntity getAssignee() { return assignee; }
    public void setAssignee(UserEntity assignee) { this.assignee = assignee; }
}
