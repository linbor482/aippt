"""Flask/Vercel entry point and compatibility exports for local scripts."""
import hmac
import os

from flask import Flask, Response, request
from flask_cors import CORS
from settings import ALLOWED_ORIGINS, BASE_DIR
from json_api import register_json_api
from generation_api import register_generation_api

# Keep the local rendering/review scripts' imports stable.
from outline_service import generate_default_content, outline_prompt
from pptx_export import create_presentation, presentation_events, ImageSearchFailed

app = Flask(__name__, template_folder=BASE_DIR)
CORS(app, origins=ALLOWED_ORIGINS)
register_json_api(app)
register_generation_api(app)


@app.before_request
def require_access_password():
    """局域网共享时的访问口令：设置 ACCESS_PASSWORD 即启用 HTTP Basic Auth。

    未设置则不鉴权（纯本地单机使用不受影响）。用户名默认 admin，可用
    ACCESS_USERNAME 覆盖。口令走浏览器原生弹窗，验证通过后浏览器自动随请求带上。
    """
    password = os.environ.get('ACCESS_PASSWORD', '')
    if not password:
        return None
    username = os.environ.get('ACCESS_USERNAME', 'admin')
    auth = request.authorization
    if auth and hmac.compare_digest(auth.username or '', username) \
            and hmac.compare_digest(auth.password or '', password):
        return None
    return Response('需要访问口令', 401, {'WWW-Authenticate': 'Basic realm="AIPPT"'})

if __name__ == '__main__':
    # 本地运行：默认只监听本机、关闭 debug（Werkzeug 调试器可执行任意代码）。
    # 需要局域网共享时用环境变量 HOST=0.0.0.0 覆盖；用 waitress 生产级服务器承载。
    from waitress import serve
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '5000'))
    threads = int(os.environ.get('THREADS', '8'))
    # 绑定非本机地址即意味着局域网/公网可访问，此时必须设置访问口令，否则任何能
    # 连上该地址的人都能使用服务并读写本机密钥配置。
    if host not in ('127.0.0.1', 'localhost', '::1') and not os.environ.get('ACCESS_PASSWORD', ''):
        print(f'错误：HOST={host} 会暴露给网络，必须设置 ACCESS_PASSWORD 才能启动；'
              f'或改回 HOST=127.0.0.1 仅供本机使用。')
        raise SystemExit(1)
    print(f' * Serving on http://{host}:{port} (threads={threads})')
    serve(app, host=host, port=port, threads=threads)
