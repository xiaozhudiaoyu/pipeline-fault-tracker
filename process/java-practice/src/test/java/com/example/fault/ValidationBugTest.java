package com.example.fault;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Set;
import javax.validation.ConstraintViolation;
import javax.validation.Validation;
import javax.validation.Validator;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 「特征测试」(characterization test)：证明坑的存在。
 * 全绿 = 坑确实存在（"空格/null 通过校验"是预期行为，因为 DTO 写法有缺陷）。
 *
 * 新 API 逐个拆（对照 Python 的 pydantic 校验）：
 *   Validator validator = Validation.buildDefaultValidatorFactory().getValidator();
 *     ↔ Python: 直接 FaultCreate.model_validate(data) 就报错
 *     Java 得手动建一个 Validator 工厂再取 validator 实例（Boot 里这步由框架自动做）。
 *
 *   Set<ConstraintViolation<T>> violations = validator.validate(dto);
 *     ↔ Python: pydantic 抛 ValidationError（异常流）；Java 不抛，返回违规集合（结果流）。
 *     violations.size() == 0 → 校验通过；> 0 → 有违规项。
 */
class ValidationBugTest {

    // 建 Validator（每个测试类一个就够，线程安全可复用）。
    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

    @Test
    @DisplayName("BUG #1：纯空格 \"   \" 通过 @Size(min=1)（空格穿过 min_length）")
    void whitespacePassesSize() {
        FaultCreateDto dto = new FaultCreateDto("   ", "valid");
        Set<ConstraintViolation<FaultCreateDto>> violations = validator.validate(dto);
        // 坑：title 是 "   "，长度 3 >= 1，@Size 不 trim → 0 个违规
        assertEquals(0, violations.size(),
                "空格竟然通过了 min=1 校验——这就是你项目曾经的 bug");
    }

    @Test
    @DisplayName("BUG #2：null 通过 @Size（显式 null 被跳过，不触发约束）")
    void nullBypassesSize() {
        FaultCreateDto dto = new FaultCreateDto(null, "valid");
        Set<ConstraintViolation<FaultCreateDto>> violations = validator.validate(dto);
        // 坑：Bean Validation 规范规定 null 不触发 @Size → 0 个违规
        assertEquals(0, violations.size(),
                "null 竟然通过了校验——Bean Validation 对 null 默认放行");
    }
}
