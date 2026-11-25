package com.example.fault;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDateTime;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * POST + @Valid 的 HTTP 级测试 —— 第四层「掌握判定」的 HTTP 部分开始补验。
 *
 * 对照 Python test_api_faults.py 里用 httpx 打 POST /api/faults 断言 422 的那些用例。
 *
 * 新语法：
 *   post("/api/faults")          ← 模拟 POST（之前只用了 get）
 *   .contentType(MediaType.APPLICATION_JSON)  ← 设 Content-Type 头
 *   .content("{...}")            ← 原始 JSON 字符串作为请求体
 *   status().isUnprocessableEntity()  ← 断言 422
 *   status().isCreated()         ← 断言 201
 *   jsonPath("$.details[0].field")  ← 嵌套 JSON 路径（$ → details 数组 → 第 0 项 → field 键）
 */
@SpringBootTest
@AutoConfigureMockMvc
class FaultControllerPostTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    @DisplayName("POST 纯空格 title → 422 + details 含 field=title（空格穿过坑已修）")
    void postWithWhitespaceReturns422() throws Exception {
        mockMvc.perform(post("/api/faults")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"   \",\"description\":\"valid\",\"pipelineId\":1}"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value(422))
                .andExpect(jsonPath("$.details[0].field").value("title"));
    }

    @Test
    @DisplayName("POST null title → 422（显式 null 坑已修）")
    void postWithNullReturns422() throws Exception {
        mockMvc.perform(post("/api/faults")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":null,\"description\":\"valid\",\"pipelineId\":1}"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value(422));
    }

    @Test
    @DisplayName("POST 合法数据 → 201")
    void postWithValidDataReturns201() throws Exception {
        mockMvc.perform(post("/api/faults")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"管道泄漏\",\"description\":\"详细描述\",\"pipelineId\":1}"))
                .andExpect(status().isCreated());
    }

    // ===== 第四层剩余 3 个 HTTP 判定 =====

    @Test
    @DisplayName("POST location 首字符空格 → 422（@Pattern 拦截）")
    void postWithLeadingSpaceLocationReturns422() throws Exception {
        mockMvc.perform(post("/api/faults")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"ok\",\"description\":\"ok\",\"location\":\" abc\",\"pipelineId\":1}"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value(422))
                .andExpect(jsonPath("$.details[0].field").value("location"));
    }

    @Test
    @DisplayName("POST 混入多余字段 status → 422（extra forbid，对齐 Pydantic）")
    void postWithExtraFieldReturns422() throws Exception {
        mockMvc.perform(post("/api/faults")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"ok\",\"description\":\"ok\",\"pipelineId\":1,\"status\":\"done\"}"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value(422));
    }

    @Test
    @DisplayName("POST 缺 pipelineId → 422（@NotNull 拦必填字段缺失）")
    void postWithoutPipelineIdReturns422() throws Exception {
        mockMvc.perform(post("/api/faults")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"ok\",\"description\":\"ok\"}"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value(422))
                .andExpect(jsonPath("$.details[0].field").value("pipelineId"));
    }

    @Test
    @DisplayName("POST occurredAt 未来时间(+120s) → 422（自定义约束 @NotInFutureWithTolerance）")
    void postWithFutureOccurredAtReturns422() throws Exception {
        // 动态计算未来时间，截断纳秒保证 ISO 格式干净
        String futureTime = LocalDateTime.now().plusSeconds(120).withNano(0).toString();
        String json = "{\"title\":\"ok\",\"description\":\"ok\",\"pipelineId\":1,"
                + "\"occurredAt\":\"" + futureTime + "\"}";
        mockMvc.perform(post("/api/faults")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value(422))
                .andExpect(jsonPath("$.details[0].field").value("occurredAt"));
    }
}
