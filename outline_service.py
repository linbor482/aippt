"""Outline content provider and deterministic placeholder content."""
import json
import logging
import re
import requests
import runtime_config
from settings import DEEPSEEK_API_URL

logger = logging.getLogger(__name__)


def outline_prompt(topic, pages, language='中文'):
    return f"""请根据以下创作需求生成 PPT 大纲。需求可能包含主题、受众、目标、语气、内容边界和禁止事项，请逐条遵守。
<创作需求>
{topic}
</创作需求>
界面设置为 {pages} 页、{language}；必须严格生成恰好 {pages} 页（第 1 页为封面，最后一页为总结/感谢页），总页数等于 {pages}，不得多一页也不得少一页。仅当创作需求中明确写明了具体页数时才可覆盖，否则一律按 {pages} 页生成。
提炼简洁的演示标题，不要把整段需求或约束当作标题。不要编造数据、来源或事实；缺少资料时明确标注待补充。

要求：
1. 返回JSON格式
2. 包含标题、副标题和每页的详细内容
3. 每页包含标题和要点（3-5个要点）
4. 第一页是封面，最后一页是总结或感谢页

JSON格式示例：
{{
    "title": "主标题",
    "subtitle": "副标题",
    "slides": [
        {{
            "type": "cover",
            "title": "封面标题",
            "content": "副标题或作者信息"
        }},
        {{
            "type": "content",
            "title": "页面标题",
            "content": [
                "要点1",
                "要点2",
                "要点3"
            ]
        }},
        {{
            "type": "final",
            "title": "感谢观看",
            "content": "谢谢"
        }}
    ]
}}

（示例仅演示 JSON 格式，实际必须输出恰好 {pages} 页）

请只返回JSON，不要包含其他说明文字。"""


def generate_content_with_ai(topic, pages, language='中文'):
    """使用DeepSeek API生成PPT内容大纲"""
    key = runtime_config.get('DEEPSEEK_API_KEY')
    if not key:
        return None
    prompt = outline_prompt(topic, pages, language)
    try:
        headers = {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.7,
            'max_tokens': 4000
        }
        
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # 提取JSON
        json_str = content
        if '```json' in content:
            json_str = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            json_str = content.split('```')[1].split('```')[0].strip()
        
        return json.loads(json_str)
        
    except Exception as e:
        logger.warning("AI 生成内容出错: %s", e)
        return None

def _extract_json_block(content):
    """从模型回复里抠出 JSON 字符串"""
    if '```json' in content:
        return content.split('```json')[1].split('```')[0].strip()
    if '```' in content:
        return content.split('```')[1].split('```')[0].strip()
    return content.strip()

def generate_default_content(topic, pages, language='中文'):
    """生成默认PPT内容"""
    topic = re.split(r'[\n。；;]', topic.strip(), maxsplit=1)[0][:60] or '未命名演示'
    slides = []
    
    # 封面
    slides.append({
        'type': 'cover',
        'title': topic,
        'content': '智能生成PPT' if language == '中文' else 'AI Generated Presentation'
    })
    
    # 内容页
    for i in range(1, pages - 1):
        slides.append({
            'type': 'content',
            'title': f'{topic} - {i}' if language == '中文' else f'{topic} - Page {i}',
            'content': [
                f'要点 {i}.1 - 详细内容描述' if language == '中文' else f'Point {i}.1 - Detailed description',
                f'要点 {i}.2 - 详细内容描述' if language == '中文' else f'Point {i}.2 - Detailed description',
                f'要点 {i}.3 - 详细内容描述' if language == '中文' else f'Point {i}.3 - Detailed description',
            ]
        })
    
    # 结束页
    if pages == 1:
        return {'title': topic, 'subtitle': '', 'slides': slides}
    slides.append({
        'type': 'final',
        'title': '谢谢观看' if language == '中文' else 'Thank You',
        'content': 'Q&A' if language == '中文' else 'Questions & Answers'
    })
    
    return {
        'title': topic,
        'subtitle': '',
        'slides': slides
    }
