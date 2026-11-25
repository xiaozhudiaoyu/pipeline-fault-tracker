package com.example.fault;

import com.fasterxml.jackson.annotation.JsonValue;

/**
 * 故障处理状态枚举 —— 对照 backend/app/models.py 的 class FaultStatus(str, enum.Enum)。
 *
 * Python 里那个枚举「继承 str」，所以 JSON 序列化天然得到小写串 "pending"。
 * Java 的枚举本身只是「一组带名字的常量」，跟字符串没关系，
 * 所以要自己：① 给每个常量挂一个小写 value；② 用 @JsonValue 告诉 Jackson「序列化时输出这个 value」。
 */
public enum FaultStatus {

    // 常量名用大写（Java 惯例）；括号里挂上对应的小写字符串。最后一行用分号结尾。
    PENDING("pending"),
    PROCESSING("processing"),
    AWAITING_CONFIRMATION("awaiting_confirmation"),
    DONE("done");

    // 每个常量都自带一个 value 字段。final = 一旦构造就不可再改。
    private final String value;

    // 枚举构造器：只在上面声明常量时被自动调用一次，把括号里的字符串存进 value。
    FaultStatus(String value) {
        this.value = value;
    }

    // @JsonValue 让 Jackson 序列化时输出 getValue() 的结果（"pending"），而不是常量名（"PENDING"）。
    @JsonValue
    public String getValue() {
        return value;
    }
}
