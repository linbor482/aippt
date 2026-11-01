"""Image providers, ranking and optional visual matching."""
import base64
import html
import io
import json
import logging
import re
from urllib.parse import quote

import requests
import runtime_config
from generation_runtime import check_budget, network_timeout
from outline_service import _extract_json_block
from settings import DEEPSEEK_API_URL, PROXY_URL, VISION_API_URL, VISION_MODEL
from similarity import text_sim as _text_sim

logger = logging.getLogger(__name__)


def _proxies():
    """需要走代理的请求统一从这里取；未配置时返回 None（沿用系统环境变量或直连）"""
    if not PROXY_URL:
        return None
    return {'http': PROXY_URL, 'https': PROXY_URL}

USER_AGENT = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
}

# 中文常见停用词与泛化标题（用于无 AI 时的本地关键词兜底）
_STOPWORDS = set(
    '的 了 和 与 及 或 在 是 有 为 对 就 都 而 也 并 这 那 这些 那些 这个 那个 '
    '一个 我们 如何 什么 为什么 怎样 以及 通过 进行 可以 需要 主要 一些 其中'.split()
)
_GENERIC_TITLES = {'概述', '介绍', '简介', '背景', '总结', '结论', '谢谢', '感谢', '谢谢观看', '欢迎交流'}



def _download_image_bytes(url, timeout=25):
    """下载图片字节，失败返回 None（对 content-type 宽松，交给后续 PIL 校验）"""
    try:
        with requests.get(url, timeout=network_timeout(timeout), headers=USER_AGENT, stream=True) as r:
            if r.status_code != 200:
                return None
            ct = r.headers.get('content-type', '')
            if ct and not ct.startswith('image') and 'octet-stream' not in ct:
                return None
            image_bytes = bytearray()
            for chunk in r.iter_content(65536):
                check_budget()
                image_bytes.extend(chunk)
                if len(image_bytes) > 8 * 1024 * 1024:
                    return None
            return bytes(image_bytes) or None
    except Exception as e:
        logger.warning("图片下载失败: %s -> %s", url, e)
    return None


def _validate_image(img, min_side=200):
    """校验是真实图片且尺寸足够大，过滤掉图标、缩略图、占位小图"""
    if not img:
        return False
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(img))
        im.verify()  # 校验文件完整性
        im = Image.open(io.BytesIO(img))  # verify 后需重新 open 才能取尺寸
        w, h = im.size
        return min(w, h) >= min_side
    except Exception:
        return False


def _ai_image(keyword):
    """AI 渲染图片：调用免费 pollinations.ai 按关键词生成情景图片"""
    url = f"https://image.pollinations.ai/prompt/{quote(keyword)}?width=768&height=576&nologo=true"
    return _download_image_bytes(url, timeout=90)


def _search_bing_images(keyword, limit=15):
    """必应图片搜索（cn.bing.com 优先，失败回退 www.bing.com），返回 [{url, title, w, h}]"""
    for host in ('https://cn.bing.com', 'https://www.bing.com'):
        results = _bing_images_from(host, keyword, limit)
        if results:
            return results
    logger.warning("必应图片搜索无结果: %s", keyword)
    return []


def _bing_images_from(host, keyword, limit):
    try:
        r = requests.get(
            f'{host}/images/search',
            params={'q': keyword, 'form': 'HDRSC2', 'first': '1', 'count': str(limit)},
            timeout=network_timeout(10),
            headers=USER_AGENT,
        )
        r.raise_for_status()
        text = r.text
    except Exception as e:
        logger.warning("必应图片搜索请求失败: %s -> %s", host, e)
        return []

    # 结果图挂在 <a class="iusc" ... m="{...json...}">，m 是转义后的 JSON（含原图直链与描述）。
    # 依次尝试多种写法，避免因一种标记失效就全军覆没。
    matches = []
    for pattern in (r'class="iusc"[^>]*\bm="([^"]+)"',
                    r'\bm="(\{[^"]+})"',
                    r"\bm='(\{[^']+})'"):
        matches = re.findall(pattern, text)
        if matches:
            break
    if not matches:
        logger.warning("必应图片页结构疑似变化（未命中 m 属性）: %s", host)
        return []

    results = []
    for raw in matches:
        try:
            meta = json.loads(html.unescape(raw))
            if not isinstance(meta, dict):
                continue
            t = meta.get('t')
            if isinstance(t, dict):
                # 旧结构：t 是 {title, w, h, turl}
                title = (t.get('t') or meta.get('desc') or '').strip()
                w = int(t.get('w') or 0)
                h = int(t.get('h') or 0)
                turl = t.get('turl')
            else:
                # 新结构：t 直接是标题字符串，尺寸不再内嵌
                title = (str(t).strip() if t else '') or (meta.get('desc') or '').strip()
                w = h = 0
                turl = None
            url = meta.get('murl') or meta.get('turl') or turl or ''
            if not url.startswith('http'):
                continue
            results.append({'url': url, 'title': title, 'w': w, 'h': h})
            if len(results) >= limit:
                break
        except (ValueError, TypeError, AttributeError):
            continue
    return results


