package com.example.fault;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.validation.Valid;
import java.util.List;

/**
 * HTTP 控制器 —— 对照 routers/faults.py。
 *
 * Python:
 *   router = APIRouter(prefix="/api/faults")
 *   @router.get("")
 *   def list_faults(db: Session = Depends(get_db)):
 *       return crud.list_faults(db)
 *
 * Java:
 *   @RestController + @RequestMapping("/api/faults")  ← 路由前缀
 *   @GetMapping                                       ← GET ""
 *   构造器注入 FaultService                            ← Depends(get_db) 的替代
 *
 * 核心差异（DI 哲学）：
 *   FastAPI: Depends(get_db) 每请求执行一次函数，拿到新 session
 *   Spring:  构造器注入在启动时执行一次，Bean 是单例，之后每请求复用同一个实例
 *   → 所以「请求态数据」（当前用户、DB session）不能存 Bean 字段里！
 *     后面用 @Transactional + EntityManager 或 SecurityContextHolder 解决。
 */
@RestController
@RequestMapping("/api/faults")
public class FaultController {

    private final FaultService faultService;

    // 构造器注入：Spring 发现本类只有一个构造器，自动把容器里的 FaultService Bean 传进来。
    // 不需要 @Autowired 注解（单构造器时 Spring 4.3+ 自动推断）。
    // 对照 Python：def __init__(self, fault_service: FaultService) 但 Python 没有容器帮你 new。
    public FaultController(FaultService faultService) {
        this.faultService = faultService;
    }

    // @GetMapping 无参数 = 映射 GET /api/faults（前缀由类上 @RequestMapping 提供）
    // 返回值被 Jackson 自动序列化为 JSON（List<String> → ["...", "..."]）
    @GetMapping
    public List<String> list() {
        return faultService.listFaults();
    }

    // ===== 第二层第二步：POST + @Valid =====
    // @RequestBody：把请求体 JSON 反序列化为 FaultCreateFixedDto 对象（对照 Pydantic model 参数）
    // @Valid：触发 Bean Validation（对照 Pydantic 自动校验）
    // 校验失败时 Spring 抛 MethodArgumentNotValidException，
    // 被 ValidationExceptionHandler 捕获 → 返回 422（对齐 FastAPI）。
    @PostMapping
    public ResponseEntity<String> create(@Valid @RequestBody FaultCreateFullDto dto) {
        // 暂不接 DB，先回 201 + 标题（第三层接 JPA 后替换为真实入库）
        return ResponseEntity.status(201).body("created: " + dto.getTitle());
    }
}
