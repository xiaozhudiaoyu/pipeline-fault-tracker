package com.example.fault;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 第二层第一个测试：证明「HTTP GET → Controller → Service → JSON」整条链跑通。
 *
 * @SpringBootTest：启动完整 Spring 容器（和真跑 Application 一样，只是不起真端口）。
 * @AutoConfigureMockMvc：注入一个 MockMvc，能在 JVM 内模拟 HTTP 请求，不用 curl。
 *
 * 对照 Python：test_api_faults.py 用 httpx.AsyncClient + ASGITransport 打 app，
 * 本质一样——不起真服务器，在进程内模拟请求。
 *
 * 新语法：
 *   @Autowired —— 让 Spring 把容器里的 Bean 注入到这个字段（测试里常用字段注入）。
 *   mockMvc.perform(get("/api/faults")) —— 模拟一次 GET 请求。
 *   .andExpect(status().isOk()) —— 断言 HTTP 200。
 *   .andExpect(jsonPath("$[0]").value("...")) —— 断言 JSON 数组第一个元素的值。
 *     jsonPath 用 "$" 代表根，"$[0]" 代表数组第一项（类似 Python data[0]）。
 */
@SpringBootTest
@AutoConfigureMockMvc
class FaultControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    @DisplayName("GET /api/faults → 200 + JSON 数组（路由 + DI + 序列化全链路）")
    void listFaultsReturns200WithJson() throws Exception {
        mockMvc.perform(get("/api/faults"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0]").value("fault-1: 管道A泄漏"))
                .andExpect(jsonPath("$[1]").value("fault-2: 管道B压力异常"));
    }
}
