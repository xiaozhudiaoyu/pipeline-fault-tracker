package com.example.fault;

import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 全局校验异常处理器 —— 对照 exceptions.py 的 RequestValidationError handler。
 *
 * Python:
 *   @app.exception_handler(RequestValidationError)
 *   async def validation_handler(request, exc):
 *       return JSONResponse(status_code=422, content={code, message, details})
 *
 * Java:
 *   @RestControllerAdvice  ← 标记为「全局控制器增强」（所有 Controller 的异常都经过这里）
 *   @ExceptionHandler(XxxException.class)  ← 指定捕获哪种异常
 *
 * Spring 默认对 @Valid 失败返回 400；我们改成 422 对齐 FastAPI。
 * 错误体结构也对齐：{code: 422, message: "...", details: [{field, message}]}
 *
 * 新语法：
 *   Map<String, Object>  ← Python dict[str, Any]，Java 用 HashMap 实现
 *   List<Map<...>>       ← Python list[dict]
 *   ResponseEntity.status(422).body(map)  ← 手动指定 HTTP 状态码 + 响应体
 */
@RestControllerAdvice
public class ValidationExceptionHandler {

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(MethodArgumentNotValidException ex) {
        // 把每个字段错误转成 {field, message} 结构
        List<Map<String, String>> details = new ArrayList<>();
        for (FieldError fe : ex.getBindingResult().getFieldErrors()) {
            Map<String, String> item = new HashMap<>();
            item.put("field", fe.getField());
            item.put("message", fe.getDefaultMessage());
            details.add(item);
        }

        // 组装响应体，对齐 Python 侧 ErrorOut 结构
        Map<String, Object> body = new HashMap<>();
        body.put("code", 422);
        body.put("message", "Validation failed");
        body.put("details", details);

        return ResponseEntity.status(422).body(body);
    }

    // ===== 第二种异常：JSON 解析失败（多余字段 / 格式错误） =====
    // 开了 fail-on-unknown-properties=true 后，JSON 里出现 DTO 没有的 key
    // → Jackson 抛 UnrecognizedPropertyException → Spring 包装为 HttpMessageNotReadableException
    // 对照 Python：Pydantic extra="forbid" 时多余字段直接 ValidationError
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Map<String, Object>> handleUnreadable(HttpMessageNotReadableException ex) {
        Map<String, Object> body = new HashMap<>();
        body.put("code", 422);
        body.put("message", "Request body is not readable: " + ex.getMostSpecificCause().getMessage());
        body.put("details", new ArrayList<>());
        return ResponseEntity.status(422).body(body);
    }
}
