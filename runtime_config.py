"""Runtime API-key configuration shared by the outline and image services.

The optional web "settings" page writes to a local ``config.json``; those values
take priority over environment variables (which remain the fallback). Only the
whitelisted fields are persisted, values never leave the machine, and the API
never returns a plaintext key.
"""
import json
import os
from contextvars import ContextVar

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_BASE_DIR, 'config.json')

# 网页「设置」页可写的密钥字段
EDITABLE_KEYS = ('DEEPSEEK_API_KEY', 'VISION_API_KEY')

# 每请求的浏览器端密钥覆盖（各人各自），用 ContextVar 与并发请求隔离。
_request_keys = ContextVar('request_api_keys', default=None)


def set_request_keys(ppt_key='', vision_key=''):
    """为当前请求注入浏览器端密钥，返回重置令牌。"""
    return _request_keys.set({
        'DEEPSEEK_API_KEY': (ppt_key or '').strip(),
        'VISION_API_KEY': (vision_key or '').strip(),
    })


def reset_request_keys(token):
    _request_keys.reset(token)


def _env_fallback():
    return {
        'DEEPSEEK_API_KEY': os.environ.get('DEEPSEEK_API_KEY', ''),
        'VISION_API_KEY': os.environ.get('VISION_API_KEY', ''),
    }


def _read_file():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def get_config():
    """网页配置（非空）优先，环境变量兜底。"""
    cfg = _env_fallback()
    saved = _read_file()
    for key in EDITABLE_KEYS:
        value = saved.get(key)
        if isinstance(value, str) and value.strip():
            cfg[key] = value.strip()
    return cfg


def get(key, default=''):
    """浏览器端每请求密钥优先，其次 config.json，再次环境变量。"""
    override = _request_keys.get() or {}
    value = override.get(key)
    if value:
        return value
    return get_config().get(key, default)


def save_config(data):
    """只保存白名单字段，返回清洗后的结果。

    仅接受对象与字符串值：非对象（数组/字符串等）与非字符串值一律置空，
    避免 `(data or {}).get` 抛 AttributeError，或把 None 写成字符串 "None"。
    """
    if not isinstance(data, dict):
        data = {}
    cleaned = {}
    for key in EDITABLE_KEYS:
        value = data.get(key)
        cleaned[key] = value.strip() if isinstance(value, str) else ''
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    return cleaned


def mask(value):
    """回显掩码，避免把明文 key 交给前端。"""
    value = value or ''
    return f'{value[:3]}****{value[-4:]}' if len(value) > 8 else ('****' if value else '')
