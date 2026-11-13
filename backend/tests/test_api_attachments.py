# 第 3+4 层：图片附件接口集成测试（第四阶段）。
# httpx ASGITransport 走完整链路：上传（multipart）→ 列表 → 回放 → 删除，
# 并逐一验证格式/大小/张数三类拒绝与跨用户越权拦截。文件落盘用 tmp_path 隔离，
# 通过 monkeypatch 把 settings.upload_dir 指到临时目录，绝不污染开发库目录。
#
# 验收标准清单：
# 【正常】
#   N1 POST 上传 PNG → 201 + AttachmentOut，存储名被重写（≠原始名），content_type=image/png
#   N2 GET /api/faults/{id}/attachments → 200，含刚上传项
#   N3 GET /api/attachments/{id} → 200，字节内容与上传一致，Content-Type/Content-Disposition 正确
#   N4 GET /api/faults/{id} → 详情内嵌 attachments[0]
#   N5 DELETE /api/attachments/{id} → 204，列表转空，磁盘文件删除
# 【异常】
#   E1 上传到不存在故障 → 404 fault_not_found
#   E2 上传非图片字节 → 422 attachment_format_unsupported
#   E3 空文件 → 422 attachment_format_unsupported
#   E4 超过大小上限 → 422 attachment_too_large（半成品不留盘）
#   E5 超过张数上限 → 422 attachment_limit_exceeded
#   E6 未登录回放 → 401
# 【权限】
#   P1 无查看权的普通用户上传/回放他人故障 → 404（不泄露存在性）
#   P2 非创建人且非 admin 删除 → 403
#   P3 已过 pending 删除 → 409
#
# 【时间线附图（第四阶段追加：追加进展/提交结果可附图）】
#   TN1 负责人 progress → 响应带 timeline_id，向该时间线上传 → 201；/timelines 里该条带附件；
#       现场图片集合（GET /api/faults/{id}.attachments）不含时间线附图
#   TN2 submit 结果附图 → 挂在 submit 时间线上，下载字节一致
#   TE1 向不存在的 timeline_id 上传 → 404 timeline_not_found
#   TE2 时间线附图非图片 → 422 attachment_format_unsupported
#   TE3 现场图片 + 时间线附图共享每故障张数预算 → 超限 422
#   TP1 能查看故障但非本条时间线操作人且非 admin 上传 → 403

from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from app import timeutil
from app.config import settings

pytestmark = pytest.mark.anyio

# 最小可辨识文件头：后端只做 magic bytes 判定，不解码图像，故签名 + 任意填充即可。
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_BYTES = PNG_MAGIC + b"\x00" * 24
JPEG_BYTES = JPEG_MAGIC + b"\x00" * 24
NOT_IMAGE = b"this is definitely not a png or jpeg file"


@pytest.fixture(autouse=True)
def _isolate_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """每个用例把附件目录指向独立临时目录，回放/落盘互不干扰。"""
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(settings, "upload_dir", str(upload_root))
    return upload_root


