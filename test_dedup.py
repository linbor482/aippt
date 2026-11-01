"""模板查重：四套模板彼此相似度 <70%，单份稿内版面重复率 ≤70%。"""
import unittest
from collections import Counter
from itertools import combinations

from presentation_design import build_scenes
from similarity import token_jaccard


SAMPLE = {'title': '市场分析', 'slides': [
    {'type': 'cover', 'title': '市场分析', 'content': '行业洞察'},
    {'type': 'content', 'title': '行业现状', 'content': ['市场规模增长', '竞争格局', '技术趋势', '政策环境']},
    {'type': 'content', 'title': '发展历程', 'content': ['2018 起步', '2021 扩张', '2024 成熟']},
    {'type': 'content', 'title': '核心洞察', 'content': ['洞察一', '洞察二', '洞察三']},
    {'type': 'final', 'title': '总结', 'content': '谢谢观看'},
]}


def _template_signature(outline, template):
    """模板结构签名：元素种类 + 圆整几何 + 字号/字体/加粗（不含颜色，颜色本就该不同）。"""
    tokens = []
    for scene in build_scenes(outline, template, 'none'):
        tokens.append('layout:' + str(scene.get('layout')))
        for el in scene.get('elements', []):
            tokens.append(f"{el.get('kind')}:{round(float(el.get('x', 0)), 1)}:{round(float(el.get('y', 0)), 1)}"
                          f":{round(float(el.get('w', 0)), 1)}:{round(float(el.get('h', 0)), 1)}"
                          f":{el.get('size')}:{el.get('font')}:{el.get('bold')}")
    return ' '.join(tokens)


class TemplateDedupTests(unittest.TestCase):
    def test_four_templates_pairwise_similarity_below_70(self):
        sigs = {t: _template_signature(SAMPLE, t) for t in ('default', 'modern', 'creative', 'luxury')}
        for a, b in combinations(sigs, 2):
            sim = token_jaccard(sigs[a], sigs[b])
            self.assertLess(sim, 0.70, f'{a} vs {b} 相似度 {sim:.2f} 超过 70%')

    def test_deck_layout_repetition_capped_at_70(self):
        slides = [{'type': 'cover', 'title': '封面', 'content': ''}]
        for i in range(10):
            slides.append({'type': 'content', 'title': f'页{i+1}', 'content': ['要点甲', '要点乙', '要点丙', '要点丁']})
        slides.append({'type': 'final', 'title': '结束', 'content': ''})
        scenes = build_scenes({'title': 'T', 'slides': slides}, 'luxury', 'none')
        layouts = [s['layout'] for s in scenes if s['layout'] in ('editorial', 'columns', 'timeline')]
        dominant = Counter(layouts).most_common(1)[0][1]
        self.assertLessEqual(dominant / len(layouts), 0.70)


if __name__ == '__main__':
    unittest.main()
