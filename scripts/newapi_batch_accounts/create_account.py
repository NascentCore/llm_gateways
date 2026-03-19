#!/usr/bin/env python3
"""
NewAPI 批量建号脚本：创建用户（opc-2026-03-20-XXX）、设置额度、创建不限额 API Key，输出用户名/API_KEY/额度。
编号由查询用户列表自动确定，只需输入金额（人民币）。
"""

import argparse
import os
import re
import sys

try:
    import requests
except ImportError:
    print("需要 requests 库，请执行: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

USERNAME_PREFIX = "opc-2026-03-20-"
PASSWORD = "sxwl66620260320!"
QUOTA_MULTIPLIER = 73529
SEARCH_PAGE_SIZE = 200


def _step(n: int, total: int, msg: str):
    print(f"  [{n}/{total}] {msg}")


def parse_args():
    p = argparse.ArgumentParser(description="NewAPI 创建单个账号（自动编号），设置额度并生成不限额 API Key")
    p.add_argument("--amount", type=float, required=True, help="人民币金额（必填），用于计算额度 = 金额 × 73529")
    p.add_argument("--base-url", type=str, default=None, help="NewAPI 根地址（也可用 NEWAPI_BASE_URL）")
    p.add_argument("--admin-token", type=str, default=None, help="管理员 API Token（也可用 NEWAPI_ADMIN_TOKEN）")
    p.add_argument("--admin-user-id", type=str, default=None, help="管理员用户 ID（也可用 NEWAPI_ADMIN_USER_ID）")
    p.add_argument("--admin-username", type=str, default=None, help="管理员用户名（与 --admin-password 一起时代替 token）")
    p.add_argument("--admin-password", type=str, default=None, help="管理员密码（与 --admin-username 一起时先登录取 token）")
    args = p.parse_args()

    base_url = (args.base_url or os.environ.get("NEWAPI_BASE_URL", "")).rstrip("/")
    if not base_url:
        print("错误: 请设置 NEWAPI_BASE_URL 或 --base-url", file=sys.stderr)
        sys.exit(1)

    amount = args.amount
    if amount < 0:
        print("错误: 金额不能为负", file=sys.stderr)
        sys.exit(1)

    admin_token = args.admin_token or os.environ.get("NEWAPI_ADMIN_TOKEN")
    admin_user_id = args.admin_user_id or os.environ.get("NEWAPI_ADMIN_USER_ID")
    admin_username = args.admin_username or os.environ.get("NEWAPI_ADMIN_USERNAME")
    admin_password = args.admin_password or os.environ.get("NEWAPI_ADMIN_PASSWORD")

    if not admin_token or not admin_user_id:
        if admin_username and admin_password:
            admin_session, admin_user_id = admin_login(base_url, admin_username, admin_password)
            if admin_user_id is None:
                sys.exit(1)
            # 使用 Session（Cookie）鉴权，不传 token
            return {
                "base_url": base_url,
                "amount": amount,
                "admin_session": admin_session,
                "admin_token": None,
                "admin_user_id": str(admin_user_id),
            }
        else:
            print("错误: 请提供管理员鉴权：NEWAPI_ADMIN_TOKEN + NEWAPI_ADMIN_USER_ID，或 NEWAPI_ADMIN_USERNAME + NEWAPI_ADMIN_PASSWORD", file=sys.stderr)
            sys.exit(1)

    return {
        "base_url": base_url,
        "amount": amount,
        "admin_session": None,
        "admin_token": admin_token,
        "admin_user_id": str(admin_user_id),
    }


def admin_login(base_url: str, username: str, password: str):
    """管理员登录。若响应含 token 则返回 (None, token, user_id)；若仅含用户信息则用 Session 并返回 (session, None, user_id)。"""
    url = f"{base_url}/api/user/login"
    session = requests.Session()
    r = session.post(url, json={"username": username, "password": password}, timeout=30)
    if r.status_code != 200:
        print(f"登录失败 HTTP {r.status_code}: {r.text}", file=sys.stderr)
        return None, None
    data = r.json()
    if not data.get("success"):
        print(f"登录失败: {data.get('message', r.text)}", file=sys.stderr)
        return None, None
    inner = data.get("data") or {}
    # 兼容两种格式：1) data.data 为 { token, user: { id } }  2) data.data 直接为用户对象 { id, username, ... }
    user_id = None
    if isinstance(inner, dict):
        if "user" in inner and isinstance(inner["user"], dict):
            user_id = inner["user"].get("id")
        if user_id is None:
            user_id = inner.get("id")
    if user_id is None:
        print("登录响应中缺少用户 id（data.data.id 或 data.data.user.id）", file=sys.stderr)
        return None, None
    # 当前站点登录不返回 token，仅通过 Cookie 鉴权，返回带 Cookie 的 session
    return session, user_id


def admin_headers(admin_token: str, admin_user_id: str):
    return {
        "Authorization": f"Bearer {admin_token}",
        "New-Api-User": str(admin_user_id),
        "Content-Type": "application/json",
    }


def _admin_request(cfg, method: str, url: str, **kwargs):
    """统一发起管理接口请求：优先使用 Session（Cookie），否则使用 Bearer token。Session 模式下也需带 New-Api-User。"""
    user_id = cfg.get("admin_user_id")
    if cfg.get("admin_session") is not None:
        session = cfg["admin_session"]
        headers = kwargs.get("headers") or {}
        headers = dict(headers)
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("New-Api-User", str(user_id))
        kwargs["headers"] = headers
        return session.request(method, url, timeout=30, **kwargs)
    token = cfg.get("admin_token")
    if "headers" in kwargs:
        kwargs["headers"].update(admin_headers(token, user_id))
    else:
        kwargs["headers"] = admin_headers(token, user_id)
    return requests.request(method, url, timeout=30, **kwargs)


def search_users(cfg: dict, keyword: str, page: int = 1, page_size: int = SEARCH_PAGE_SIZE):
    """GET /api/user/search，返回 (items, total) 或 (None, 0) 表示失败。"""
    base_url = cfg["base_url"]
    url = f"{base_url}/api/user/search"
    params = {"keyword": keyword, "p": page, "page_size": page_size}
    r = _admin_request(cfg, "GET", url, params=params)
    if r.status_code != 200:
        print(f"搜索用户失败 HTTP {r.status_code}: {r.text}", file=sys.stderr)
        return None, 0
    data = r.json()
    if not data.get("success"):
        print(f"搜索用户失败: {data.get('message', r.text)}", file=sys.stderr)
        return None, 0
    inner = data.get("data") or {}
    items = inner.get("items") or []
    total = int(inner.get("total") or 0)
    return items, total


def get_all_users_with_prefix(cfg: dict, prefix: str):
    """拉取所有用户名以 prefix 开头的用户，返回 [(username, id), ...]。"""
    all_items = []
    page = 1
    while True:
        items, total = search_users(cfg, prefix, page=page, page_size=SEARCH_PAGE_SIZE)
        if items is None:
            return None
        all_items.extend(items)
        if len(all_items) >= total or len(items) < SEARCH_PAGE_SIZE:
            break
        page += 1
    return [(u.get("username"), u.get("id")) for u in all_items if u.get("username", "").startswith(prefix)]


def next_index(users_with_prefix):
    """从 (username, id) 列表中解析编号，返回下一个可用编号。"""
    pattern = re.compile(r"^" + re.escape(USERNAME_PREFIX) + r"(\d{3})$")
    indices = []
    for username, _ in users_with_prefix or []:
        m = pattern.match(username)
        if m:
            indices.append(int(m.group(1)))
    return max(indices, default=-1) + 1


def create_user(cfg: dict, username: str):
    """POST /api/user/ 创建用户，返回 True 成功。"""
    base_url = cfg["base_url"]
    url = f"{base_url}/api/user/"
    # 同时传 username / Username / name，兼容不同部署的字段名
    body = {
        "username": username,
        "Username": username,
        "name": username,
        "password": PASSWORD,
        "display_name": username,
        "DisplayName": username,
        "role": 1,
    }
    r = _admin_request(cfg, "POST", url, json=body)
    if r.status_code != 200:
        print(f"创建用户失败 HTTP {r.status_code}: {r.text}", file=sys.stderr)
        return False
    data = r.json()
    if not data.get("success"):
        print(f"创建用户失败: {data.get('message', r.text)}", file=sys.stderr)
        return False
    return True


def update_user_quota(cfg: dict, user_id: int, username: str, quota: int):
    """PUT /api/user/ 设置用户额度。同时传 username 避免服务端部分更新时把用户名置空触发唯一约束。"""
    base_url = cfg["base_url"]
    url = f"{base_url}/api/user/"
    body = {"id": user_id, "username": username, "quota": quota}
    r = _admin_request(cfg, "PUT", url, json=body)
    if r.status_code != 200:
        print(f"设置额度失败 HTTP {r.status_code}: {r.text}", file=sys.stderr)
        return False
    data = r.json()
    if not data.get("success"):
        print(f"设置额度失败: {data.get('message', r.text)}", file=sys.stderr)
        return False
    return True


def enable_user(cfg: dict, user_id: int):
    """POST /api/user/manage 启用用户（部分部署新建用户默认为禁用）。"""
    base_url = cfg["base_url"]
    url = f"{base_url}/api/user/manage"
    body = {"id": user_id, "action": "enable"}
    r = _admin_request(cfg, "POST", url, json=body)
    if r.status_code != 200:
        return False
    data = r.json()
    return data.get("success", False)


def user_login(base_url: str, username: str, password: str):
    """新用户登录。返回 (token_or_session, user_id)：若响应含 token 则为 (str, id)，若仅含用户信息则为 (Session, id)。"""
    url = f"{base_url}/api/user/login"
    session = requests.Session()
    r = session.post(url, json={"username": username, "password": password}, timeout=30)
    if r.status_code != 200:
        print(f"用户登录失败 HTTP {r.status_code}: {r.text}", file=sys.stderr)
        return None, None
    data = r.json()
    if not data.get("success"):
        print(f"用户登录失败: {data.get('message', r.text)}（若开启 2FA 或用户被禁用，请在后台调整）", file=sys.stderr)
        return None, None
    inner = data.get("data") or {}
    token = inner.get("token") if isinstance(inner, dict) else None
    user_id = None
    if isinstance(inner, dict):
        if inner.get("user") and isinstance(inner["user"], dict):
            user_id = inner["user"].get("id")
        if user_id is None:
            user_id = inner.get("id")
    if user_id is None:
        print("登录响应中缺少用户 id", file=sys.stderr)
        return None, None
    if token:
        return token, user_id
    return session, user_id


def create_token(base_url: str, user_cred, user_id, name: str = "default", unlimited_quota: bool = True):
    """POST /api/token/ 创建令牌。user_cred 为 token 字符串或已登录的 requests.Session。返回 (key, None) 或 (None, error_msg)。"""
    url = f"{base_url}/api/token/"
    body = {"name": name, "unlimited_quota": unlimited_quota, "expired_time": -1}
    if isinstance(user_cred, requests.Session):
        r = user_cred.post(
            url,
            headers={"Content-Type": "application/json", "New-Api-User": str(user_id)},
            json=body,
            timeout=30,
        )
    else:
        headers = {
            "Authorization": f"Bearer {user_cred}",
            "New-Api-User": str(user_id),
            "Content-Type": "application/json",
        }
        r = requests.post(url, headers=headers, json=body, timeout=30)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}: {r.text}"
    data = r.json()
    if os.environ.get("NEWAPI_DEBUG"):
        print("[DEBUG] POST /api/token/ 响应:", data, file=sys.stderr)
    if not data.get("success"):
        return None, data.get("message", r.text)
    # 按 NewAPI 文档，创建成功时响应 data 为 Token 对象，data.key 为明文（仅创建时返回一次）
    def is_plain_key(s):
        if not s or not isinstance(s, str):
            return False
        if "*" in s:
            return False
        return len(s) >= 10

    raw = data.get("data")
    # 优先使用 data.key（文档约定）
    if isinstance(raw, dict):
        key = raw.get("key")
        if is_plain_key(key):
            return key, None
        for k in ("token", "api_key", "value"):
            v = raw.get(k)
            if is_plain_key(v):
                return v, None
    if isinstance(raw, str) and is_plain_key(raw):
        return raw, None
    for k in ("key", "token", "api_key"):
        v = data.get(k)
        if is_plain_key(v):
            return v, None
    return None, None


