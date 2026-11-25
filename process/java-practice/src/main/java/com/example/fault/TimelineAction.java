package com.example.fault;

import com.fasterxml.jackson.annotation.JsonValue;

/**
 * 时间线动作枚举 —— 对照 models.py 的 TimelineAction（9 个动作）。
 *
 * 这层的新知识点在底部那个 fromValue 方法：
 * Python 里 FaultStatus("pending") / TimelineAction("submit") 能「按 value 反查回枚举」，
 * 是因为它们继承 str 且元类按 value 匹配；Java 枚举【没有】这个能力，必须自己写。
 * （Java 自带的 valueOf("SUBMIT") 只认【常量名大写】，不认 "submit"，且大小写敏感、认不了就抛异常。）
 */
public enum TimelineAction {

    // 常量名用大写、value 用你项目里的下划线小写串。
    // 注意 Python 那个 return_ = "return"（因为 return 是 Python 关键字被迫加下划线）；
    // Java 里常量名 RETURN 不冲突（关键字 return 是小写、且常量名本可大写），value 照样填 "return"。
    CREATE("create"),
    ASSIGN("assign"),
    REASSIGN("reassign"),
    START("start"),
    PROGRESS("progress"),
    SUBMIT("submit"),
    CONFIRM("confirm"),
    RETURN("return"),
    PRIORITY_CHANGE("priority_change");

    private final String value;

    // 枚举构造器仍是（隐式）私有，不能写 public。
    TimelineAction(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }

    // ===== 本层新知识点：按 value 反查（对应 Python 的 TimelineAction("submit")）=====
    // static：属于【类】而非某个实例，调用方式是 TimelineAction.fromValue("submit")，不用 new。
    // 遍历所有常量（values() 是编译器给每个枚举自动生成的方法，返回全部常量的数组）。
    public static TimelineAction fromValue(String value) {
        for (TimelineAction action : values()) {
            if (action.value.equals(value)) {
                return action;
            }
        }
        // 找不到就抛异常 —— 对应 FastAPI/Pydantic 里非法枚举值直接 422 的行为。
        throw new IllegalArgumentException("未知的动作类型: " + value);
    }
}
