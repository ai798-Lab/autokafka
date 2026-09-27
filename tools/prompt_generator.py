"""
插图 Prompt 生成器
根据编排方案生成 Gemini 图像生成 Prompt
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import json
import os


@dataclass
class ImagePrompt:
    """图像生成 Prompt"""
    id: str
    type: str
    prompt: str
    negative_prompt: str
    position: str
    context: str


class PromptGenerator:
    """Prompt 生成器"""

    # 背景色定义
    BACKGROUND_COLOR = "#F5F0E6"  # 高端米黄色

    # 默认风格基底（纯手绘线条风）
    DEFAULT_STYLE_BASE = """
    Pure hand-drawn line art illustration, minimalist sketch style,
    simple elegant black ink strokes on warm cream background (#{bg_color}),
    single-weight fine lines, loose artistic hand-drawn quality,
    whitespace as design element, editorial illustration aesthetic,
    subtle imperfections that feel human and organic,
    16:9 aspect ratio, centered composition with breathing room
    """.strip().format(bg_color="F5F0E6")

    # 默认负面提示词
    DEFAULT_NEGATIVE = """
    digital art, 3D render, photorealistic, gradients, shadows,
    complex shading, multiple colors, busy composition,
    cluttered elements, heavy line weight, perfect symmetry,
    corporate clip art, stock photo style, watermark
    """.strip()

    # 类型特定的提示词模板
    # 设计原则：先理解主旨 → 抽象出隐喻/象征元素 → 用极简线条表现
    TYPE_TEMPLATES = {
        'hero': {
            'template': """
            {style_base},

            [Core visual metaphor]: {metaphor_description},

            [Composition]: The main symbolic element is placed at the center,
            secondary elements orbit or connect to it with delicate dotted lines,
            generous negative space on all sides creating visual breathing room,

            [Line quality]: Confident single-stroke outlines, hand-drawn wobble,
            minimal interior details, let the silhouette tell the story,

            [Optional text]: One short phrase (2-4 words max) in elegant sans-serif,
            placed discretely at bottom or corner, acting as a gentle anchor
            """,
            'negative_extra': "heavy shading, complex backgrounds, multiple focal points"
        },
        'concept': {
            'template': """
            {style_base},

            [Core visual metaphor]: {metaphor_description},

            [Symbolic elements]: Distill the concept into 1-2 iconic objects,
            use universally understood symbols (lightbulb=idea, key=access, bridge=connection),
            show relationship between elements through spatial arrangement,

            [Composition]: Single focal point with supporting elements,
            elements connected by thin hand-drawn lines or arrows,
            70% whitespace to 30% illustration ratio,

            [Line quality]: Clean but imperfect strokes, sketch-like quality,
            varying line confidence to show emphasis
            """,
            'negative_extra': "literal representation, complex diagrams, too many symbols"
        },
        'analogy': {
            'template': """
            {style_base},

            [Core visual metaphor]: {metaphor_description},

            [Scene construction]: Create a mini-narrative with 2-3 symbolic objects,
            show the relationship/interaction between the analogy elements,
            use familiar everyday objects to represent abstract concepts,

            [Spatial relationship]: Main subject on one side,
            the thing it connects to on the other,
            visual bridge or connection line between them,

            [Storytelling details]: One or two tiny details that add charm,
            (a small arrow, a dotted path, a gentle curve connecting elements),

            [Optional label]: Single word or short phrase near each key element
            """,
            'negative_extra': "realistic scenes, complex environments, too many characters"
        },
        'diagram': {
            'template': """
            {style_base},

            [Core visual metaphor]: {metaphor_description},

            [Flow visualization]: Show {process_count} steps as connected nodes,
            each node is a simple iconic symbol (circle, square, or small sketch),
            hand-drawn arrows or dotted lines showing direction of flow,

            [Layout]: Linear left-to-right or top-to-bottom arrangement,
            equal spacing between steps, clear visual hierarchy,
            numbered or lettered steps in small handwritten style,

            [Connection style]: Curved hand-drawn arrows, not rigid straight lines,
            small decorative elements at connection points (dots, small circles),

            [Labels]: Minimal text labels (1-2 words) below or beside each node
            """,
            'negative_extra': "complex flowcharts, too many branches, corporate diagram style"
        },
        'comparison': {
            'template': """
            {style_base},

            [Core visual metaphor]: {metaphor_description},

            [Dual composition]: Split canvas into left and right zones,
            each side contains one symbolic representation,
            vertical dotted line or gentle divide in the middle,

            [Contrast elements]: Left side shows concept A as simple icon,
            right side shows concept B as contrasting icon,
            visual weight and size indicate relative importance,

            [Connecting element]: A small bridge, arrow, or "vs" symbol in center,
            subtle visual cues showing the key difference,

            [Optional labels]: Single word beneath each side identifying the concept
            """,
            'negative_extra': "complex charts, data visualizations, too many comparison points"
        },
        'mood': {
            'template': """
            {style_base},

            [Core visual metaphor]: {metaphor_description},

            [Atmosphere]: Single poetic visual element floating in space,
            extremely minimal - just one or two strokes suggesting the theme,
            80% negative space creating contemplative feeling,

            [Emotional tone]: Gentle, reflective, like a pause for breath,
            the illustration whispers rather than shouts,

            [Element placement]: Off-center placement creating dynamic tension,
            small scale relative to canvas size,

            [Optional poetry]: One evocative word or very short phrase,
            placed with intention, adding to the meditative quality
            """,
            'negative_extra': "busy scenes, strong emotions, action or movement"
        }
    }

    def __init__(self, style_base: str = None, negative_base: str = None):
        """
        初始化生成器

        Args:
            style_base: 自定义风格基底
            negative_base: 自定义负面提示词
        """
        self.style_base = style_base or self.DEFAULT_STYLE_BASE
        self.negative_base = negative_base or self.DEFAULT_NEGATIVE

    def _clean_text(self, text: str) -> str:
        """清理文本，移除多余空白"""
        return ' '.join(text.split())

    def _build_metaphor_description(self, slot: Dict, article_title: str = "") -> str:
        """
        构建隐喻描述

        优先使用 slot 中的 metaphor_description 字段（由 AI 生成的详细隐喻）
        如果没有，则使用 context 和 anchor_text 作为后备

        Args:
            slot: 插图槽位信息，应包含：
                - metaphor_description: AI 生成的详细隐喻描述（推荐）
                  例如："A friendly robot head in the center, with multiple glowing skill
                         modules floating around its brain area, connected by thin dotted
                         lines suggesting neural pathways"
                - context: 段落上下文（后备）
                - anchor_text: 锚定文本（后备）
            article_title: 文章标题

        Returns:
            隐喻描述字符串
        """
        # 优先使用 AI 生成的详细隐喻描述
        if slot.get('metaphor_description'):
            return slot['metaphor_description']

        # 后备方案：从 context 和 anchor_text 构建
        context = slot.get('context', '')
        anchor = slot.get('anchor_text', '')

        if anchor:
            return f"Visual representation of: {anchor}"
        elif context:
            # 截取前100字符作为描述
            return f"Visual representation of: {context[:100]}"
        elif article_title:
            return f"Visual representation of: {article_title}"
        else:
            return "Abstract conceptual illustration"

    def _count_process_steps(self, context: str) -> int:
        """
        从上下文中提取流程步骤数量

        Args:
            context: 上下文文本

        Returns:
            步骤数量，默认为 3
        """
        import re

        # 尝试匹配中文序号
        chinese_patterns = [
            r'第[一二三四五六七八九十]步',
            r'[一二三四五六七八九十]、',
            r'[①②③④⑤⑥⑦⑧⑨⑩]',
        ]

        # 尝试匹配数字序号
        digit_patterns = [
            r'\d+\.',
            r'\d+、',
            r'\d+\)',
        ]

        max_count = 0

        for pattern in chinese_patterns + digit_patterns:
            matches = re.findall(pattern, context)
            if len(matches) > max_count:
                max_count = len(matches)

        return max_count if max_count >= 2 else 3  # 默认 3 步

    def generate_prompt(
        self,
        slot: Dict,
        article_title: str = "",
        additional_context: str = ""
    ) -> ImagePrompt:
        """
        为单个槽位生成 Prompt

        slot 数据结构应包含：
        {
            'id': 'img_001',
            'type': 'hero' | 'concept' | 'analogy' | 'diagram' | 'comparison' | 'mood',
            'position': 'before_paragraph_1',
            'context': '段落原文或摘要',
            'anchor_text': '触发词或关键句',
            'metaphor_description': '【推荐】AI 生成的详细隐喻描述，例如：
                "A friendly robot head in the center, with multiple glowing skill
                 modules floating around its brain area, connected by thin dotted
                 lines suggesting neural pathways. The robot has simple dot eyes
                 showing curiosity."'
        }

        Args:
            slot: 插图槽位信息
            article_title: 文章标题
            additional_context: 额外上下文

        Returns:
            生成的 Prompt
        """
        slot_type = slot.get('type', 'concept')
        template_config = self.TYPE_TEMPLATES.get(slot_type, self.TYPE_TEMPLATES['concept'])

        context = slot.get('context', '')

        # 构建隐喻描述
        metaphor_description = self._build_metaphor_description(slot, article_title)

        # 获取流程步骤数量（用于 diagram 类型）
        process_count = self._count_process_steps(context)

        # 根据类型填充模板
        if slot_type == 'diagram':
            filled_template = template_config['template'].format(
                style_base=self.style_base,
                metaphor_description=metaphor_description,
                process_count=process_count
            )
        else:
            filled_template = template_config['template'].format(
                style_base=self.style_base,
                metaphor_description=metaphor_description
            )

        # 组合负面提示词
        negative = f"{self.negative_base}, {template_config.get('negative_extra', '')}"

        return ImagePrompt(
            id=slot.get('id', 'img_001'),
            type=slot_type,
            prompt=self._clean_text(filled_template),
            negative_prompt=self._clean_text(negative),
            position=slot.get('position', ''),
            context=context
        )

    def generate_all(
        self,
        layout: Dict,
        article_title: str = ""
    ) -> List[ImagePrompt]:
        """
        为所有槽位生成 Prompt

        Args:
            layout: 编排方案
            article_title: 文章标题

        Returns:
            Prompt 列表
        """
        prompts = []

        slots = layout.get('layout', [])
        for slot in slots:
            prompt = self.generate_prompt(slot, article_title)
            prompts.append(prompt)

        return prompts

    def to_json(self, prompts: List[ImagePrompt]) -> str:
        """
        转换为 JSON 格式

        Args:
            prompts: Prompt 列表

        Returns:
            JSON 字符串
        """
        data = [asdict(p) for p in prompts]
        return json.dumps(data, ensure_ascii=False, indent=2)

    def save_to_file(self, prompts: List[ImagePrompt], filepath: str):
        """
        保存到文件

        Args:
            prompts: Prompt 列表
            filepath: 文件路径
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json(prompts))


