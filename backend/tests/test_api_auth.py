# M3 认证模块集成测试：login → me → logout → token_version 失效。
#
# 与 test_phase3_workflow.py::TestAuth 的区别：
#   - TestAuth 是 M0 阶段立下的"红测试基线"，验证的是"业务级需求规则"（未登录访问 /api/faults 应 401），
#     依赖 M4 权限层为业务接口挂 require_login，暂时保持 xfail；
#   - 本文件专测 M3 交付物本身：/api/auth/login /me /logout 的契约、bcrypt + JWT + token_version 闭环。
#
# 覆盖规则（对齐 D3/D4 决策与需求二.4）：
#   AU-M3-1  正确用户名密码 → 200，响应含 access_token / token_type / expires_in
#   AU-M3-2  错误密码 → 401，message 与"用户不存在"一致（防枚举）
#   AU-M3-3  已停用账号登录 → 401，同"密码错误"话术
#   AU-M3-4  GET /me 带有效 token → 200 返回当前用户（不含 password_hash）
#   AU-M3-5  GET /me 不带 token → 401
#   AU-M3-6  POST /logout 后旧 token 立即失效（GET /me → 401）
#   AU-M3-7  bcrypt 哈希比对：同明文两次 hash_password 结果不同（盐随机），checkpw 均返 True

import pytest
from sqlalchemy.orm import Session

from app import crud, schemas
from app.auth import hash_password, verify_password
from app.models import FaultRole, User

pytestmark = pytest.mark.anyio


@pytest.fixture
def seeded_user(db_session: Session) -> schemas.UserCreate:
    """建一个可用的普通用户，返回原始创建数据（含明文密码）。"""
    payload = schemas.UserCreate(
        username="alice",
        password="wonderland",
        display_name="爱丽丝",
        role=FaultRole.user,
    )
    crud.create_user(db_session, payload)
    return payload


class TestAuthLogin:
    async def test_au_m3_1_login_success(self, client, seeded_user):
        resp = await client.post(
            "/api/auth/login",
            json={"username": seeded_user.username, "password": seeded_user.password},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0
        assert isinstance(body["access_token"], str) and body["access_token"]

    async def test_au_m3_2_wrong_password_401(self, client, seeded_user):
        resp = await client.post(
            "/api/auth/login",
            json={"username": seeded_user.username, "password": "wrong"},
        )
        assert resp.status_code == 401

    async def test_au_m3_3_deactivated_account_401(self, client, db_session: Session, seeded_user):
        user = crud.get_user_by_username(db_session, seeded_user.username)
        assert user is not None
        crud.set_user_active(db_session, user, active=False)
        resp = await client.post(
            "/api/auth/login",
            json={"username": seeded_user.username, "password": seeded_user.password},
        )
        assert resp.status_code == 401

    async def test_au_m3_2_unknown_user_same_message(self, client):
        """用户名不存在与密码错误共用同一话术，防枚举。"""
        resp_unknown = await client.post(
            "/api/auth/login", json={"username": "nobody", "password": "x"}
        )
        assert resp_unknown.status_code == 401


class TestAuthMe:
    async def test_au_m3_4_me_returns_current_user(self, client, seeded_user):
        login = await client.post(
            "/api/auth/login",
            json={"username": seeded_user.username, "password": seeded_user.password},
        )
        token = login.json()["access_token"]
        me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        body = me.json()
        assert body["username"] == seeded_user.username
        assert body["display_name"] == seeded_user.display_name
        assert body["role"] == "user"
        assert body["is_active"] is True
        # password_hash / token_version 不在响应里
        assert "password_hash" not in body
        assert "token_version" not in body

    async def test_au_m3_5_me_without_token_401(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_au_m3_5_me_with_bogus_token_401(self, client):
        resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert resp.status_code == 401


class TestAuthLogout:
    async def test_au_m3_6_logout_invalidates_token(self, client, seeded_user):
        login = await client.post(
            "/api/auth/login",
            json={"username": seeded_user.username, "password": seeded_user.password},
        )
        token = login.json()["access_token"]
        # 用一次证明有效
        first = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert first.status_code == 200
        # 登出
        logout = await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert logout.status_code == 204
        # 旧 token 立即失效（token_version bump）
        second = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert second.status_code == 401
        # 重新登录后新 token 生效
        relogin = await client.post(
            "/api/auth/login",
            json={"username": seeded_user.username, "password": seeded_user.password},
        )
        new_token = relogin.json()["access_token"]
        third = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
        assert third.status_code == 200


class TestPasswordHashing:
    """AU-M3-7：bcrypt 直用（D4）的语义校验。"""

    def test_same_password_different_hash(self):
        h1 = hash_password("wonderland")
        h2 = hash_password("wonderland")
        assert h1 != h2, "bcrypt 应内嵌随机盐，同明文两次哈希结果不同"

    def test_verify_password_matches(self):
        h = hash_password("wonderland")
        assert verify_password("wonderland", h) is True
        assert verify_password("wrong", h) is False

    def test_verify_password_malformed_hash_returns_false(self):
        """损坏的哈希串不应抛，直接返回 False。"""
        assert verify_password("anything", "not-a-bcrypt-hash") is False


class TestCreateUser:
    def test_create_user_persists_hashed_password(self, db_session: Session):
        payload = schemas.UserCreate(
            username="bob",
            password="builder",
            display_name="鲍勃",
            role=FaultRole.handler,
        )
        user = crud.create_user(db_session, payload)
        assert isinstance(user, User)
        assert user.id is not None
        # 明文不落库
        assert user.password_hash != payload.password
        assert user.password_hash.startswith("$2")  # bcrypt 前缀 $2a/$2b/$2y
        assert verify_password(payload.password, user.password_hash)
        assert user.token_version == 0
        assert user.is_active is True

    def test_duplicate_username_raises_409(self, db_session: Session):
        from app.exceptions import UsernameDuplicateError
        payload = schemas.UserCreate(
            username="carol",
            password="password1",
            display_name="卡罗尔",
            role=FaultRole.admin,
        )
        crud.create_user(db_session, payload)
        with pytest.raises(UsernameDuplicateError):
            crud.create_user(db_session, payload)
