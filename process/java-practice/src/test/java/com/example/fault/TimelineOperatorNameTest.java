package com.example.fault;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 参考实现的绿灯测试（三条分支，对应掌握判定 #2）。
 * 这个不用你写——先跑绿，确认范例逻辑正确，再照着仿写 Attachment。
 */
class TimelineOperatorNameTest {

    @Test
    @DisplayName("operator 存在 → 取当前用户显示名")
    void prefersLiveOperator() {
        Timeline t = new Timeline(new User("张处理"), "旧快照名");
        assertEquals("张处理", t.getOperatorName());
    }

    @Test
    @DisplayName("operator 为 null → 回退到写入时快照")
    void fallsBackToSnapshot() {
        Timeline t = new Timeline(null, "已注销的人");
        assertEquals("已注销的人", t.getOperatorName());
    }

    @Test
    @DisplayName("operator 与快照都 null → 返回 null（交展示层占位）")
    void bothNull() {
        Timeline t = new Timeline(null, null);
        assertNull(t.getOperatorName());
    }
}
