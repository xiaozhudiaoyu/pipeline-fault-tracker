package com.example.fault;

import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.List;

/**
 * 业务层 Bean —— 对照 crud.py 里的查询函数。
 *
 * @Service 告诉 Spring："把这个类注册为一个 Bean（单例），别人需要时自动注入。"
 * 对照 Python：FastAPI 没有 DI 容器，crud 函数是普通函数，谁调谁 import。
 * Spring 的 Bean 由容器管理生命周期，默认整个进程只有一个实例。
 *
 * 暂用硬编码数据（第三层接 JPA 后替换为真实 DB 查询）。
 */
@Service
public class FaultService {

    public List<String> listFaults() {
        return Arrays.asList(
                "fault-1: 管道A泄漏",
                "fault-2: 管道B压力异常"
        );
    }
}
