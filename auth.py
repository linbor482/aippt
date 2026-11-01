"""局域网访问鉴权：账密首次由用户在网页设置，存本地 auth.json。

仅当服务绑定非本机地址（is_lan_mode）且已设置账密（state == 'set'）时才要求登录；
本机 127.0.0.1 部署始终免登录。环境变量 ACCESS_PASSWORD 仍作为公网/Vercel 部署的
显式覆盖，由 app.py 优先处理。密码只存 pbkdf2 哈希，不落明文。
"""
import hashlib
import hmac
import json
import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_PATH = os.path.join(BASE_DIR, 'auth.json')

LOCAL_HOSTS = ('127.0.0.1', 'localhost', '::1')


def is_lan_mode():
    """服务是否绑定到非本机地址（局域网/公网可访问）。"""
    return os.environ.get('HOST', '127.0.0.1').strip() not in LOCAL_HOSTS


def _read():
    try:
        with open(AUTH_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def state():
    """返回 'unset' | 'set' | 'skipped'。"""
    data = _read()
    if not data:
        return 'unset'
    if data.get('state') == 'skipped':
        return 'skipped'
    if data.get('state') == 'set' and data.get('password_hash') and data.get('salt'):
        return 'set'
    return 'unset'


def verify(username, password):
    """校验账密，恒定时间比较。"""
    data = _read()
    if data.get('state') != 'set':
        return False
    if not hmac.compare_digest(str(data.get('username', '')), str(username)):
        return False
    salt = data.get('salt', '')
    expected = data.get('password_hash', '')
    if not salt or not expected:
        return False
    candidate = hashlib.pbkdf2_hmac(
        'sha256', str(password).encode('utf-8'), str(salt).encode('utf-8'), 100_000).hex()
    return hmac.compare_digest(candidate, expected)


def setup(username, password):
    """保存账密（只存哈希），返回 None；参数不合法时抛 ValueError。"""
    username = (username or '').strip()
    password = password or ''
    if not username or len(username) > 50:
        raise ValueError('用户名须为 1–50 个字符')
    if len(password) < 6:
        raise ValueError('密码至少 6 位')
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt.encode('utf-8'), 100_000).hex()
    with open(AUTH_PATH, 'w', encoding='utf-8') as f:
        json.dump({'state': 'set', 'username': username, 'salt': salt, 'password_hash': password_hash},
                  f, ensure_ascii=False, indent=2)


def skip():
    """标记用户明确跳过鉴权，下次不再弹设置提示。"""
    with open(AUTH_PATH, 'w', encoding='utf-8') as f:
        json.dump({'state': 'skipped'}, f, ensure_ascii=False, indent=2)
