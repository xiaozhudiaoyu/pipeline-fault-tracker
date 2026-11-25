package com.example.fault;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 范例的绿灯测试：验证序列化 + 反查 + 非法值抛异常三件事。
 * 先跑绿它，看懂 fromValue 怎么用，再照这个模式给 FaultRole 仿写一个 fromValue。
 */
class TimelineActionTest {

    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    @DisplayName("RETURN 序列化成 \"return\"（常量名大写、value 小写，对齐 Python）")
    void serializesToWireValue() throws Exception {
        assertEquals("\"return\"", mapper.writeValueAsString(TimelineAction.RETURN));
    }

    @Test
    @DisplayName("fromValue 按 value 反查回枚举（对应 Python TimelineAction(\"submit\")）")
    void fromValueLooksUpByWireValue() {
        assertEquals(TimelineAction.SUBMIT, TimelineAction.fromValue("submit"));
        assertEquals(TimelineAction.PRIORITY_CHANGE, TimelineAction.fromValue("priority_change"));
    }

    @Test
    @DisplayName("非法 value 抛 IllegalArgumentException（对应 Pydantic 非法枚举 422）")
    void unknownValueThrows() {
        // () -> 是「 lambda 表达式」，把「一段会抛错的代码」打包交给 assertThrows 去执行。
        assertThrows(IllegalArgumentException.class,
                () -> TimelineAction.fromValue("no_such_action"));
    }
}