async def _seed_pipeline(client: httpx.AsyncClient) -> int:
    resp = await client.post("/api/pipelines", json={"code": "LINE-A", "name": "总装线A"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _seed_fault(client: httpx.AsyncClient, pipeline_id: int) -> int:
    body = {
        "pipeline_id": pipeline_id,
        "location": "3号工位传送带",
        "occurred_at": (timeutil.business_now() - timedelta(hours=1)).isoformat(),
        "symptom": "传送带异响并卡死",
    }
    resp = await client.post("/api/faults", json=body)
    assert resp.status_code == 201
    return resp.json()["id"]


async def _upload(
    client: httpx.AsyncClient, fault_id: int, content: bytes, filename: str = "现场照片.png"
) -> httpx.Response:
    return await client.post(
        f"/api/faults/{fault_id}/attachments",
        files={"file": (filename, content, "image/png")},
    )


def _assert_error_shape(payload: dict, code: str) -> None:
    assert payload["code"] == code
    assert isinstance(payload["message"], str) and payload["message"]
    assert isinstance(payload["details"], list)


# ── 正常路径 ──────────────────────────────────────────────────────────
async def test_n1_upload_png_ok_rewrites_filename(client: httpx.AsyncClient, _isolate_upload_dir: Path):
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)

    resp = await _upload(client, fid, PNG_BYTES, filename="../恶意/名字.png")
    assert resp.status_code == 201, resp.text
    data = resp.json()

    # 存储文件名被重写：不含原始名、无路径分隔符，落盘在隔离目录里。
    assert data["content_type"] == "image/png"
    assert "名字" not in data["url"]
    assert data["size_bytes"] == len(PNG_BYTES)
    assert data["uploader_id"] is not None
    files = list(_isolate_upload_dir.iterdir())
    assert len(files) == 1
    assert files[0].read_bytes() == PNG_BYTES

    # 详情内嵌 attachments（N4 一并固化）
    detail = await client.get(f"/api/faults/{fid}")
    assert detail.status_code == 200
    embedded = detail.json()["attachments"]
    assert len(embedded) == 1
    assert embedded[0]["id"] == data["id"]


async def test_n2_n3_list_and_download_roundtrip(client: httpx.AsyncClient):
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    up = await _upload(client, fid, JPEG_BYTES)
    att_id = up.json()["id"]

    listed = await client.get(f"/api/faults/{fid}/attachments")
    assert listed.status_code == 200
    assert [a["id"] for a in listed.json()] == [att_id]

    down = await client.get(f"/api/attachments/{att_id}")
    assert down.status_code == 200
    assert down.content == JPEG_BYTES
    assert down.headers["content-type"] == "image/jpeg"
    assert "inline" in down.headers["content-disposition"]


async def test_n5_delete_removes_row_and_file(client: httpx.AsyncClient, _isolate_upload_dir: Path):
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    att_id = (await _upload(client, fid, PNG_BYTES)).json()["id"]
    assert len(list(_isolate_upload_dir.iterdir())) == 1

    dele = await client.delete(f"/api/attachments/{att_id}")
    assert dele.status_code == 204
    assert list(_isolate_upload_dir.iterdir()) == []  # 磁盘文件已删

    after = await client.get(f"/api/faults/{fid}/attachments")
    assert after.json() == []
    gone = await client.get(f"/api/attachments/{att_id}")
    assert gone.status_code == 404


# ── 异常路径 ──────────────────────────────────────────────────────────
async def test_e1_upload_to_missing_fault_404(client: httpx.AsyncClient):
    resp = await _upload(client, 999999, PNG_BYTES)
    assert resp.status_code == 404
    _assert_error_shape(resp.json(), "fault_not_found")


async def test_e2_upload_non_image_422(client: httpx.AsyncClient, _isolate_upload_dir: Path):
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    resp = await _upload(client, fid, NOT_IMAGE)
    assert resp.status_code == 422
    _assert_error_shape(resp.json(), "attachment_format_unsupported")
    # 不合格文件不留半成品
    assert list(_isolate_upload_dir.iterdir()) == []


async def test_e3_empty_file_422(client: httpx.AsyncClient):
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    resp = await _upload(client, fid, b"")
    assert resp.status_code == 422
    _assert_error_shape(resp.json(), "attachment_format_unsupported")


async def test_e4_too_large_422(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, _isolate_upload_dir: Path):
    monkeypatch.setattr(settings, "attachment_max_bytes", 16)
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    resp = await _upload(client, fid, PNG_BYTES)  # 32 字节 > 16
    assert resp.status_code == 422
    _assert_error_shape(resp.json(), "attachment_too_large")
    assert list(_isolate_upload_dir.iterdir()) == []


async def test_e5_over_count_limit_422(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "attachment_max_per_fault", 1)
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    first = await _upload(client, fid, PNG_BYTES)
    assert first.status_code == 201
    second = await _upload(client, fid, PNG_BYTES)
    assert second.status_code == 422
    _assert_error_shape(second.json(), "attachment_limit_exceeded")


async def test_e6_download_without_auth_401(raw_client: httpx.AsyncClient):
    # 回放端点鉴权走 get_current_user 依赖（与业务逻辑解耦），依赖先于函数体执行：
    # 未带凭证直接 401，无需真实存在的附件（口径同 AU1 / USR-2 的 raw_client 匿名请求）。
    resp = await raw_client.get("/api/attachments/1")
    assert resp.status_code == 401


# ── 权限路径 ──────────────────────────────────────────────────────────
async def test_p1_stranger_cannot_upload_or_download(client: httpx.AsyncClient, login_as, creator_user):
    # client 默认 admin 建故障（created_by=admin）；切到另一个普通用户，无查看权。
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    att_id = (await _upload(client, fid, PNG_BYTES)).json()["id"]

    login_as(creator_user)
    up = await _upload(client, fid, PNG_BYTES)
    assert up.status_code == 404  # 越权与不存在同为 404
    down = await client.get(f"/api/attachments/{att_id}")
    assert down.status_code == 404


async def test_p2_non_owner_delete_forbidden(client: httpx.AsyncClient, login_as, creator_user):
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    att_id = (await _upload(client, fid, PNG_BYTES)).json()["id"]

    login_as(creator_user)  # 普通用户既非创建人亦非 admin
    resp = await client.delete(f"/api/attachments/{att_id}")
    assert resp.status_code == 403


async def test_p3_delete_after_pending_conflict(
    client: httpx.AsyncClient, login_as, admin_user, handler_user
):
    # admin 建故障并上传，指派 handler 并开始处理（→ processing）。
    # 删除权限面镜像 update_fault：先过状态门槛（非 pending → 409）再判归属。
    # 用具备删除权限的 admin 视角验证“过 pending → 409”，隔离掉权限维度。
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    att_id = (await _upload(client, fid, PNG_BYTES)).json()["id"]

    assign = await client.post(f"/api/faults/{fid}/assign", json={"assignee_id": handler_user.id})
    assert assign.status_code == 200
    login_as(handler_user)
    assert (await client.post(f"/api/faults/{fid}/start")).status_code == 200

    # client fixture 初始即 admin，上面 login_as 已切走，显式复位到 admin（同一 admin_user 实例）。
    login_as(admin_user)
    resp = await client.delete(f"/api/attachments/{att_id}")
    assert resp.status_code == 409
    _assert_error_shape(resp.json(), "invalid_transition")

    # 409 属拒绝、不产生副作用：附件行与磁盘文件均应还在。
    still = await client.get(f"/api/faults/{fid}/attachments")
    assert [a["id"] for a in still.json()] == [att_id]


# ── 时间线附图（第四阶段追加）─────────────────────────────────────
async def _upload_timeline(
    client: httpx.AsyncClient, timeline_id: int, content: bytes, filename: str = "进展图.png"
) -> httpx.Response:
    return await client.post(
        f"/api/timelines/{timeline_id}/attachments",
        files={"file": (filename, content, "image/png")},
    )


async def _start_and_progress(client, login_as, admin_user, handler_user, fid) -> int:
    """admin 指派 handler → handler 开始并追进一条进展，返回该进展时间线 id。"""
    assert (await client.post(f"/api/faults/{fid}/assign", json={"assignee_id": handler_user.id})).status_code == 200
    login_as(handler_user)
    assert (await client.post(f"/api/faults/{fid}/start")).status_code == 200
    prog = await client.post(f"/api/faults/{fid}/progress", json={"note": "已更换轴承待复测"})
    assert prog.status_code == 200
    return prog.json()["timeline_id"]


async def test_tn1_progress_attachment_in_timeline_not_gallery(
    client: httpx.AsyncClient, login_as, admin_user, handler_user
):
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    tid = await _start_and_progress(client, login_as, admin_user, handler_user, fid)

    # handler 是本条进展的操作人，附图 → 201。
    up = await _upload_timeline(client, tid, PNG_BYTES)
    assert up.status_code == 201, up.text
    att_id = up.json()["id"]

    # /timelines：该进展条目携带附图。
    login_as(admin_user)
    tl = await client.get(f"/api/faults/{fid}/timelines")
    assert tl.status_code == 200
    entry = next(e for e in tl.json() if e["id"] == tid)
    assert [a["id"] for a in entry["attachments"]] == [att_id]

    # 现场图片集合不包含时间线附图（分离口径）。
    gallery = await client.get(f"/api/faults/{fid}")
    assert gallery.json()["attachments"] == []


async def test_tn2_submit_attachment_roundtrip(
    client: httpx.AsyncClient, login_as, admin_user, handler_user
):
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    tid = await _start_and_progress(client, login_as, admin_user, handler_user, fid)

    # 提交结果（handler）→ 带 submit 时间线 id，向它上传 JPEG。
    sub = await client.post(f"/api/faults/{fid}/submit", json={"result_note": "更换轴承并复测正常"})
    assert sub.status_code == 200
    submit_tid = sub.json()["timeline_id"]
    up = await _upload_timeline(client, submit_tid, JPEG_BYTES, filename="结案.jpg")
    assert up.status_code == 201
    att_id = up.json()["id"]

    login_as(admin_user)
    down = await client.get(f"/api/attachments/{att_id}")
    assert down.status_code == 200
    assert down.content == JPEG_BYTES
    tl = await client.get(f"/api/faults/{fid}/timelines")
    entry = next(e for e in tl.json() if e["id"] == submit_tid)
    assert [a["id"] for a in entry["attachments"]] == [att_id]


async def test_te1_missing_timeline_404(client: httpx.AsyncClient):
    resp = await _upload_timeline(client, 999999, PNG_BYTES)
    assert resp.status_code == 404
    _assert_error_shape(resp.json(), "timeline_not_found")


async def test_te2_non_image_422(client: httpx.AsyncClient, login_as, admin_user, handler_user, _isolate_upload_dir: Path):
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    tid = await _start_and_progress(client, login_as, admin_user, handler_user, fid)
    resp = await _upload_timeline(client, tid, NOT_IMAGE)
    assert resp.status_code == 422
    _assert_error_shape(resp.json(), "attachment_format_unsupported")
    # 不合格文件不留半成品
    assert list(_isolate_upload_dir.iterdir()) == []


async def test_te3_shared_count_budget(
    client: httpx.AsyncClient, login_as, admin_user, handler_user, monkeypatch: pytest.MonkeyPatch
):
    # 预算共享：时间线附图占掉 1 张后，现场图片再传即超 1 张上限 → 422。
    monkeypatch.setattr(settings, "attachment_max_per_fault", 1)
    pid = await _seed_pipeline(client)
    fid = await _seed_fault(client, pid)
    tid = await _start_and_progress(client, login_as, admin_user, handler_user, fid)
    assert (await _upload_timeline(client, tid, PNG_BYTES)).status_code == 201
    login_as(admin_user)
    second = await _upload(client, fid, PNG_BYTES)
    assert second.status_code == 422
    _assert_error_shape(second.json(), "attachment_limit_exceeded")


async def test_tp1_non_operator_viewer_forbidden(
    client: httpx.AsyncClient, login_as, admin_user, handler_user, creator_user
):
    # creator_user 建故障（自己是创建人→可看），handler 做进展（操作人）；
    # creator_user 能看故障但不是本条时间线操作人且非 admin → 403。
    pid = await _seed_pipeline(client)  # admin 建流水线
    login_as(creator_user)
    fid = await _seed_fault(client, pid)  # created_by = creator_user
    login_as(admin_user)
    assert (await client.post(f"/api/faults/{fid}/assign", json={"assignee_id": handler_user.id})).status_code == 200
    login_as(handler_user)
    assert (await client.post(f"/api/faults/{fid}/start")).status_code == 200
    prog = await client.post(f"/api/faults/{fid}/progress", json={"note": "已更换轴承待复测"})
    tid = prog.json()["timeline_id"]

    login_as(creator_user)
    resp = await _upload_timeline(client, tid, PNG_BYTES)
    assert resp.status_code == 403
    _assert_error_shape(resp.json(), "permission_denied")

