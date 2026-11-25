package com.example.fault;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 第一层「语法与 OOP」——掌握判定 #1 的起步红灯测试（TDD）。
 *
 * 现状：本文件引用了【尚未创建】的 {@code com.example.fault.FaultStatus}，
 * 所以现在整个测试模块【编译不通过】——这就是 Java 里 TDD 的第一种「红」：
 * 「先让代码因缺实现而编译失败，再用最小实现把它点亮」。
 *
 * 你要做的第一步：在
 *   process/java-practice/src/main/java/com/example/fault/FaultStatus.java
 * 手写这个枚举，让下面三个断言全部跑绿。
 *
 * 对照教材：backend/app/models.py 的
 *   class FaultStatus(str, enum.Enum):
 *       pending = "pending"
 *       processing = "processing"
 *       awaiting_confirmation = "awaiting_confirmation"
 *       done = "done"
 * 实测就是 4 个取值（不是 5），以代码为准。
 *
 * 关键要求：Python 那个枚举继承了 str，所以 JSON 序列化【白得】小写串。
 * Java 枚举与字符串是两回事，必须在每个常量上携带小写 value，并用 Jackson 的
 * {@code @JsonValue} 标注该字段，序列化才会输出 "pending" 而非 "PENDING"。
 * 这正是「换语言后同一需求要额外补一刀」的第一个真实体感。
 *
 * 提示（不给答案，只给形状）：
 *   public enum FaultStatus {
 *       PENDING("pending"), PROCESSING("processing"),
 *       AWAITING_CONFIRMATION("awaiting_confirmation"), DONE("done");
 *       private final String value;
 *       FaultStatus(String value) { this.value = value; }
 *       @JsonValue public String getValue() { return value; }
 *   }
 * —— 亲手敲一遍、跑绿，比抄这段提示收获大；上面只是让你确认方向没跑偏。
 */
class FaultStatusTest {

    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    @DisplayName("PENDING 序列化成小写串 \"pending\"（对齐 Python 继承 str 的行为）")
    void serializesToLowerCase() throws Exception {
        assertEquals("\"pending\"", mapper.writeValueAsString(FaultStatus.PENDING));
    }

    @Test
    @DisplayName("四个状态都序列化成需求里的字符串")
    void allStatesSerialize() throws Exception {
        assertEquals("\"processing\"", mapper.writeValueAsString(FaultStatus.PROCESSING));
        assertEquals("\"awaiting_confirmation\"", mapper.writeValueAsString(FaultStatus.AWAITING_CONFIRMATION));
        assertEquals("\"done\"", mapper.writeValueAsString(FaultStatus.DONE));
    }

    @Test
    @DisplayName("getValue() 暴露原始字符串（对应 Python 的 fault.status.value）")
    void exposesWireValue() {
        assertEquals("awaiting_confirmation", FaultStatus.AWAITING_CONFIRMATION.getValue());
    }
}
