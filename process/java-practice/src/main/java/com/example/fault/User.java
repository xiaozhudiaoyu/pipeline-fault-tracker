package com.example.fault;

/**
 * 极简 User —— 只保留这次练习要用的 displayName。
 * 对照 models.py 里 User.display_name 字段（真实模型字段多得多，这里按需裁剪）。
 */
public class User {

    // final：一旦在构造器里赋值，之后不可再改（对应你熟悉的「不可变」倾向）。
    private final String displayName;

    // 构造器：方法名 = 类名、无返回类型。new User("张处理") 就是调它。
    public User(String displayName) {
        this.displayName = displayName;
    }

    // getter：Java 里 private 字段对外读取的惯例方式（不像 Python 直接 obj.display_name）。
    public String getDisplayName() {
        return displayName;
    }
}
