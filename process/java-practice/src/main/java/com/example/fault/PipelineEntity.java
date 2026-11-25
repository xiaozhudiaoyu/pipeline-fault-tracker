package com.example.fault;

import javax.persistence.*;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 流水线实体 —— 对照 models.py 的 Pipeline(Base)。
 *
 * 新概念：JPA 注解（javax.persistence，Boot 2.7 命名空间）
 *
 *   @Entity          ≈ class Pipeline(Base):  —— 告诉 Hibernate "这个类映射一张表"
 *   @Table(name=)    ≈ __tablename__ = "pipelines"
 *   @Id              ≈ primary_key=True
 *   @GeneratedValue  ≈ autoincrement=True（IDENTITY = 数据库自增）
 *   @Column          ≈ mapped_column(String(50), unique=True, nullable=False)
 *   @OneToMany       ≈ relationship(back_populates="pipeline", cascade="all, delete-orphan")
 *
 * 对照 Python 的关键差异：
 *   · SQLAlchemy 用 Mapped[list["PipelineFault"]] 类型标注声明关系；
 *     JPA 用 @OneToMany + 泛型 List<PipelineFaultEntity> 字段。
 *   · cascade="all, delete-orphan" 拆成两个属性：
 *     cascade = CascadeType.ALL（删/改/持久化都传播）
 *     orphanRemoval = true（从集合移除 = 删除该行）
 *   · mappedBy = "pipeline"：告诉 Hibernate "对方那个字段才是关系的拥有者"
 *     （≈ back_populates 的镜像声明，但 JPA 必须显式指定哪端管 FK）
 *
 * 注意：JPA 实体必须有【无参构造器】（Hibernate 反射创建实例用）。
 *   这和 Jackson 的 @JsonCreator 不同——Hibernate 不走 JSON，走反射。
 *   所以这里给一个 protected 无参构造 + 一个业务用的全参构造。
 */
@Entity
@Table(name = "pipelines")
public class PipelineEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "code", length = 50, unique = true, nullable = false)
    private String code;

    @Column(name = "name", length = 100, nullable = false)
    private String name;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    // ---- 一对多的"一"端 ----
    // 对照: faults: Mapped[list["PipelineFault"]] = relationship(
    //           back_populates="pipeline", cascade="all, delete-orphan")
    @OneToMany(mappedBy = "pipeline", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<PipelineFaultEntity> faults = new ArrayList<>();

    // Hibernate 反射用的无参构造（不能删！）
    protected PipelineEntity() {}

    // 业务构造器
    public PipelineEntity(String code, String name, String description) {
        this.code = code;
        this.name = name;
        this.description = description;
        this.createdAt = LocalDateTime.now();
    }

    // ---- getter ----
    public Long getId() { return id; }
    public String getCode() { return code; }
    public String getName() { return name; }
    public String getDescription() { return description; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public List<PipelineFaultEntity> getFaults() { return faults; }

    // 便捷方法：往集合里加故障（同时维护双向关系）
    public void addFault(PipelineFaultEntity fault) {
        faults.add(fault);
        fault.setPipeline(this);
    }
}
