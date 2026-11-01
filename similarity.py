"""文本相似度与大纲文本化，供图片匹配与大纲查重共用。"""
import re


def _ngrams(s, n=2):
    s = re.sub(r'[\W_]+', '', s.lower())
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def text_sim(a, b):
    """无词典的文本相似度：英文按词、中文按二元组，取较大者（0~1）。"""
    if not a or not b:
        return 0.0
    a_l, b_l = a.lower(), b.lower()
    aw = set(re.findall(r'[a-z0-9]+', a_l))
    bw = set(re.findall(r'[a-z0-9]+', b_l))
    word = len(aw & bw) / len(aw | bw) if (aw and bw) else 0.0
    ga, gb = _ngrams(a_l), _ngrams(b_l)
    bigram = len(ga & gb) / len(ga | gb) if (ga and gb) else 0.0
    return max(word, bigram)


def token_jaccard(a, b):
    """集合 Jaccard（按空白切词），用于结构化签名比较，避免二元组兜底虚高。"""
    sa = set(a.split())
    sb = set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def outline_text(outline):
    """把大纲压成一段文本（主标题+副标题+每页标题+要点），用于相似度比较。"""
    parts = [outline.get('title') or '', outline.get('subtitle') or '']
    for slide in outline.get('slides', []):
        parts.append(slide.get('title') or '')
        content = slide.get('content')
        if isinstance(content, list):
            parts += [str(x) for x in content]
        elif content:
            parts.append(str(content))
    return ' '.join(p for p in parts if p)
