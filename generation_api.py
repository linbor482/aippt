"""NDJSON transport, request lifetime and stream errors."""
import json
import time

from flask import Response, jsonify, request, stream_with_context
import outline_service
import pptx_export
import runtime_config
from generation_runtime import deadline
from generation_service import complete_slides, outline_events, validate_generation_options, validate_outline, validate_outline_request


def register_generation_api(app):
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

    @app.after_request
    def cache_policy(response):
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.post('/api/outline/stream')
    @app.post('/api/generate/stream')
    def generate_stream():
        data = request.get_json(silent=True)
        is_outline = request.path == '/api/outline/stream'
        ppt_key = request.headers.get('X-DeepSeek-Key', '')
        vision_key = request.headers.get('X-Vision-Key', '')
        try:
            if not isinstance(data, dict):
                raise ValueError('请求必须为 JSON 对象')
            if is_outline:
                request_data = validate_outline_request(data)
                events = outline_events(outline_service, request_data)
            else:
                outline = validate_outline(data.get('outline'))
                template, image_mode, use_vision = validate_generation_options(data)
                events = pptx_export.presentation_events(outline, template, image_mode, use_vision)
        except (ValueError, TypeError) as error:
            return jsonify(success=False, error=str(error)), 400

        def stream():
            token = deadline.set(time.monotonic() + 240)
            key_token = runtime_config.set_request_keys(ppt_key, vision_key)
            sent_bytes = 0
            try:
                for event in events:
                    line = json.dumps(event, ensure_ascii=False) + '\n'
                    sent_bytes += len(line.encode('utf-8'))
                    if sent_bytes > 4_200_000:
                        raise ValueError('文稿与图片总大小超出当前下载限制，请减少配图或拆分文稿后重试。')
                    yield line
            except pptx_export.ImageSearchFailed as error:
                yield json.dumps({'type': 'error', 'success': False, 'code': 'IMAGE_SEARCH_FAILED',
                                  'error': str(error), 'sourceIndex': error.source_index,
                                  'outline': data['outline']}, ensure_ascii=False) + '\n'
            except ValueError as error:
                yield json.dumps({'type': 'error', 'success': False, 'error': str(error)}, ensure_ascii=False) + '\n'
            except Exception:
                yield json.dumps({'type': 'error', 'success': False,
                                  'error': '生成服务暂时不可用，请稍后重试；大纲内容已保留。'}, ensure_ascii=False) + '\n'
            finally:
                events.close()
                deadline.reset(token)
                runtime_config.reset_request_keys(key_token)
        return Response(stream_with_context(stream()), content_type='application/x-ndjson; charset=utf-8',
                        headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
