"""
图文编排引擎
决定在文章的什么位置放置什么类型的插图
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class IllustrationType(Enum):
    """插图类型"""
    HERO = "hero"              # 主视觉，抽象概念具象化
    CONCEPT = "concept"        # 概念可视化
    ANALOGY = "analogy"        # 类比场景图
    DIAGRAM = "diagram"        # 流程/结构图
    COMPARISON = "comparison"  # 对比图
    MOOD = "mood"              # 氛围图/留白图


class LengthTier(Enum):
    """字数档位"""
    COMPACT = "compact"        # 精炼版 1200-2000
    STANDARD = "standard"      # 标准版 2000-4000
    DEEP = "deep"              # 深度版 4000-7000
    LONG = "long"              # 长文版 7000-10000


@dataclass
class IllustrationSlot:
    """插图位置槽"""
    id: str
    position: str              # before_paragraph_N / after_paragraph_N
    paragraph_index: int
    type: IllustrationType
    priority: int              # 1-5, 5 最高
    context: str               # 相关上下文
    anchor_text: str = ""      # 锚定文本（如类比的具体句子）
    is_required: bool = False  # 是否必需

    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            'type': self.type.value
        }


@dataclass
class LayoutPlan:
    """编排方案"""
    article_title: str
    length_tier: LengthTier
    word_count: int
    total_paragraphs: int

    # 推荐的插图数量范围
    min_illustrations: int
    max_illustrations: int

    # 插图槽位
    slots: List[IllustrationSlot] = field(default_factory=list)

    # 最终选中的槽位
    selected_slots: List[IllustrationSlot] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'article_title': self.article_title,
            'length_tier': self.length_tier.value,
            'word_count': self.word_count,
            'total_paragraphs': self.total_paragraphs,
            'min_illustrations': self.min_illustrations,
            'max_illustrations': self.max_illustrations,
            'slots': [s.to_dict() for s in self.slots],
            'selected_slots': [s.to_dict() for s in self.selected_slots]
        }


class LayoutEngine:
    """图文编排引擎"""

    # 字数档位配置
    TIER_CONFIG = {
        LengthTier.COMPACT: {
            'min_words': 1200,
            'max_words': 2000,
            'min_illustrations': 1,
            'max_illustrations': 2,
            'required': [IllustrationType.HERO],
            'optional': [IllustrationType.CONCEPT, IllustrationType.ANALOGY]
        },
        LengthTier.STANDARD: {
            'min_words': 2000,
            'max_words': 4000,
            'min_illustrations': 2,
            'max_illustrations': 3,
            'required': [IllustrationType.HERO, IllustrationType.CONCEPT],
            'optional': [IllustrationType.ANALOGY, IllustrationType.DIAGRAM]
        },
        LengthTier.DEEP: {
            'min_words': 4000,
            'max_words': 7000,
            'min_illustrations': 3,
            'max_illustrations': 5,
            'required': [IllustrationType.HERO, IllustrationType.CONCEPT, IllustrationType.ANALOGY],
            'optional': [IllustrationType.DIAGRAM, IllustrationType.COMPARISON]
        },
        LengthTier.LONG: {
            'min_words': 7000,
            'max_words': 10000,
            'min_illustrations': 4,
            'max_illustrations': 6,
            'required': [IllustrationType.HERO, IllustrationType.CONCEPT, IllustrationType.ANALOGY, IllustrationType.DIAGRAM],
            'optional': [IllustrationType.COMPARISON, IllustrationType.MOOD]
        }
    }

    # 触发条件关键词
    ANALOGY_TRIGGERS = [
        "就像", "好比", "类似于", "想象一下", "打个比方",
        "如同", "仿佛", "相当于", "可以理解为"
    ]

    DIAGRAM_TRIGGERS = [
        "首先", "其次", "然后", "最后", "第一步", "第二步",
        "步骤", "流程", "分为", "包括以下"
    ]

    COMPARISON_TRIGGERS = [
        "相比", "对比", "区别", "不同", "vs", "VS",
        "优势", "劣势", "差异"
    ]

    def __init__(self):
        self.plan: Optional[LayoutPlan] = None

    def _detect_tier(self, word_count: int) -> LengthTier:
        """
        根据字数检测档位

        Args:
            word_count: 字数

        Returns:
            档位
        """
        if word_count < 2000:
            return LengthTier.COMPACT
        elif word_count < 4000:
            return LengthTier.STANDARD
        elif word_count < 7000:
            return LengthTier.DEEP
        else:
            return LengthTier.LONG

    def _split_paragraphs(self, content: str) -> List[str]:
        """
        分割段落

        Args:
            content: 文章内容

        Returns:
            段落列表
        """
        # 按换行分割，过滤空段落
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        return paragraphs

    def _find_analogy_positions(self, paragraphs: List[str]) -> List[Dict]:
        """
        找到类比段落位置

        Args:
            paragraphs: 段落列表

        Returns:
            类比位置信息列表
        """
        positions = []

        for i, para in enumerate(paragraphs):
            for trigger in self.ANALOGY_TRIGGERS:
                if trigger in para:
                    positions.append({
                        'index': i,
                        'trigger': trigger,
                        'text': para[:100]
                    })
                    break

        return positions

    def _find_diagram_positions(self, paragraphs: List[str]) -> List[Dict]:
        """
        找到流程/步骤段落位置

        Args:
            paragraphs: 段落列表

        Returns:
            流程位置信息列表
        """
        positions = []

        # 检查连续的步骤
        step_count = 0
        step_start = -1

        for i, para in enumerate(paragraphs):
            has_trigger = any(t in para for t in self.DIAGRAM_TRIGGERS)

            if has_trigger:
                if step_start == -1:
                    step_start = i
                step_count += 1
            else:
                if step_count >= 3:  # 至少3步才触发
                    positions.append({
                        'index': step_start,
                        'step_count': step_count,
                        'text': paragraphs[step_start][:100]
                    })
                step_count = 0
                step_start = -1

        # 处理结尾的步骤
        if step_count >= 3:
            positions.append({
                'index': step_start,
                'step_count': step_count,
                'text': paragraphs[step_start][:100]
            })

        return positions

    def _find_comparison_positions(self, paragraphs: List[str]) -> List[Dict]:
        """
        找到对比段落位置

        Args:
            paragraphs: 段落列表

        Returns:
            对比位置信息列表
        """
        positions = []

        for i, para in enumerate(paragraphs):
            for trigger in self.COMPARISON_TRIGGERS:
                if trigger in para:
                    positions.append({
                        'index': i,
                        'trigger': trigger,
                        'text': para[:100]
                    })
                    break

        return positions

    def _find_mood_positions(self, paragraphs: List[str]) -> List[Dict]:
        """
        找到适合放氛围图的位置（长段落后）

        Args:
            paragraphs: 段落列表

        Returns:
            氛围图位置信息列表
        """
        positions = []
        cumulative_length = 0

        for i, para in enumerate(paragraphs):
            cumulative_length += len(para)

            # 每累积 1500 字左右考虑一个节奏点
            if cumulative_length > 1500:
                positions.append({
                    'index': i,
                    'cumulative_length': cumulative_length,
                    'text': '节奏调节点'
                })
                cumulative_length = 0

        return positions

    def analyze(self, content: str, title: str = "") -> LayoutPlan:
        """
        分析文章并生成编排方案

        Args:
            content: 文章内容
            title: 文章标题

        Returns:
            编排方案
        """
        word_count = len(content)
        tier = self._detect_tier(word_count)
        config = self.TIER_CONFIG[tier]

        paragraphs = self._split_paragraphs(content)

        self.plan = LayoutPlan(
            article_title=title,
            length_tier=tier,
            word_count=word_count,
            total_paragraphs=len(paragraphs),
            min_illustrations=config['min_illustrations'],
            max_illustrations=config['max_illustrations']
        )

        slots = []
        slot_id = 0

        # 1. 头图（必需）
        slot_id += 1
        slots.append(IllustrationSlot(
            id=f"img_{slot_id:03d}",
            position="before_paragraph_1",
            paragraph_index=0,
            type=IllustrationType.HERO,
            priority=5,
            context=title or paragraphs[0][:50] if paragraphs else "",
            is_required=IllustrationType.HERO in config['required']
        ))

        # 2. 概念图位置（通常在第一个主要概念解释后）
        if len(paragraphs) > 2:
            slot_id += 1
            slots.append(IllustrationSlot(
                id=f"img_{slot_id:03d}",
                position="after_paragraph_2",
                paragraph_index=2,
                type=IllustrationType.CONCEPT,
                priority=4,
                context=paragraphs[1][:100] if len(paragraphs) > 1 else "",
                is_required=IllustrationType.CONCEPT in config['required']
            ))

        # 3. 类比图位置
        analogy_positions = self._find_analogy_positions(paragraphs)
        for pos in analogy_positions[:2]:  # 最多2个类比图
            slot_id += 1
            slots.append(IllustrationSlot(
                id=f"img_{slot_id:03d}",
                position=f"after_paragraph_{pos['index'] + 1}",
                paragraph_index=pos['index'],
                type=IllustrationType.ANALOGY,
                priority=4,
                context=pos['text'],
                anchor_text=pos['trigger'],
                is_required=IllustrationType.ANALOGY in config['required']
            ))

        # 4. 流程图位置
        diagram_positions = self._find_diagram_positions(paragraphs)
        for pos in diagram_positions[:1]:  # 最多1个流程图
            slot_id += 1
            slots.append(IllustrationSlot(
                id=f"img_{slot_id:03d}",
                position=f"after_paragraph_{pos['index'] + 1}",
                paragraph_index=pos['index'],
                type=IllustrationType.DIAGRAM,
                priority=3,
                context=f"{pos['step_count']}个步骤的流程",
                is_required=IllustrationType.DIAGRAM in config['required']
            ))

        # 5. 对比图位置
        comparison_positions = self._find_comparison_positions(paragraphs)
        for pos in comparison_positions[:1]:  # 最多1个对比图
            slot_id += 1
            slots.append(IllustrationSlot(
                id=f"img_{slot_id:03d}",
                position=f"after_paragraph_{pos['index'] + 1}",
                paragraph_index=pos['index'],
                type=IllustrationType.COMPARISON,
                priority=3,
                context=pos['text'],
                is_required=IllustrationType.COMPARISON in config['required']
            ))

        # 6. 氛围图位置（仅长文版）
        if tier == LengthTier.LONG:
            mood_positions = self._find_mood_positions(paragraphs)
            for pos in mood_positions[:2]:  # 最多2个氛围图
                slot_id += 1
                slots.append(IllustrationSlot(
                    id=f"img_{slot_id:03d}",
                    position=f"after_paragraph_{pos['index'] + 1}",
                    paragraph_index=pos['index'],
                    type=IllustrationType.MOOD,
                    priority=2,
                    context=pos['text'],
                    is_required=False
                ))

        self.plan.slots = slots

        # 选择最终的插图槽位
        self._select_slots()

        return self.plan

    def _select_slots(self):
        """选择最终的插图槽位"""
        if not self.plan:
            return

        # 先选必需的
        required = [s for s in self.plan.slots if s.is_required]

        # 再按优先级选可选的
        optional = [s for s in self.plan.slots if not s.is_required]
        optional.sort(key=lambda x: x.priority, reverse=True)

        # 计算还需要多少
        needed = self.plan.max_illustrations - len(required)
        selected_optional = optional[:needed] if needed > 0 else []

        # 合并并按段落顺序排序
        all_selected = required + selected_optional
        all_selected.sort(key=lambda x: x.paragraph_index)

        self.plan.selected_slots = all_selected

    def get_layout_json(self) -> Dict:
        """
        获取编排方案的 JSON 格式

        Returns:
            编排方案字典
        """
        if not self.plan:
            return {}

        return {
            'total_illustrations': len(self.plan.selected_slots),
            'layout': [
                {
                    'id': slot.id,
                    'position': slot.position,
                    'type': slot.type.value,
                    'context': slot.context,
                    'anchor_text': slot.anchor_text
                }
                for slot in self.plan.selected_slots
            ]
        }


# 便捷函数
def generate_layout(content: str, title: str = "") -> Dict:
    """
    生成图文编排方案（便捷函数）

    Args:
        content: 文章内容
        title: 文章标题

    Returns:
        编排方案
    """
    engine = LayoutEngine()
    engine.analyze(content, title)
    return engine.get_layout_json()


if __name__ == "__main__":
    # 测试
    test_content = """
    你以为AI在思考，其实它在做填空题。

    这不是在贬低它。恰恰相反，这个"填空题"做得实在太好了。

    要理解这一点，我们需要先搞清楚什么是Token。Token就像乐高积木。一个汉字可能是一块积木，一个英文单词可能要两三块拼起来。AI就是用这些积木来理解和组装语言。

    Claude Skills 是什么呢？想象一下，你有一个万能工匠，手边放着不同的工具箱。需要木工活就拿木工箱，需要电工活就拿电工箱。Skills 就是这些工具箱。

    使用 Skills 的步骤很简单：

    第一步，找到合适的 Skill。
    第二步，配置参数。
    第三步，运行测试。
    第四步，根据结果调整。

    相比传统的 System Prompt，Skills 更加模块化。相比 Agent，Skills 更加聚焦。它不是要替代什么，而是填补了一个空白。

    这让我想起一句话：最好的工具不是替代你，而是让你变成更好的自己。
    """

    layout = generate_layout(test_content, "Claude Skills 入门指南")

    import json
    print(json.dumps(layout, ensure_ascii=False, indent=2))
