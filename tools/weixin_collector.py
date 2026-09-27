"""
微信公众号文章采集工具
基于 weixin_search_mcp 项目
"""

import sys
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

# 添加 weixin_search_mcp 到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'weixin_search_mcp'))

from weixin_search_mcp.tools.weixin_search import sogou_weixin_search, get_article_content


@dataclass
class WeixinArticle:
    """微信文章数据结构"""
    title: str
    url: str
    source: str
    publish_time: str
    content: str
    relevance_score: float = 0.0


class WeixinCollector:
    """微信公众号文章采集器"""

    # 可信公众号列表
    TRUSTED_SOURCES = [
        "机器之心", "量子位", "新智元", "AI前线",
        "硅星人", "极客公园", "少数派", "36氪",
        "虎嗅", "爱范儿", "雷科技", "差评"
    ]

    def __init__(self, months_limit: int = 3):
        """
        初始化采集器

        Args:
            months_limit: 时效限制（月）
        """
        self.months_limit = months_limit
        self.cutoff_date = datetime.now() - timedelta(days=months_limit * 30)

    def search(self, keyword: str, limit: int = 5) -> List[Dict]:
        """
        搜索公众号文章

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制

        Returns:
            搜索结果列表
        """
        try:
            results = sogou_weixin_search(keyword)
            return results[:limit] if results else []
        except Exception as e:
            print(f"搜索失败: {e}")
            return []

    def get_content(self, url: str, referer: str = None) -> str:
        """
        获取文章内容

        Args:
            url: 文章真实链接
            referer: 来源链接

        Returns:
            文章正文内容
        """
        try:
            return get_article_content(url, referer)
        except Exception as e:
            print(f"获取内容失败: {e}")
            return ""

    def _parse_publish_time(self, time_str: str) -> Optional[datetime]:
        """
        解析发布时间

        Args:
            time_str: 时间字符串（可能包含 JS 代码）

        Returns:
            datetime 对象
        """
        import re

        # 尝试提取时间戳
        match = re.search(r"timeConvert\('(\d+)'\)", time_str)
        if match:
            try:
                timestamp = int(match.group(1))
                return datetime.fromtimestamp(timestamp)
            except:
                pass

        return None

    def _calculate_relevance(self, article: Dict, core_keywords: List[str], refined_keywords: List[str]) -> float:
        """
        计算文章相关性得分

        Args:
            article: 文章信息
            core_keywords: 核心关键词
            refined_keywords: 细化关键词

        Returns:
            相关性得分
        """
        score = 0.0
        title = article.get('title', '').lower()

        # 标题命中核心词 +3
        for kw in core_keywords:
            if kw.lower() in title:
                score += 3

        # 标题命中细化词 +2
        for kw in refined_keywords:
            if kw.lower() in title:
                score += 2

        # 来源为可信源 +2
        # 注：搜狗搜索结果中可能没有公众号名称，需要从内容中提取

        return score

    def collect(
        self,
        core_keywords: List[str],
        refined_keywords: List[str] = None,
        core_limit: int = 5,
        refined_limit: int = 3
    ) -> List[WeixinArticle]:
        """
        采集文章

        Args:
            core_keywords: 核心关键词列表
            refined_keywords: 细化关键词列表
            core_limit: 核心关键词每个取 top N
            refined_limit: 细化关键词每个取 top N

        Returns:
            采集到的文章列表
        """
        all_articles = []
        seen_urls = set()

        # 采集核心关键词结果
        for kw in core_keywords:
            results = self.search(kw, limit=core_limit)
            for item in results:
                real_url = item.get('real_url', '')
                if real_url and real_url not in seen_urls:
                    seen_urls.add(real_url)

                    # 获取内容
                    content = self.get_content(real_url, item.get('link'))

                    # 计算相关性
                    score = self._calculate_relevance(
                        item,
                        core_keywords,
                        refined_keywords or []
                    )

                    article = WeixinArticle(
                        title=item.get('title', ''),
                        url=real_url,
                        source='公众号',
                        publish_time=item.get('publish_time', ''),
                        content=content,
                        relevance_score=score
                    )
                    all_articles.append(article)

        # 采集细化关键词结果
        if refined_keywords:
            for kw in refined_keywords:
                results = self.search(kw, limit=refined_limit)
                for item in results:
                    real_url = item.get('real_url', '')
                    if real_url and real_url not in seen_urls:
                        seen_urls.add(real_url)

                        content = self.get_content(real_url, item.get('link'))
                        score = self._calculate_relevance(
                            item,
                            core_keywords,
                            refined_keywords
                        )

                        article = WeixinArticle(
                            title=item.get('title', ''),
                            url=real_url,
                            source='公众号',
                            publish_time=item.get('publish_time', ''),
                            content=content,
                            relevance_score=score
                        )
                        all_articles.append(article)

        # 按相关性排序
        all_articles.sort(key=lambda x: x.relevance_score, reverse=True)

        return all_articles

    def to_dict_list(self, articles: List[WeixinArticle]) -> List[Dict]:
        """
        转换为字典列表

        Args:
            articles: 文章列表

        Returns:
            字典列表
        """
        return [
            {
                'title': a.title,
                'url': a.url,
                'source': a.source,
                'publish_time': a.publish_time,
                'content': a.content[:500] + '...' if len(a.content) > 500 else a.content,
                'content_full': a.content,
                'relevance_score': a.relevance_score
            }
            for a in articles
        ]


# 便捷函数
def collect_weixin_articles(
    core_keywords: List[str],
    refined_keywords: List[str] = None,
    core_limit: int = 5,
    refined_limit: int = 3
) -> List[Dict]:
    """
    采集微信公众号文章（便捷函数）

    Args:
        core_keywords: 核心关键词
        refined_keywords: 细化关键词
        core_limit: 核心词每个取 top N
        refined_limit: 细化词每个取 top N

    Returns:
        文章列表
    """
    collector = WeixinCollector()
    articles = collector.collect(
        core_keywords=core_keywords,
        refined_keywords=refined_keywords,
        core_limit=core_limit,
        refined_limit=refined_limit
    )
    return collector.to_dict_list(articles)


if __name__ == "__main__":
    # 测试
    articles = collect_weixin_articles(
        core_keywords=["Claude Skills"],
        refined_keywords=["Claude Skills 教程", "Claude Skills 入门"],
        core_limit=3,
        refined_limit=2
    )

    print(f"采集到 {len(articles)} 篇文章:\n")
    for i, a in enumerate(articles, 1):
        print(f"{i}. {a['title']}")
        print(f"   相关性: {a['relevance_score']}")
        print(f"   链接: {a['url'][:60]}...")
        print()
