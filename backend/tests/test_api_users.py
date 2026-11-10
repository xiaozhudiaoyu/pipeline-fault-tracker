# M6 补充：/api/users 用户管理端点集成测试（高风险面——权限边界逐条覆盖，需求九.3）。
#
# 覆盖规则：
#   USR-1  admin GET /api/users → 200，返回含 is_active 的完整账户字段
#   USR-2  非 admin（handler / 普通用户 / 未登录）访问任意 /api/users 端点 → 403 / 401
#   USR-3  admin POST 创建 → 201，响应不含 password_hash；重名 → 409
#   USR-4  admin PATCH 停用他人 → 200 且 token_version bump；停用自己 → 403
#   USR-5  admin POST 重置密码 → 200，落库为新哈希且 token_version bump（旧 token 失效）
#   USR-6  操作不存在的用户 ID → 404

import pytest
from sqlalchemy.orm import Session

from app import crud, schemas
from app.auth import verify_password
from app.models import FaultRole

pytestmark = pytest.mark.anyio


def _mk(db: Session, username: str, role: FaultRole):
    return crud.create_user(
        db,
        schemas.UserCreate(
            username=username, password="origin123", display_name=username, role=role
        ),
    )


class TestUsersAccess:
    async def test_usr_1_admin_list(self, client, db_session: Session):
        _mk(db_session, "hand1", FaultRole.handler)
        resp = await client.get("/api/users")
        assert resp.status_code == 200
        names = [u["username"] for u in resp.json()]
        assert "hand1" in names and "test_admin" in names
        # 完整账户字段可见（管理页需要），密码哈希绝不可见
        assert all("is_active" in u and "password_hash" not in u for u in resp.json())

    async def test_usr_2_handler_forbidden(self, client, login_as, db_session: Session):
        login_as(_mk(db_session, "hand2", FaultRole.handler))
        resp = await client.get("/api/users")
        assert resp.status_code == 403

    async def test_usr_2_plain_user_forbidden(self, client, login_as, db_session: Session):
        login_as(_mk(db_session, "usr2", FaultRole.user))
        resp = await client.post(
            "/api/users",
            json={"username": "nobody", "password": "whatever1", "display_name": "x", "role": "user"},
        )
        assert resp.status_code == 403

    async def test_usr_2_anonymous_401(self, raw_client):
        resp = await raw_client.get("/api/users")
        assert resp.status_code == 401


class TestUsersCreate:
    async def test_usr_3_create_ok(self, client):
        resp = await client.post(
            "/api/users",
            json={
                "username": "newbie",
                "password": "secret123",
                "display_name": "新人",
                "role": "handler",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["username"] == "newbie" and body["role"] == "handler"
        assert body["is_active"] is True
        assert "password_hash" not in body

    async def test_usr_3_duplicate_username_409(self, client, db_session: Session):
        _mk(db_session, "dup", FaultRole.user)
        resp = await client.post(
            "/api/users",
            json={"username": "dup", "password": "secret123", "display_name": "重名", "role": "user"},
        )
        assert resp.status_code == 409

    async def test_usr_3_short_password_422(self, client):
        resp = await client.post(
            "/api/users",
            json={"username": "shorty", "password": "123", "display_name": "短", "role": "user"},
        )
        assert resp.status_code == 422


class TestUsersActiveToggle:
    async def test_usr_4_deactivate_others_bumps_token(self, client, db_session: Session):
        target = _mk(db_session, "vic", FaultRole.handler)
        tv_before = target.token_version
        resp = await client.patch(f"/api/users/{target.id}/active", json={"is_active": False})
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        refreshed = crud.get_user(db_session, target.id)
        assert refreshed.token_version == tv_before + 1  # 停用即时失效其全部 token

    async def test_usr_4_cannot_deactivate_self(self, client, admin_user):
        resp = await client.patch(f"/api/users/{admin_user.id}/active", json={"is_active": False})
        assert resp.status_code == 403

    async def test_usr_6_unknown_id_404(self, client):
        resp = await client.patch("/api/users/99999/active", json={"is_active": False})
        assert resp.status_code == 404


class TestUsersResetPassword:
    async def test_usr_5_reset_rehashes_and_invalidates(self, client, db_session: Session):
        target = _mk(db_session, "forgetful", FaultRole.user)
        old_hash, tv_before = target.password_hash, target.token_version
        resp = await client.post(
            f"/api/users/{target.id}/reset-password", json={"password": "brandnew1"}
        )
        assert resp.status_code == 200
        refreshed = crud.get_user(db_session, target.id)
        assert refreshed.password_hash != old_hash
        assert verify_password("brandnew1", refreshed.password_hash)
        assert not verify_password("origin123", refreshed.password_hash)
        assert refreshed.token_version == tv_before + 1  # 旧 token 全失效

    async def test_usr_5_reset_unknown_404(self, client):
        resp = await client.post("/api/users/99999/reset-password", json={"password": "brandnew1"})
        assert resp.status_code == 404
