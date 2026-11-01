"""Shared request validation and outline generation for JSON and NDJSON APIs."""
import json
import re
import time

import requests
import runtime_config
import history


SUPPORTED_TEMPLATES = {'default', 'modern', 'creative', 'luxury'}
SUPPORTED_IMAGE_MODES = {'none', 'blank', 'ai', 'real'}
DEDUP_THRESHOLD = 0.65
DEDUP_RETRIES = 2


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

        def generate_once(extra=''):
            generated = backend.generate_content_with_ai(topic, pages, language, extra)
            if not generated:
                raise ValueError('AI 大纲生成失败，请稍后重试。')
            return validate_outline(generated)

        outline, _, _ = generate_outline_with_dedup(topic, pages, language, generate_once)
        return outline
    return validate_outline(backend.generate_default_content(topic, pages, language))


def enforce_page_count(outline, pages):
    """把大纲页数收敛到恰好 pages 页：偏多裁中间内容页，偏少拆分最长内容页补齐。

    拆分只作用于 content 页（要点数组），插入在原页之后、结束页之前；
    没有可拆的内容页时按当前页数返回，不编造内容。
    """
    slides = outline['slides']
    if len(slides) > pages:
        head = slides[:1]
        tail = slides[-1:] if pages > 1 else []
        keep_middle = max(0, pages - len(head) - len(tail))
        outline['slides'] = head + slides[1:-1][:keep_middle] + tail
        return outline
    while len(slides) < pages:
        split = next((s for s in slides
                      if s.get('type') == 'content'
                      and isinstance(s.get('content'), list) and len(s['content']) >= 2), None)
        if split is None:
            break
        half = len(split['content']) // 2
        cont = dict(split)
        cont['content'] = split['content'][half:]
        cont['title'] = f"{split.get('title') or ''}（续）"
        split['content'] = split['content'][:half]
        slides.insert(slides.index(split) + 1, cont)
    return outline


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


def _dedup_instruction(entries, limit=6):
    examples = [e.get('text') or e.get('title', '') for e in entries if (e.get('text') or e.get('title', ''))]
    if not examples:
        return ''
    lines = '\n'.join(f'- {t[:120]}' for t in examples[:limit])
    return ('\n\n【去重要求】以下是近期已生成的大纲内容，本次生成必须避免与其重复或高度相似，'
            '请更换表述、结构与切入角度，保证重复率低于 65%。\n' + lines)


def _stream_ai_outline(backend, topic, pages, language, extra=''):
    """流式请求一次 AI 大纲，返回完整大纲 dict；失败抛 ValueError。"""
    ppt_key = runtime_config.get('DEEPSEEK_API_KEY')
    payload = {'model': 'deepseek-chat', 'stream': True,
               'messages': [{'role': 'user', 'content': backend.outline_prompt(topic, pages, language) + extra}],
               'temperature': 0.7, 'max_tokens': 8000}
    started = time.monotonic()
    text, finished = '', False
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
        if not finished:
            raise ValueError('AI 输出未完成，请减少页数或内容后重试。')
    return validate_outline(json.loads(backend._extract_json_block(text)))


def generate_outline_with_dedup(topic, pages, language, generate_once):
    """生成大纲并查重：超阈值自动换写法重试；返回 (outline, similarity, retries)。

    generate_once(extra) 负责单次生成并返回已校验的大纲（不含页数收敛）。
    """
    instruction = _dedup_instruction(history.load())
    outline = generate_once(instruction)
    if len(outline['slides']) > 30:
        raise ValueError('AI 返回超过 30 页，请调整需求后重试。')
    outline = enforce_page_count(outline, pages)
    similarity = history.max_similarity(outline)
    retries = 0
    while similarity > DEDUP_THRESHOLD and retries < DEDUP_RETRIES:
        retries += 1
        outline = generate_once(instruction)
        if len(outline['slides']) > 30:
            raise ValueError('AI 返回超过 30 页，请调整需求后重试。')
        outline = enforce_page_count(outline, pages)
        similarity = history.max_similarity(outline)
    history.append(outline)
    return outline, similarity, retries


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
    yield {'type': 'stage', 'message': 'AI 正在撰写大纲，完成后将一次性显示全部页面'}

    def generate_once(extra=''):
        return _stream_ai_outline(backend, topic, pages, language, extra)

    outline, similarity, retries = generate_outline_with_dedup(topic, pages, language, generate_once)
    for index, slide in enumerate(outline['slides']):
        yield {'type': 'outline_slide', 'index': index, 'slide': slide}
    yield {'type': 'complete', 'success': True, 'outline': outline, 'mode': 'ai',
           'dedup': {'similarity': round(similarity, 3),
                     'warn': similarity > DEDUP_THRESHOLD,
                     'rewritten': retries}}
