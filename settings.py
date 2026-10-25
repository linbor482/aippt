"""Process configuration loaded from the project directory."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, '.env'))
except ImportError:
    pass

DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
VISION_API_URL = os.environ.get('VISION_API_URL', 'https://api.siliconflow.cn/v1/chat/completions')
VISION_MODEL = os.environ.get('VISION_MODEL', 'Qwen/Qwen2.5-VL-7B-Instruct')
PROXY_URL = os.environ.get('PROXY_URL', '')
ALLOWED_ORIGINS = [origin.strip() for origin in os.environ.get(
    'ALLOWED_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000').split(',') if origin.strip()]
