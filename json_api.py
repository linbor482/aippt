"""Legacy JSON endpoints with shared validation and generation services."""
import base64
import logging

from flask import jsonify, render_template, request
import outline_service
import pptx_export
import runtime_config
import auth as lan_auth
from generation_service import build_outline, validate_generation_options, validate_outline, validate_outline_request
from presentation_design import build_scenes

logger = logging.getLogger(__name__)


def _masked_config(cfg):
    return {
        'pptKey': runtime_config.mask(cfg.get('DEEPSEEK_API_KEY', '')),
        'pptKeySet': bool(cfg.get('DEEPSEEK_API_KEY', '')),
        'visionKey': runtime_config.mask(cfg.get('VISION_API_KEY', '')),
        'visionKeySet': bool(cfg.get('VISION_API_KEY', '')),
    }


def register_json_api(app):
    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/api/auth/status')
    def api_auth_status():
        return jsonify(success=True, setup=lan_auth.state(), lan=lan_auth.is_lan_mode())

    @app.post('/api/auth/setup')
    def api_auth_setup():
        data = request.get_json(silent=True) or {}
        try:
            lan_auth.setup(data.get('username', ''), data.get('password', ''))
        except ValueError as error:
            return jsonify(success=False, error=str(error)), 400
        return jsonify(success=True)

    @app.post('/api/auth/skip')
    def api_auth_skip():
        lan_auth.skip()
        return jsonify(success=True)

    @app.get('/api/config')
    def api_get_config():
        return jsonify(success=True, config=_masked_config(runtime_config.get_config()))

    @app.post('/api/config')
    def api_set_config():
        saved = runtime_config.save_config(request.get_json(silent=True) or {})
        return jsonify(success=True, config=_masked_config(saved))

    @app.post('/api/preview')
    def preview_design():
        data = request.get_json(silent=True)
        try:
            if not isinstance(data, dict):
                raise ValueError('请求必须为 JSON 对象')
            outline = validate_outline(data.get('outline'))
            template, image_mode, _ = validate_generation_options(data, default_template='luxury')
        except (TypeError, ValueError) as error:
            return jsonify(success=False, error=str(error)), 400
        return jsonify(success=True, scenes=build_scenes(outline, template, image_mode))

    @app.post('/api/outline')
    def preview_outline():
        try:
            data = validate_outline_request(request.get_json(silent=True), default_pages=5, clamp_pages=True)
            key_token = runtime_config.set_request_keys(
                request.headers.get('X-DeepSeek-Key', ''), request.headers.get('X-Vision-Key', ''))
            try:
                outline = build_outline(outline_service, data['topic'], data['pages'], data['language'], data['useAi'])
            finally:
                runtime_config.reset_request_keys(key_token)
            return jsonify(success=True, outline=outline)
        except (TypeError, ValueError) as error:
            return jsonify(success=False, error=str(error)), 400
        except Exception:
            logger.exception("大纲生成失败")
            return jsonify(success=False, error='服务暂时不可用，请稍后重试。'), 500

    @app.post('/api/generate')
    def generate_ppt():
        try:
            data = request.get_json(silent=True)
            options = validate_outline_request(data, default_pages=5, require_topic=False, clamp_pages=True)
            template, image_mode, use_vision = validate_generation_options(data, default_image_mode='blank')
            key_token = runtime_config.set_request_keys(
                request.headers.get('X-DeepSeek-Key', ''), request.headers.get('X-Vision-Key', ''))
            try:
                outline = build_outline(outline_service, options['topic'], options['pages'], options['language'],
                                        options['useAi'], options['outline'])
                filename, raw = pptx_export.create_presentation(outline, template, image_mode, use_vision)
            finally:
                runtime_config.reset_request_keys(key_token)
            return jsonify(success=True, filename=filename, file=base64.b64encode(raw).decode('ascii'), outline=outline)
        except pptx_export.ImageSearchFailed as error:
            return jsonify(success=False, code='IMAGE_SEARCH_FAILED', error=str(error),
                           sourceIndex=error.source_index, outline=outline), 409
        except (TypeError, ValueError) as error:
            return jsonify(success=False, error=str(error)), 400
        except Exception:
            logger.exception("PPT 生成失败")
            return jsonify(success=False, error='生成服务暂时不可用，请稍后重试。'), 500