def _slide_text(slide_data, topic):
    """拼接一页的语义文本，用于相关性打分"""
    parts = [topic, slide_data.get('title') or '']
    content = slide_data.get('content') or []
    if isinstance(content, list):
        parts += [str(x) for x in content]
    else:
        parts.append(str(content))
    return ' '.join(p for p in parts if p)


def _local_image_query(slide_data, topic):
    """无 DeepSeek 时的本地兜底：标题优先，标题太泛时融合主题"""
    title = (slide_data.get('title') or '').strip()
    if title and title not in _GENERIC_TITLES:
        return title
    if title:
        return f'{title} {topic}'.strip()
    content = slide_data.get('content') or []
    bullet_text = ' '.join(str(x) for x in content) if isinstance(content, list) else str(content)
    words = [w for w in re.findall(r'[一-鿿]+|[a-zA-Z0-9]+', bullet_text)
             if w not in _STOPWORDS and len(w) > 1]
    return ' '.join(words[:6]) or topic


def _generate_image_queries(data):
    """一次性让 DeepSeek 为每页内容生成最合适的图片搜索词，返回 {页索引: 关键词}"""
    key = runtime_config.get('DEEPSEEK_API_KEY')
    if not key:
        return {}
    slides = data.get('slides', [])
    content_idx = [(i, s) for i, s in enumerate(slides) if s.get('type') == 'content']
    if not content_idx:
        return {}
    lines = []
    for i, s in content_idx:
        title = s.get('title', '')
        bullets = s.get('content', [])
        bullet_str = ' / '.join(str(b) for b in bullets[:3]) if isinstance(bullets, list) else str(bullets)
        lines.append(f'{i}. 标题：{title}；要点：{bullet_str}')
    prompt = (
        '下面每行是一页幻灯片的标题和要点。请为每一页分别生成一个最适合搜索配图的英文关键词短语'
        '（2~5 个单词，聚焦画面主体、场景或意象，不要包含 "PPT"、"slide"、"presentation" 等词）。\n'
        + '\n'.join(lines)
        + '\n只返回 JSON，形如 {"0": "关键词短语", "1": "关键词短语"}'
    )
    try:
        headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
        payload = {'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': prompt}],
                   'temperature': 0.4, 'max_tokens': 600}
        r = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=network_timeout(60))
        r.raise_for_status()
        result = json.loads(_extract_json_block(r.json()['choices'][0]['message']['content']))
        return {int(k): str(v) for k, v in result.items() if v}
    except Exception as e:
        logger.warning("AI 生成图片搜索词失败: %s", e)
        return {}


def _vision_match(image_bytes, expected):
    """用视觉大模型判断图片与主题的匹配度，返回 0~1 分数；未配置或无结果返回 None"""
    key = runtime_config.get('VISION_API_KEY')
    if not key or not image_bytes:
        return None
    try:
        b64 = base64.b64encode(image_bytes).decode('ascii')
        payload = {
            'model': VISION_MODEL,
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}},
                    {'type': 'text', 'text': f'这张图片作为幻灯片配图，是否贴合主题「{expected}」？只回答 0 到 100 的一个整数匹配度。'},
                ],
            }],
            'max_tokens': 10,
        }
        r = requests.post(VISION_API_URL, headers={'Authorization': f'Bearer {key}',
                                                   'Content-Type': 'application/json'},
                          json=payload, timeout=network_timeout(30), proxies=_proxies())
        r.raise_for_status()
        txt = r.json()['choices'][0]['message']['content']
        m = re.search(r'\d+', txt)
        return int(m.group()) / 100.0 if m else None
    except Exception as e:
        logger.warning("视觉校验失败: %s", e)
        return None


def _rank_images(candidates, slide_text):
    """按图片自身描述与页面内容的相关性排序（无视觉模型时的软匹配），大图略优先"""
    scored = []
    for c in candidates:
        sim = _text_sim(c.get('title', ''), slide_text)
        area = max(0, (c.get('w') or 0) * (c.get('h') or 0))
        size_bonus = min(0.2, area / 4_000_000 * 0.2)  # 4MP 封顶 +0.2
        scored.append((sim + size_bonus, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored]


def _get_slide_image(slide_data, topic, image_mode, query=None, use_vision=False):
    """按用户选择获取图片；联网失败不自动调用 AI。"""
    query = query or _local_image_query(slide_data, topic)
    if image_mode == 'ai':
        return _ai_image(query)

    if image_mode == 'real':
        slide_text = _slide_text(slide_data, topic)
        candidates = _rank_images(_search_bing_images(query), slide_text)
        if not candidates:
            return None

        # 依相关性依次下载前几名，只保留通过质量校验的
        picked = []
        for c in candidates[:6]:
            check_budget()
            img = _download_image_bytes(c['url'], timeout=15)
            if _validate_image(img):
                picked.append(img)
            if len(picked) >= (3 if use_vision else 1):
                break

        if not picked:
            return None

        # 可选：用视觉模型在候选里挑最贴合的一张
        if use_vision and len(picked) > 1:
            best = max(picked, key=lambda b: _vision_match(b, query) or 0.0)
            return best
        return picked[0]

    return None