def list_tokens(base_url: str, user_cred, user_id):
    """GET /api/token/ 获取令牌列表。user_cred 为 token 字符串或已登录的 Session。返回 [{"name","key"}, ...] 或 None。"""
    url = f"{base_url}/api/token/"
    params = {"p": 1, "size": 50}
    if isinstance(user_cred, requests.Session):
        r = user_cred.get(
            url,
            headers={"Content-Type": "application/json", "New-Api-User": str(user_id)},
            params=params,
            timeout=30,
        )
    else:
        headers = {"Authorization": f"Bearer {user_cred}", "New-Api-User": str(user_id), "Content-Type": "application/json"}
        r = requests.get(url, headers=headers, params=params, timeout=30)
    if r.status_code != 200:
        print(f"获取令牌列表失败 HTTP {r.status_code}: {r.text}", file=sys.stderr)
        return None
    data = r.json()
    if not data.get("success"):
        return None
    inner = data.get("data") or {}
    items = inner.get("items") or []
    return [{"id": t.get("id"), "name": t.get("name"), "key": t.get("key")} for t in items]


def get_token_key(base_url: str, user_cred, user_id, token_id) -> str:
    """POST /api/token/{id}/key 获取令牌明文 key（部分部署仅此接口返回明文）。返回时若无 sk- 前缀则拼上。"""
    url = f"{base_url}/api/token/{token_id}/key"
    if isinstance(user_cred, requests.Session):
        r = user_cred.post(
            url,
            headers={"Content-Type": "application/json", "New-Api-User": str(user_id)},
            timeout=30,
        )
    else:
        headers = {"Authorization": f"Bearer {user_cred}", "New-Api-User": str(user_id), "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, timeout=30)
    if r.status_code != 200:
        return ""
    data = r.json()
    if not data.get("success"):
        return ""
    key = (data.get("data") or {}).get("key") if isinstance(data.get("data"), dict) else None
    if not key or not isinstance(key, str) or "*" in key:
        return ""
    if not key.startswith("sk-"):
        key = "sk-" + key
    return key


def run(cfg):
    base_url = cfg["base_url"]
    amount = cfg["amount"]
    quota = int(amount * QUOTA_MULTIPLIER)
    total_steps = 7

    # 1) 查已有用户，确定下一个编号
    _step(1, total_steps, "查询已有用户，确定编号…")
    users = get_all_users_with_prefix(cfg, USERNAME_PREFIX)
    if users is None:
        return 1
    idx = next_index(users)
    username = f"{USERNAME_PREFIX}{idx:03d}"
    _step(1, total_steps, f"下一个编号: {idx:03d} → {username}")

    # 2) 创建用户
    _step(2, total_steps, "创建用户…")
    if not create_user(cfg, username):
        return 1

    # 3) 查新用户 id
    _step(3, total_steps, "获取新用户 ID…")
    items, _ = search_users(cfg, username, page_size=10)
    if not items:
        print("创建成功但搜索不到新用户，请稍后手动在后台设置额度并创建 Token", file=sys.stderr)
        print(f"用户名: {username}", file=sys.stderr)
        return 1
    new_user_id = None
    for u in items:
        if u.get("username") == username:
            new_user_id = u.get("id")
            break
    if new_user_id is None:
        print("未找到新用户 id", file=sys.stderr)
        return 1

    # 4) 设置额度（带 username 避免 PUT 时服务端误触唯一约束）
    _step(4, total_steps, f"设置额度: {quota} …")
    if not update_user_quota(cfg, new_user_id, username, quota):
        return 1

    # 5) 启用用户（部分部署新建用户默认为禁用，需先 enable 才能登录）
    _step(5, total_steps, "启用用户…")
    enable_user(cfg, new_user_id)

    # 6) 新用户登录（可能返回 token 或 Session）
    _step(6, total_steps, "新用户登录…")
    user_cred, uid = user_login(base_url, username, PASSWORD)
    if user_cred is None:
        return 1

    # 7) 创建不限额 Token（创建接口返回的 data 为明文 key）
    _step(7, total_steps, "创建 API Token（不限额）…")
    token_name = "default"
    api_key, err = create_token(base_url, user_cred, uid, name=token_name, unlimited_quota=True)
    if err:
        print(f"创建 Token 失败: {err}", file=sys.stderr)
        return 1
    if not api_key:
        tokens = list_tokens(base_url, user_cred, uid)
        if tokens:
            for t in tokens:
                if t.get("name") == token_name:
                    tid = t.get("id")
                    if tid is not None:
                        api_key = get_token_key(base_url, user_cred, uid, tid)
                    if not api_key:
                        api_key = t.get("key")
                    break
            if not api_key and tokens:
                tid = tokens[0].get("id")
                api_key = get_token_key(base_url, user_cred, uid, tid) if tid is not None else None
                if not api_key:
                    api_key = tokens[0].get("key")
        if not api_key:
            print("创建 Token 成功但无法获取 key，请在后台查看", file=sys.stderr)
            return 1

    # 结果输出（API_KEY 明文展示，便于复制）
    print()
    print("  " + "─" * 52)
    print("  创建成功")
    print("  " + "─" * 52)
    print(f"  用户名   {username}")
    print(f"  API_KEY  {api_key}")
    if "*" in (api_key or ""):
        print("  (当前为脱敏显示，完整 Key 请到后台「令牌管理」中查看或复制)")
    print(f"  额度     {quota}")
    print("  " + "─" * 52)
    return 0


def main():
    cfg = parse_args()
    sys.exit(run(cfg))


if __name__ == "__main__":
    main()
