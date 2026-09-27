"""
Research 分析器
对采集到的多源内容进行深度分析，生成 Research Report
"""

import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class ConsensusLevel(Enum):
    """共识度等级"""
    HIGH = 5       # 3+ 篇文章提到
    MEDIUM = 3     # 2 篇文章提到
    LOW = 2        # 仅 1 篇文章提到
    CONTROVERSIAL = 1  # 存在争议


@dataclass
class Insight:
    """洞察点"""
    content: str
    sources: List[int]  # 来源文章索引
    consensus_level: ConsensusLevel = ConsensusLevel.LOW
    is_controversial: bool = False
    conflicting_views: List[str] = field(default_factory=list)


@dataclass
class KnowledgeNode:
    """知识图谱节点"""
    concept: str
    definition: str = ""
    components: List[str] = field(default_factory=list)
    use_cases: List[str] = field(default_factory=list)
    related_concepts: List[str] = field(default_factory=list)
    common_misconceptions: List[str] = field(default_factory=list)


@dataclass
class SourceArticle:
    """源文章信息"""
    index: int
    title: str
    source_type: str  # 公众号 / 小红书 / Web
    source_name: str
    publish_time: str
    url: str
    citation_count: int = 0
    cited_in: List[str] = field(default_factory=list)  # 被哪些洞察引用


@dataclass
class ResearchReport:
    """Research 报告"""
    topic: str
    generated_at: str

    # 信息源统计
    source_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # 核心定义
    core_definition: str = ""
    definition_consensus: ConsensusLevel = ConsensusLevel.LOW

    # 关键洞察
    insights: List[Insight] = field(default_factory=list)

    # 知识图谱
    knowledge_graph: Optional[KnowledgeNode] = None

    # 争议点
    controversies: List[Dict[str, str]] = field(default_factory=list)

    # 源文章列表
    sources: List[SourceArticle] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        # 处理枚举
        data['definition_consensus'] = self.definition_consensus.name
        for insight in data['insights']:
            insight['consensus_level'] = ConsensusLevel(insight['consensus_level']).name
        return data

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        lines = []

        # 标题
        lines.append(f"# 📚 Deep Research Report")
        lines.append(f"**主题**: {self.topic}")
        lines.append(f"**生成时间**: {self.generated_at}")
        lines.append("")

        # 信息源概览
        lines.append("## 一、信息源概览")
        lines.append("")
        lines.append("| 采集源 | 采集数 | 有效数 | 时效内 |")
        lines.append("|--------|--------|--------|--------|")
        total = {'collected': 0, 'valid': 0, 'in_time': 0}
        for source, stats in self.source_stats.items():
            lines.append(f"| {source} | {stats.get('collected', 0)} | {stats.get('valid', 0)} | {stats.get('in_time', 0)} |")
            total['collected'] += stats.get('collected', 0)
            total['valid'] += stats.get('valid', 0)
            total['in_time'] += stats.get('in_time', 0)
        lines.append(f"| **合计** | {total['collected']} | {total['valid']} | {total['in_time']} |")
        lines.append("")

        # 核心定义
        lines.append("## 二、核心定义")
        lines.append("")
        consensus_stars = "★" * self.definition_consensus.value + "☆" * (5 - self.definition_consensus.value)
        lines.append(f"> {self.core_definition}")
        lines.append(f">")
        lines.append(f"> **共识度**: {consensus_stars}")
        lines.append("")

        # 关键洞察
        lines.append("## 三、关键洞察")
        lines.append("")
        for i, insight in enumerate(self.insights, 1):
            consensus_stars = "★" * insight.consensus_level.value + "☆" * (5 - insight.consensus_level.value)
            source_refs = ", ".join([f"[{s}]" for s in insight.sources])
            lines.append(f"### {i}. {insight.content}")
            lines.append(f"- **来源**: {source_refs}")
            lines.append(f"- **共识度**: {consensus_stars}")
            if insight.is_controversial:
                lines.append(f"- **⚠️ 存在争议**")
                for view in insight.conflicting_views:
                    lines.append(f"  - {view}")
            lines.append("")

        # 知识图谱
        if self.knowledge_graph:
            lines.append("## 四、知识图谱")
            lines.append("")
            kg = self.knowledge_graph
            lines.append(f"```")
            lines.append(f"{kg.concept}")
            if kg.definition:
                lines.append(f"├── 定义: {kg.definition}")
            if kg.components:
                lines.append(f"├── 组成: {', '.join(kg.components)}")
            if kg.use_cases:
                lines.append(f"├── 用途: {', '.join(kg.use_cases)}")
            if kg.related_concepts:
                lines.append(f"├── 相关概念: {', '.join(kg.related_concepts)}")
            if kg.common_misconceptions:
                lines.append(f"└── 常见误解: {', '.join(kg.common_misconceptions)}")
            lines.append(f"```")
            lines.append("")

        # 争议点
        if self.controversies:
            lines.append("## 五、争议/不确定点")
            lines.append("")
            for c in self.controversies:
                lines.append(f"- **{c.get('question', '')}**")
                lines.append(f"  {c.get('detail', '')}")
            lines.append("")

        # 源文章列表
        lines.append("## 六、源文章列表")
        lines.append("")
        for source in self.sources:
            cited_info = f"(引用 {source.citation_count} 次: {', '.join(source.cited_in)})" if source.citation_count > 0 else ""
            lines.append(f"**[{source.index}]** {source.title}")
            lines.append(f"- 来源: {source.source_type}·{source.source_name}")
            lines.append(f"- 日期: {source.publish_time}")
            lines.append(f"- 链接: {source.url}")
            if cited_info:
                lines.append(f"- {cited_info}")
            lines.append("")

        return "\n".join(lines)