# 便捷函数
def generate_image_prompts(
    layout: Dict,
    article_title: str = "",
    style_base: str = None
) -> List[Dict]:
    """
    生成图像 Prompt（便捷函数）

    Args:
        layout: 编排方案
        article_title: 文章标题
        style_base: 自定义风格

    Returns:
        Prompt 字典列表
    """
    generator = PromptGenerator(style_base=style_base)
    prompts = generator.generate_all(layout, article_title)
    return [asdict(p) for p in prompts]


if __name__ == "__main__":
    # 测试 - 展示新的 metaphor_description 字段用法
    #
    # 核心理念：
    # 1. 先理解段落主旨
    # 2. 抽象出隐喻和象征元素
    # 3. 用极简手绘线条表现
    #
    # metaphor_description 字段应由 AI 在分析段落后生成，
    # 描述具体的视觉元素和它们之间的空间关系

    test_layout = {
        'total_illustrations': 3,
        'layout': [
            {
                'id': 'img_001',
                'position': 'before_paragraph_1',
                'type': 'hero',
                'context': 'Claude Skills 就是给 AI 的外挂技能包',
                'anchor_text': '',
                # 【重要】metaphor_description 是核心字段
                # 详细描述画面元素和空间关系
                'metaphor_description': '''
                A friendly robot head drawn with simple curved lines,
                positioned at center. Around its brain area, 4-5 small
                skill module icons (shaped like puzzle pieces or app icons)
                float in an orbital pattern. Thin dotted lines connect
                each module to the robot's head, suggesting neural pathways.
                The robot has minimal dot eyes showing curiosity.
                Small label "Skills" near one floating module.
                '''
            },
            {
                'id': 'img_002',
                'position': 'after_paragraph_4',
                'type': 'analogy',
                'context': 'Token 就像乐高积木，AI 用这些积木来理解和组装语言',
                'anchor_text': '就像乐高积木',
                'metaphor_description': '''
                Left side: A simple speech bubble or text block,
                drawn with loose hand strokes.
                Right side: The same shape broken into small LEGO-like
                brick pieces, scattered but recognizable.
                A curved arrow with hand-drawn wobble connects left to right,
                showing the transformation.
                Small handwritten label "Token" pointing to one brick.
                '''
            },
            {
                'id': 'img_003',
                'position': 'after_paragraph_8',
                'type': 'diagram',
                'context': '''使用 Skills 的步骤：
                第一步，找到合适的 Skill。
                第二步，配置参数。
                第三步，运行测试。
                第四步，根据结果调整。''',
                'anchor_text': '',
                'metaphor_description': '''
                4 simple circular nodes arranged horizontally,
                each containing a minimal icon:
                Node 1: magnifying glass (Find)
                Node 2: slider controls (Configure)
                Node 3: play button (Run)
                Node 4: circular arrows (Adjust)
                Hand-drawn curved arrows connect the nodes left to right.
                Small handwritten numbers "1 2 3 4" above each node.
                '''
            }
        ]
    }

    prompts = generate_image_prompts(test_layout, "Claude Skills 入门指南")

    print("=" * 60)
    print("生成的 Prompt 示例（纯手绘线条风格）")
    print("背景色: #F5F0E6 (高端米黄色)")
    print("=" * 60)
    print(json.dumps(prompts, ensure_ascii=False, indent=2))
