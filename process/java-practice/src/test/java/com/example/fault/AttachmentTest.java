package com.example.fault;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 你要仿写的红灯测试（掌握判定 #2 的「你来写」部分）。
 *
 * 现状：本文件引用了【尚未创建】的 com.example.fault.Attachment —— 编译不过，红灯。
 * 任务：照 Timeline.java 的样子，新建
 *   src/main/java/com/example/fault/Attachment.java
 * 实现「上传人显示名回退快照」，让下面三条断言全绿。
 *
 * 业务对照 models.py 的 FaultAttachment.uploader_name（和 Timeline.operator_name 是【同一个模式】）：
 *   @property
 *   def uploader_name(self):
 *       return self.uploader.display_name if self.uploader is not None else self.uploader_name_snapshot
 *
 * 需要的成员（自己拼，别抄 Timeline，练记忆）：
 *   - 两个可空字段：User uploader、String uploaderNameSnapshot
 *   - 一个构造器：Attachment(User uploader, String uploaderNameSnapshot)
 *   - 一个派生 getter：getUploaderName()，逻辑同 operator_name 回退
 *
 * 提示：这次是「一模一样结构的第二次」——正是练肌肉记忆的题。敲完跑绿，第一层就齐了。
 */
class AttachmentTest {

    @Test
    @DisplayName("uploader 存在 → 取当前用户显示名")
    void prefersLiveUploader() {
        Attachment a = new Attachment(new User("王上传"), "旧快照");
        assertEquals("王上传", a.getUploaderName());
    }

    @Test
    @DisplayName("uploader 为 null → 回退快照")
    void fallsBackToSnapshot() {
        Attachment a = new Attachment(null, "已注销的上传人");
        assertEquals("已注销的上传人", a.getUploaderName());
    }

    @Test
    @DisplayName("两者都 null → 返回 null")
    void bothNull() {
        Attachment a = new Attachment(null, null);
        assertNull(a.getUploaderName());
    }
}
