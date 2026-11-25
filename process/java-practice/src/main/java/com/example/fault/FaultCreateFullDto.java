package com.example.fault;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.NotNull;
import javax.validation.constraints.Pattern;
import javax.validation.constraints.Size;
import java.time.LocalDateTime;

/**
 * 完整版登记 DTO —— 覆盖第四层全部 5 个 HTTP 校验判定。
 *
 * 对照 schemas.py 的 FaultCreate：
 *   title       → @NotBlank（空格/null 都拦）
 *   description → @NotBlank
 *   location    → @Pattern("^\\S.*$")（首字符不能是空格；null 时跳过 = 可选字段）
 *   pipelineId  → @NotNull（必填，缺了或传 null 都拦）
 *
 * 多余字段（如 "status":"done"）由全局 Jackson 配置拦截（application.properties）。
 *
 * 新注解：
 *   @Pattern(regexp=...) —— 正则校验，≈ Pydantic Field(pattern=r"^\S.*$")
 *   @NotNull —— 只拦 null，不管空串/空格（和 @NotBlank 的区别！）
 *   Integer（大写 I）—— 包装类型，能为 null；int（小写）是基本类型，不能为 null
 */
public class FaultCreateFullDto {

    @NotBlank
    @Size(max = 200)
    private String title;

    @NotBlank
    @Size(max = 500)
    private String description;

    // 可选字段：null 时 @Pattern 跳过（不违规）；有值时首字符必须非空格
    @Pattern(regexp = "^\\S.*$", message = "不能以空格开头")
    private String location;

    // 必填字段：缺了（JSON 里没这个 key）或显式 null → 违规
    @NotNull(message = "pipeline_id 不能为空")
    private Integer pipelineId;

    // 可选字段：null 时跳过；有值时不得晚于当前时间 + 60s
    @NotInFutureWithTolerance(seconds = 60)
    private LocalDateTime occurredAt;

    @JsonCreator
    public FaultCreateFullDto(
            @JsonProperty("title") String title,
            @JsonProperty("description") String description,
            @JsonProperty("location") String location,
            @JsonProperty("pipelineId") Integer pipelineId,
            @JsonProperty("occurredAt") LocalDateTime occurredAt) {
        this.title = title;
        this.description = description;
        this.location = location;
        this.pipelineId = pipelineId;
        this.occurredAt = occurredAt;
    }

    public String getTitle() { return title; }
    public String getDescription() { return description; }
    public String getLocation() { return location; }
    public Integer getPipelineId() { return pipelineId; }
    public LocalDateTime getOccurredAt() { return occurredAt; }
}
