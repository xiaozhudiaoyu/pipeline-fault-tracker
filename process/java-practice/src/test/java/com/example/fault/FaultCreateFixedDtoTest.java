package com.example.fault;

import static org.junit.jupiter.api.Assertions.assertFalse;

import java.util.Set;
import javax.validation.ConstraintViolation;
import javax.validation.Validation;
import javax.validation.Validator;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 你要仿写的红灯测试（第四层「掌握判定」）。
 *
 * 现状：本文件引用了【尚未创建】的 FaultCreateFixedDto —— 编译不过，红灯。
 * 任务：照 FaultCreateDto.java 的样子，新建
 *   src/main/java/com/example/fault/FaultCreateFixedDto.java
 * 把 @Size 换成 @NotBlank（javax.validation.constraints.NotBlank），
 * 让下面两条断言全绿（坑消失 → violations 不为空）。
 *
 * @NotBlank 的语义 = @NotNull + 非空串 + 非纯空格（三合一）。
 * 它一步就修好上面两个坑：null 被拦、空格也被拦。
 *
 * 对照 Python 侧的修法：schemas.py 的 _strip_required（strip 后重验 min_length）
 *                      + 显式 null 拦截。@NotBlank 相当于把这两步合成一个注解。
 *
 * 提示：
 *   - 字段名和构造器签名照 FaultCreateDto 不变（title, description）
 *   - 只改注解：@Size(min=1, max=200) → @NotBlank + @Size(max=200)（@NotBlank 管下限，@Size 管上限）
 *   - description 同理
 */
class FaultCreateFixedDtoTest {

    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

    @Test
    @DisplayName("FIX #1：纯空格被拒绝（@NotBlank 不放行）")
    void whitespaceRejected() {
        FaultCreateFixedDto dto = new FaultCreateFixedDto("   ", "valid");
        Set<ConstraintViolation<FaultCreateFixedDto>> violations = validator.validate(dto);
        assertFalse(violations.isEmpty(), "修复后空格应被拦截");
    }

    @Test
    @DisplayName("FIX #2：null 被拒绝（@NotBlank 含 @NotNull 语义）")
    void nullRejected() {
        FaultCreateFixedDto dto = new FaultCreateFixedDto(null, "valid");
        Set<ConstraintViolation<FaultCreateFixedDto>> violations = validator.validate(dto);
        assertFalse(violations.isEmpty(), "修复后 null 应被拦截");
    }
}
