package com.example.fault;

import javax.validation.ConstraintValidator;
import javax.validation.ConstraintValidatorContext;
import java.time.LocalDateTime;

/**
 * 自定义约束的执行逻辑 —— 对照 schemas.py 第 115 行：
 *   if wall > timeutil.business_now() + timedelta(seconds=60):
 *       raise ValueError("故障发生时间不得晚于当前时间")
 *
 * 新语法：implements ConstraintValidator<A, T>
 *   A = 注解类型（NotInFutureWithTolerance）
 *   T = 被校验的字段类型（LocalDateTime）
 *   接口强制两个方法：
 *     initialize(A) —— 读取注解参数（只调一次）
 *     isValid(T, context) —— 每次校验调一次，返回 true=通过 / false=违规
 *
 * 对照 Python：@field_validator 是一个函数，直接写 if/raise；
 * Java 拆成"注解定义 + 校验器类"两个文件（声明与实现分离）。
 *
 * LocalDateTime（java.time）≈ Python datetime（naive，无时区）。
 *   .isAfter(other)  ≈ Python 的 >
 *   .plusSeconds(n)  ≈ Python 的 + timedelta(seconds=n)
 *   .now()           ≈ Python 的 datetime.now()
 */
public class NotInFutureWithToleranceValidator
        implements ConstraintValidator<NotInFutureWithTolerance, LocalDateTime> {

    private int seconds;

    @Override
    public void initialize(NotInFutureWithTolerance annotation) {
        // 从注解上读参数：@NotInFutureWithTolerance(seconds=60) → this.seconds = 60
        this.seconds = annotation.seconds();
    }

    @Override
    public boolean isValid(LocalDateTime value, ConstraintValidatorContext context) {
        // null 放行（可选字段，和 @Size/@Pattern 同一规范）
        if (value == null) {
            return true;
        }
        // 核心判定：value > now + tolerance → 违规（返回 false）
        // 对照 Python: if wall > business_now() + timedelta(seconds=60): raise
        return !value.isAfter(LocalDateTime.now().plusSeconds(seconds));
    }
}
