package com.example.fault;

/**
 * 时间线一条记录 —— 只保留这次练习要的「操作人显示名」回退逻辑。
 *
 * 对照 models.py 的 FaultTimeline：
 *   @property
 *   def operator_name(self):
 *       return self.operator.display_name if self.operator is not None else self.operator_name_snapshot
 *
 * 这就是你项目里「账号被删（operator 变 null）后，仍能显示当时快照名」的业务规则。
 */
public class Timeline {

    // 可空字段：operator 是「对象引用」，没关联到用户时为 null（Java 里对象默认就是 null）。
    private final User operator;
    // 可空字段：写入时的名称快照，字符串，也可能为 null。
    private final String operatorNameSnapshot;

    public Timeline(User operator, String operatorNameSnapshot) {
        this.operator = operator;
        this.operatorNameSnapshot = operatorNameSnapshot;
    }

    // 派生 getter：值不是存的，是每次调用现算的。对应 Python 的 @property。
    // 三元运算符 a ? b : c —— 就是 Python 的「b if a else c」，只是把条件放前面。
    public String getOperatorName() {
        return operator != null ? operator.getDisplayName() : operatorNameSnapshot;
    }
}
