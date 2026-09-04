# -*- coding: utf-8 -*-
"""
轻量密码登录鉴权（密码即账号）
- 666666  → guest（访客：仅可浏览历史）
- 071527  → admin（管理员：可开始/继续面试，消耗 API）
token 保存在内存中，重启后需重新登录。
"""
import os
import threading
import time
import uuid

# 密码可通过环境变量覆盖（默认值见下）
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "071527")
GUEST_PASSWORD = os.environ.get("GUEST_PASSWORD", "666666")

TOKEN_TTL = 7 * 24 * 3600  # 7 天

# token -> (role, expire_ts)
_tokens = {}
_lock = threading.Lock()

ROLE_NAMES = {
    "admin": "管理员",
    "guest": "访客",
}


def login(password: str):
    """校验密码，成功则签发 token"""
    password = (password or "").strip()
    if password == ADMIN_PASSWORD:
        role = "admin"
    elif password == GUEST_PASSWORD:
        role = "guest"
    else:
        return None

    token = uuid.uuid4().hex
    with _lock:
        _tokens[token] = (role, time.time() + TOKEN_TTL)
    return {"token": token, "role": role, "name": ROLE_NAMES[role]}


def _cleanup():
    now = time.time()
    with _lock:
        expired = [t for t, (_, exp) in _tokens.items() if exp < now]
        for t in expired:
            del _tokens[t]


def _resolve_role(token: str):
    """返回 token 对应角色，无效/过期返回 None"""
    if not token:
        return None
    _cleanup()
    with _lock:
        item = _tokens.get(token)
    if not item:
        return None
    role, exp = item
    if exp < time.time():
        with _lock:
            _tokens.pop(token, None)
        return None
    return role


def get_role_from_authorization(authorization: str):
    """从 Authorization: Bearer xxx 解析角色"""
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return _resolve_role(parts[1].strip())


def logout(token: str):
    """登出：删除 token"""
    with _lock:
        _tokens.pop(token, None)
