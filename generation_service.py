"""Shared request validation and outline generation for JSON and NDJSON APIs."""
import json
import re
import time

import requests
import runtime_config


SUPPORTED_TEMPLATES = {'default', 'modern', 'creative', 'luxury'}
SUPPORTED_IMAGE_MODES = {'none', 'blank', 'ai', 'real'}


def validate_outline(outline):
    if not isinstance(outline, dict) or not isinstance(outline.get('slides'), list):
        raise ValueError('大纲必须包含 slides 数组')
    if not 1 <= len(outline['slides']) <= 100:
        raise ValueError('大纲应包含 1–100 页')
    if not isinstance(outline.get('title', ''), str):
        raise ValueError('大纲标题必须为文字')
    for slide in outline['slides']:
        if not isinstance(slide, dict) or slide.get('type') not in ('cover', 'content', 'final'):
            raise ValueError('页面类型须为 cover / content / final')
        if not isinstance(slide.get('title', ''), str):
            raise ValueError('页面标题必须为文字')
        content = slide.get('content', [] if slide['type'] == 'content' else '')
        if slide['type'] == 'content':
            if not isinstance(content, list) or not all(isinstance(item, str) for item in content):
                raise ValueError('内容页要点必须是文字数组')
        elif not isinstance(content, str):
            raise ValueError('封面和结束页内容必须为文字')
    return outline


def validate_outline_request(data, default_pages=8, require_topic=True, clamp_pages=False):
    if not isinstance(data, dict):
        raise ValueError('请求必须为 JSON 对象')
    topic = data.get('topic', '')
    if not isinstance(topic, str) or (require_topic and not topic.strip()) or len(topic.strip()) > 200:
        raise ValueError('请输入 1–200 字的主题与创作需求')
    if not isinstance(topic, str):
        topic = ''
    try:
        pages = int(data.get('pages', default_pages))
    except (TypeError, ValueError) as error:
        raise ValueError('页数须为 1–30 之间的整数') from error
    if clamp_pages:
        pages = max(1, min(30, pages))
    elif not 1 <= pages <= 30:
        raise ValueError('页数须在 1–30 之间')
    language = data.get('language', '中文')
    if language not in ('中文', 'English'):
        raise ValueError('请选择支持的语言')
    return {
        'topic': topic.strip(),
        'pages': pages,
        'language': language,
        'useAi': bool(data.get('useAi', False)),
        'outline': data.get('outline'),
    }


def build_outline(backend, topic, pages, language='中文', use_ai=False, outline=None):
    """Use the same validation and fallback rules for synchronous and streamed requests."""
    if outline and isinstance(outline, dict) and outline.get('slides'):
        return validate_outline(outline)
    if use_ai:
        if not runtime_config.get('DEEPSEEK_API_KEY'):
            raise ValueError('尚未配置 AI 服务密钥，请配置后重试或关闭 AI。')
        generated = backend.generate_content_with_ai(topic, pages, language)
        if not generated:
            raise ValueError('AI 大纲生成失败，请稍后重试。')
        return validate_outline(generated)
    return validate_outline(backend.generate_default_content(topic, pages, language))


def validate_generation_options(data, default_template='default', default_image_mode='none'):
    template = data.get('template', default_template)
    image_mode = data.get('imageMode', default_image_mode)
    if template not in SUPPORTED_TEMPLATES:
        raise ValueError('未知模板')
    if image_mode not in SUPPORTED_IMAGE_MODES:
        raise ValueError('未知图片方式')
    return template, image_mode, bool(data.get('useVision'))


def complete_slides(text):
    """Decode only complete slide objects, including strings with escaped braces."""
    match = re.search(r'"slides"\s*:\s*\[', text)
    if not match:
        return []
    position = match.end()
    slides = []
    decoder = json.JSONDecoder()
    while position < len(text):
        while position < len(text) and text[position] in ' \r\n\t,':
            position += 1
        try:
            slide, end = decoder.raw_decode(text, position)
        except ValueError:
            break
        if not isinstance(slide, dict):
            break
        slides.append(slide)
        position = end
    return slides


def outline_events(backend, data):
    topic = data['topic'].strip()
    pages = int(data.get('pages', 8))
    language = data.get('language', '中文')
    yield {'type': 'stage', 'message': '已接收创作需求，正在规划页面结构'}
    if not data.get('useAi', False):
        outline = build_outline(backend, topic, pages, language)
        yield {'type': 'stage', 'message': '未启用 AI：生成可编辑占位大纲，尚未应用内容约束'}
        for index, slide in enumerate(outline['slides']):
            yield {'type': 'outline_slide', 'index': index, 'slide': slide}
        yield {'type': 'complete', 'success': True, 'outline': outline, 'mode': 'template'}
        return
    ppt_key = runtime_config.get('DEEPSEEK_API_KEY')
    if not ppt_key:
        raise ValueError('尚未配置 AI 服务密钥，请在服务端配置后重试，或关闭 AI 使用占位大纲。')
    yield {'type': 'stage', 'message': 'AI 正在撰写大纲，完成的页面将依次显示'}
    payload = {'model': 'deepseek-chat', 'stream': True,
               'messages': [{'role': 'user', 'content': backend.outline_prompt(topic, pages, language)}],
               'temperature': 0.7, 'max_tokens': 8000}
    started = time.monotonic()
    text, emitted, finished = '', 0, False
    with requests.post(backend.DEEPSEEK_API_URL,
                       headers={'Authorization': f'Bearer {ppt_key}'},
                       json=payload, stream=True, timeout=(10, 45)) as upstream:
        upstream.raise_for_status()
        upstream.encoding = 'utf-8'
        for line in upstream.iter_lines(decode_unicode=True, chunk_size=1):
            if time.monotonic() - started > 240:
                raise ValueError('AI 生成超时，请减少页数后重试。')
            if not line or not line.startswith('data:'):
                continue
            body = line[5:].strip()
            if body == '[DONE]':
                break
            chunk = json.loads(body)
            if chunk.get('error'):
                raise ValueError('AI 服务未能完成大纲，请稍后重试。')
            for choice in chunk.get('choices', []):
                if choice.get('finish_reason') == 'stop':
                    finished = True
                text += choice.get('delta', {}).get('content') or ''
            if len(text) > 250000:
                raise ValueError('大纲内容过长，请精简需求。')
            slides = complete_slides(text)
            for index in range(emitted, len(slides)):
                yield {'type': 'outline_slide', 'index': index, 'slide': slides[index]}
            emitted = len(slides)
        if not finished:
            raise ValueError('AI 输出未完成，请减少页数或内容后重试。')
    outline = validate_outline(json.loads(backend._extract_json_block(text)))
    if len(outline['slides']) > 30:
        raise ValueError('AI 返回超过 30 页，请调整需求后重试。')
    # 收紧到用户设定页数：多出来的裁掉中间内容页，保留封面与结束页
    if len(outline['slides']) > pages:
        head = outline['slides'][:1]
        tail = outline['slides'][-1:] if pages > 1 else []
        keep_middle = max(0, pages - len(head) - len(tail))
        outline['slides'] = head + outline['slides'][1:-1][:keep_middle] + tail
    yield {'type': 'complete', 'success': True, 'outline': outline, 'mode': 'ai'}
