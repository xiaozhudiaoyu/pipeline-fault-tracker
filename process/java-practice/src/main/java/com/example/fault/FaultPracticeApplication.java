package com.example.fault;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Spring Boot 启动入口 —— 对照 main.py 的 app = FastAPI()。
 *
 * @SpringBootApplication 是一个组合注解，等于同时贴了三个：
 *   @Configuration      —— 本类是配置源
 *   @EnableAutoConfiguration —— 根据 classpath 自动装配（有 Tomcat 就起 Web 服务器）
 *   @ComponentScan      —— 扫描本包及子包下所有 @Service/@Controller/@Component
 *
 * Python 对照：
 *   app = FastAPI()          ← 创建应用
 *   app.include_router(...)  ← 注册路由
 *   uvicorn.run(app)         ← 启动服务器
 * Java 这三步合成一个注解 + 一行 main。
 */
@SpringBootApplication
public class FaultPracticeApplication {

    public static void main(String[] args) {
        SpringApplication.run(FaultPracticeApplication.class, args);
    }
}
