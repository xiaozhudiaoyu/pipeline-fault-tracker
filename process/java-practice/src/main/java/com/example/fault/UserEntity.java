package com.example.fault;

import javax.persistence.*;

/**
 * 用户实体 —— 对照 models.py 的 User(Base)。
 * 练习简化版：只保留 id / username / displayName / role / isActive。
 * 省略 password_hash / token_version / created_at（认证是第五层的事）。
 *
 * 新概念：
 *   @Enumerated(EnumType.STRING) 复用第一层写的 FaultRole 枚举。
 *   对照 Python: role: Mapped[FaultRole] = mapped_column(Enum(FaultRole))
 *
 * 注意：User 被 PipelineFault 的 createdBy / assignee 两个 FK 引用，
 * 删除用户时的行为是 SET NULL（不删故障，只清关联）——见 PipelineFaultEntity。
 */
@Entity
@Table(name = "users")
public class UserEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "username", length = 50, unique = true, nullable = false)
    private String username;

    @Column(name = "display_name", length = 100, nullable = false)
    private String displayName;

    @Enumerated(EnumType.STRING)
    @Column(name = "role", length = 10, nullable = false)
    private FaultRole role;

    @Column(name = "is_active", nullable = false)
    private Boolean isActive = true;

    protected UserEntity() {}

    public UserEntity(String username, String displayName, FaultRole role) {
        this.username = username;
        this.displayName = displayName;
        this.role = role;
    }

    public Long getId() { return id; }
    public String getUsername() { return username; }
    public String getDisplayName() { return displayName; }
    public FaultRole getRole() { return role; }
    public Boolean getIsActive() { return isActive; }
    public void setIsActive(Boolean isActive) { this.isActive = isActive; }
}