class ResearchAnalyzer:
    """Research 分析器"""

    def __init__(self):
        self.articles: List[Dict] = []
        self.report: Optional[ResearchReport] = None

    def add_articles(self, articles: List[Dict], source_type: str):
        """
        添加文章到分析池

        Args:
            articles: 文章列表
            source_type: 来源类型（公众号/小红书/Web）
        """
        for article in articles:
            article['_source_type'] = source_type
            self.articles.append(article)

    def analyze(self, topic: str) -> ResearchReport:
        """
        执行分析，生成报告

        Args:
            topic: 研究主题

        Returns:
            Research 报告

        Note:
            这个方法提供了分析框架。实际的内容分析（提取洞察、
            构建知识图谱等）需要 Claude 来完成。这里主要处理
            数据结构和格式化。
        """
        self.report = ResearchReport(
            topic=topic,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
        )

        # 统计信息源
        self._calculate_source_stats()

        # 构建源文章列表
        self._build_source_list()

        return self.report

    def _calculate_source_stats(self):
        """计算信息源统计"""
        stats = {}

        for article in self.articles:
            source_type = article.get('_source_type', '未知')
            if source_type not in stats:
                stats[source_type] = {
                    'collected': 0,
                    'valid': 0,
                    'in_time': 0
                }

            stats[source_type]['collected'] += 1

            # 有内容则视为有效
            if article.get('content') or article.get('content_full'):
                stats[source_type]['valid'] += 1
                # 简化处理：有内容且有发布时间则视为时效内
                if article.get('publish_time'):
                    stats[source_type]['in_time'] += 1

        self.report.source_stats = stats

    def _build_source_list(self):
        """构建源文章列表"""
        sources = []

        for i, article in enumerate(self.articles, 1):
            source = SourceArticle(
                index=i,
                title=article.get('title', ''),
                source_type=article.get('_source_type', ''),
                source_name=article.get('source', article.get('author', '')),
                publish_time=article.get('publish_time', ''),
                url=article.get('url', ''),
                citation_count=0,
                cited_in=[]
            )
            sources.append(source)

        self.report.sources = sources

    def set_core_definition(self, definition: str, consensus: ConsensusLevel):
        """
        设置核心定义

        Args:
            definition: 定义内容
            consensus: 共识度
        """
        if self.report:
            self.report.core_definition = definition
            self.report.definition_consensus = consensus

    def add_insight(
        self,
        content: str,
        sources: List[int],
        is_controversial: bool = False,
        conflicting_views: List[str] = None
    ):
        """
        添加洞察

        Args:
            content: 洞察内容
            sources: 来源文章索引列表
            is_controversial: 是否有争议
            conflicting_views: 冲突观点列表
        """
        if not self.report:
            return

        # 根据来源数量确定共识度
        if len(sources) >= 3:
            consensus = ConsensusLevel.HIGH
        elif len(sources) == 2:
            consensus = ConsensusLevel.MEDIUM
        else:
            consensus = ConsensusLevel.LOW

        if is_controversial:
            consensus = ConsensusLevel.CONTROVERSIAL

        insight = Insight(
            content=content,
            sources=sources,
            consensus_level=consensus,
            is_controversial=is_controversial,
            conflicting_views=conflicting_views or []
        )
        self.report.insights.append(insight)

        # 更新源文章的引用信息
        for idx in sources:
            for source in self.report.sources:
                if source.index == idx:
                    source.citation_count += 1
                    source.cited_in.append(f"洞察{len(self.report.insights)}")

    def set_knowledge_graph(
        self,
        concept: str,
        definition: str = "",
        components: List[str] = None,
        use_cases: List[str] = None,
        related_concepts: List[str] = None,
        common_misconceptions: List[str] = None
    ):
        """
        设置知识图谱

        Args:
            concept: 核心概念
            definition: 定义
            components: 组成部分
            use_cases: 应用场景
            related_concepts: 相关概念
            common_misconceptions: 常见误解
        """
        if self.report:
            self.report.knowledge_graph = KnowledgeNode(
                concept=concept,
                definition=definition,
                components=components or [],
                use_cases=use_cases or [],
                related_concepts=related_concepts or [],
                common_misconceptions=common_misconceptions or []
            )

    def add_controversy(self, question: str, detail: str):
        """
        添加争议点

        Args:
            question: 争议问题
            detail: 详细说明
        """
        if self.report:
            self.report.controversies.append({
                'question': question,
                'detail': detail
            })

    def get_articles_for_analysis(self) -> List[Dict]:
        """
        获取用于分析的文章内容

        Returns:
            文章列表（含完整内容）
        """
        return [
            {
                'index': i,
                'title': a.get('title', ''),
                'source': a.get('_source_type', ''),
                'content': a.get('content_full', a.get('content', ''))
            }
            for i, a in enumerate(self.articles, 1)
        ]


