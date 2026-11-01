"""本地生成历史（history.json），用于大纲查重与去重。"""
import json
import os
import time

from similarity import outline_text, text_sim

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(BASE_DIR, 'history.json')
MAX_ENTRIES = 50


def _read():
    try:
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, ValueError, OSError):
        return []


def load():
    return _read()


def append(outline):
    """把大纲摘要写入历史（去重、裁剪到最近 MAX_ENTRIES 条）。"""
    text = outline_text(outline)
    if not text:
        return
    entries = [e for e in _read() if e.get('text') != text]
    entries.append({'title': outline.get('title') or '', 'text': text, 'ts': time.time()})
    entries = entries[-MAX_ENTRIES:]
    try:
        with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # 只读文件系统（如 Vercel）下无历史，仍可正常生成


def max_similarity(outline):
    """新大纲与历史记录的最大相似度（0~1）。"""
    text = outline_text(outline)
    if not text:
        return 0.0
    return max((text_sim(text, e.get('text', '')) for e in _read()), default=0.0)
