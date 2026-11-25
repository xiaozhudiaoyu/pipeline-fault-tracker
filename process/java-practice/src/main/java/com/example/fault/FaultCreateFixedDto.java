package com.example.fault;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;

import javax.validation.constraints.Size;
import javax.validation.constraints.NotBlank;

/**
 * 修复后的 DTO —— 用 @NotBlank 拦截空格、null。
 *
 * 对应你 Python 项目 schemas.py 的 FaultCreate（同样只写 min_length=1）。
 * 两个已知坑（Bean Validation 规范 + @Size 的默认行为）：
 *   1. "   "（纯空格）长度 3 >= 1，@Size(min=1) 不 trim → 放行（空格穿过）
 *   2. null 被 @Size 跳过（规范：null 不触发任何约束，除 @NotNull）→ 放行（显式 null 绕过）
 *
 * 新语法：注解（annotation）—— @NotBlank 放在字段上方，类似 Python 装饰器但语法不同：
 *   Python: description: str = Field(min_length=1, max_length=500)
 *   Java:   @NotBlank @Size(min = 1, max = 500) private String description;
 * 注解 = 元数据标签，本身不执行逻辑，由框架（Hibernate Validator）在运行时读取并执行校验。
 */

public class FaultCreateFixedDto {

    // @NotBlank 注解：拦截 null、空格、空字符串。
    @NotBlank
    @Size(min = 1, max = 200)
    private String title;

    @NotBlank
    @Size(min = 1, max = 500)
    private String description;

    // @JsonCreator：告诉 Jackson「用这个构造器来反序列化 JSON」
    // @JsonProperty("title")：告诉 Jackson「JSON 里的 title 键对应这个参数」
    // 对照 Python：Pydantic 靠字段名自动匹配，不需要这些注解。
    @JsonCreator
    public FaultCreateFixedDto(
            @JsonProperty("title") String title,
            @JsonProperty("description") String description) {
        this.title = title;
        this.description = description;
    }

    public String getTitle() { return title; }
    public String getDescription() { return description; }
}