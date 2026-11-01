"""Flask/Vercel entry point and compatibility exports for local scripts."""
import hmac
import os

import auth as lan_auth
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
    """局域网共享鉴权：仅当服务绑定非本机地址且已设置账密时才要求登录。

    环境变量 ACCESS_PASSWORD 仍作为显式覆盖（公网/Vercel 部署用）；否则走
    auth.json 的首次网页设置账密（只存哈希）。本机 127.0.0.1 部署始终免登录。
    """
    password = os.environ.get('ACCESS_PASSWORD', '')
    if password:
        username = os.environ.get('ACCESS_USERNAME', 'admin')
        creds = request.authorization
        if creds and hmac.compare_digest(creds.username or '', username) \
                and hmac.compare_digest(creds.password or '', password):
            return None
        return Response('需要访问口令', 401, {'WWW-Authenticate': 'Basic realm="AIPPT"'})
    if lan_auth.is_lan_mode() and lan_auth.state() == 'set':
        creds = request.authorization
        if creds and lan_auth.verify(creds.username or '', creds.password or ''):
            return None
        return Response('需要访问账密', 401, {'WWW-Authenticate': 'Basic realm="AIPPT"'})
    return None

if __name__ == '__main__':
    # 本地运行：默认只监听本机、关闭 debug（Werkzeug 调试器可执行任意代码）。
    # 需要局域网共享时用环境变量 HOST=0.0.0.0 覆盖；用 waitress 生产级服务器承载。
    from waitress import serve
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '5000'))
    threads = int(os.environ.get('THREADS', '8'))
    # 绑定非本机地址即意味着局域网/公网可访问；未设账密时给出提示（首次打开页面
    # 会引导设置），而不再直接拒绝启动。
    if lan_auth.is_lan_mode() and not os.environ.get('ACCESS_PASSWORD', '') \
            and lan_auth.state() != 'set':
        print(f'提示：HOST={host} 已暴露到局域网。首次打开页面时会引导设置访问账密；'
              f'也可设置环境变量 ACCESS_PASSWORD 显式指定口令。')
    print(f' * Serving on http://{host}:{port} (threads={threads})')
    serve(app, host=host, port=port, threads=threads)
