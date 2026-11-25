package com.example.fault;

import javax.validation.Constraint;
import javax.validation.Payload;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 自定义校验注解 —— 对照 schemas.py 的 @field_validator("occurred_at") occurred_at_not_in_future。
 *
 * 新语法：@interface（注解类型声明）
 *   普通类用 class，枚举用 enum，【注解】用 @interface。
 *   它定义的不是"行为"，而是"一种可以贴在字段上的标签的规格"。
 *
 * 三个必备元素（Bean Validation 规范强制）：
 *   message()  —— 校验失败时的默认错误消息
 *   groups()   —— 分组校验（高级用法，这里留空）
 *   payload()  —— 负载元数据（高级用法，这里留空）
 *
 * 自定义参数：
 *   seconds()  —— 容忍秒数，默认 60（对照 Python timedelta(seconds=60)）
 *
 * @Constraint(validatedBy=...) —— 告诉 Bean Validation："贴了这个注解的字段，
 *   由 NotInFutureWithToleranceValidator 来执行校验逻辑。"
 * @Target(FIELD) —— 只能贴在字段上
 * @Retention(RUNTIME) —— 运行时保留（Validator 要在运行时读取它）
 */
@Target({ElementType.FIELD})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = NotInFutureWithToleranceValidator.class)
public @interface NotInFutureWithTolerance {

    String message() default "故障发生时间不得晚于当前时间";

    Class<?>[] groups() default {};

    Class<? extends Payload>[] payload() default {};

    int seconds() default 60;
}
