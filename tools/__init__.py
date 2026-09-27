"""
AutoKafka 工具集
"""

from .weixin_collector import WeixinCollector, collect_weixin_articles
from .redbook_collector import RedbookCollector, collect_redbook_notes
from .research_analyzer import (
    ResearchAnalyzer,
    ResearchReport,
    ConsensusLevel,
    create_research_report
)
from .layout_engine import LayoutEngine, generate_layout, IllustrationType, LengthTier
from .prompt_generator import PromptGenerator, generate_image_prompts
from .batch_image_generator import (
    GeminiImageGenerator,
    MockImageGenerator,
    generate_images
)

__all__ = [
    # 采集器
    'WeixinCollector',
    'collect_weixin_articles',
    'RedbookCollector',
    'collect_redbook_notes',

    # Research
    'ResearchAnalyzer',
    'ResearchReport',
    'ConsensusLevel',
    'create_research_report',

    # 编排
    'LayoutEngine',
    'generate_layout',
    'IllustrationType',
    'LengthTier',

    # Prompt
    'PromptGenerator',
    'generate_image_prompts',

    # 生图
    'GeminiImageGenerator',
    'MockImageGenerator',
    'generate_images',
]