# 便捷函数
def create_research_report(
    topic: str,
    weixin_articles: List[Dict] = None,
    redbook_notes: List[Dict] = None,
    web_results: List[Dict] = None
) -> Tuple[ResearchAnalyzer, str]:
    """
    创建 Research 报告（便捷函数）

    Args:
        topic: 研究主题
        weixin_articles: 公众号文章
        redbook_notes: 小红书笔记
        web_results: Web 搜索结果

    Returns:
        (分析器实例, 文章内容摘要)

    Note:
        返回分析器实例，以便后续调用 Claude 进行内容分析后
        补充洞察、知识图谱等信息
    """
    analyzer = ResearchAnalyzer()

    if weixin_articles:
        analyzer.add_articles(weixin_articles, '公众号')

    if redbook_notes:
        analyzer.add_articles(redbook_notes, '小红书')

    if web_results:
        analyzer.add_articles(web_results, 'Web')

    # 初始化报告框架
    analyzer.analyze(topic)

    # 获取文章摘要供 Claude 分析
    articles_summary = analyzer.get_articles_for_analysis()

    return analyzer, json.dumps(articles_summary, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 测试
    analyzer = ResearchAnalyzer()

    # 模拟添加文章
    analyzer.add_articles([
        {'title': '测试文章1', 'content': '内容1', 'url': 'http://example.com/1', 'publish_time': '2026-01-10'},
        {'title': '测试文章2', 'content': '内容2', 'url': 'http://example.com/2', 'publish_time': '2026-01-08'},
    ], '公众号')

    analyzer.add_articles([
        {'title': '测试笔记1', 'content': '内容3', 'url': 'http://xiaohongshu.com/1', 'author': '作者1'},
    ], '小红书')

    # 生成报告框架
    report = analyzer.analyze("测试主题")

    # 模拟 Claude 分析后补充信息
    analyzer.set_core_definition(
        "这是核心定义的描述...",
        ConsensusLevel.HIGH
    )

    analyzer.add_insight(
        "这是第一个洞察点",
        sources=[1, 2],
        is_controversial=False
    )

    analyzer.set_knowledge_graph(
        concept="测试主题",
        definition="定义",
        components=["组件1", "组件2"],
        use_cases=["用途1", "用途2"],
        related_concepts=["相关1", "相关2"],
        common_misconceptions=["误解1"]
    )

    # 输出 Markdown
    print(report.to_markdown())
