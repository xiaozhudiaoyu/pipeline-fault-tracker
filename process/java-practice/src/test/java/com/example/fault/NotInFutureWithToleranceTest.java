package com.example.fault;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.LocalDateTime;
import java.util.Set;
import javax.validation.ConstraintViolation;
import javax.validation.Validation;
import javax.validation.Validator;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 自定义约束的单元测试 —— 第四层「掌握判定 #2」。
 * 边界：正好 +60s 通过、+61s 拒绝、过去时间通过、null 通过。
 *
 * 对照 Python 侧测试：test_schemas.py 里 occurred_at 的边界用例。
 *
 * 新 API：
 *   LocalDateTime.now()          ≈ datetime.now()
 *   .plusSeconds(60)             ≈ + timedelta(seconds=60)
 *   .minusHours(1)               ≈ - timedelta(hours=1)
 *   .withNano(0)                 截断纳秒（让 toString 输出干净的 ISO 串）
 */
class NotInFutureWithToleranceTest {

    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

    // 辅助：构造一个只有 occurredAt 不同的合法 DTO（其余字段给合法值）
    private FaultCreateFullDto dtoWithTime(LocalDateTime occurredAt) {
        return new FaultCreateFullDto("ok", "ok", null, 1, occurredAt);
    }

    @Test
    @DisplayName("边界：正好 now+60s → 通过（不晚于容忍上限）")
    void exactlyAtTolerancePasses() {
        LocalDateTime boundary = LocalDateTime.now().plusSeconds(60);
        Set<ConstraintViolation<FaultCreateFullDto>> v = validator.validate(dtoWithTime(boundary));
        assertTrue(v.isEmpty(), "正好 +60s 应在容忍范围内");
    }

    @Test
    @DisplayName("边界：now+61s → 拒绝（超出容忍 1 秒）")
    void beyondToleranceFails() {
        LocalDateTime beyond = LocalDateTime.now().plusSeconds(61);
        Set<ConstraintViolation<FaultCreateFullDto>> v = validator.validate(dtoWithTime(beyond));
        assertFalse(v.isEmpty(), "+61s 应被拦截");
    }

    @Test
    @DisplayName("过去时间 → 通过")
    void pastTimePasses() {
        LocalDateTime past = LocalDateTime.now().minusHours(1);
        Set<ConstraintViolation<FaultCreateFullDto>> v = validator.validate(dtoWithTime(past));
        assertTrue(v.isEmpty());
    }

    @Test
    @DisplayName("null → 通过（可选字段，约束跳过）")
    void nullPasses() {
        Set<ConstraintViolation<FaultCreateFullDto>> v = validator.validate(dtoWithTime(null));
        assertTrue(v.isEmpty());
    }
}
