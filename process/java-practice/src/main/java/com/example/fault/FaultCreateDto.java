package com.example.fault;

import javax.validation.constraints.Size;

/**
 * 故意「有坑」的 DTO —— 只用 @Size，不 trim、不拦 null。
 *
 * 对应你 Python 项目最初 schemas.py 的 FaultCreate（同样只写 min_length=1）。
 * 两个已知坑（Bean Validation 规范 + @Size 的默认行为）：
 *   1. "   "（纯空格）长度 3 >= 1，@Size(min=1) 不 trim → 放行（空格穿过）
 *   2. null 被 @Size 跳过（规范：null 不触发任何约束，除 @NotNull）→ 放行（显式 null 绕过）
 *
 * 新语法：注解（annotation）—— @Size 放在字段上方，类似 Python 装饰器但语法不同：
 *   Python: description: str = Field(min_length=1, max_length=500)
 *   Java:   @Size(min = 1, max = 500) private String description;
 * 注解 = 元数据标签，本身不执行逻辑，由框架（Hibernate Validator）在运行时读取并执行校验。
 */
public class FaultCreateDto {

    // @Size 注解：参数用 key = value 形式（不是 Python 的位置参数）。
    @Size(min = 1, max = 200)
    private String title;

    @Size(min = 1, max = 500)
    private String description;

    public FaultCreateDto(String title, String description) {
        this.title = title;
        this.description = description;
    }

    public String getTitle() { return title; }
    public String getDescription() { return description; }
}
