#!/usr/bin/env python3
"""
多源搜索工具
整合微信公众号搜索和小红书搜索

使用方法:
    # 微信公众号搜索
    python3 multi_source_search.py weixin "关键词" --limit 5

    # 小红书搜索
    python3 multi_source_search.py redbook "关键词" --limit 5

    # 全部搜索
    python3 multi_source_search.py all "关键词" --limit 5
"""

import sys
import os
import json
import argparse
from typing import List, Dict
from dataclasses import dataclass, asdict

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'weixin_search_mcp'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'redbook_mcp'))
sys.path.insert(0, TOOLS_DIR)  # 添加当前目录以导入 redbook_collector


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    source: str  # 'weixin' | 'redbook' | 'web'
    snippet: str = ""
    publish_time: str = ""
    author: str = ""


def search_weixin(keyword: str, limit: int = 5) -> List[Dict]:
    """
    搜索微信公众号文章

    Args:
        keyword: 搜索关键词
        limit: 返回数量限制

    Returns:
        搜索结果列表
    """
    try:
        from weixin_search_mcp.tools.weixin_search import sogou_weixin_search

        results = sogou_weixin_search(keyword)

        formatted_results = []
        for item in results[:limit]:
            result = SearchResult(
                title=item.get('title', ''),
                url=item.get('real_url', '') or item.get('link', ''),
                source='weixin',
                publish_time=item.get('publish_time', ''),
                snippet=item.get('title', '')[:100]
            )
            formatted_results.append(asdict(result))

        return formatted_results

    except ImportError as e:
        print(f"[错误] 无法导入微信搜索模块: {e}", file=sys.stderr)
        print("[提示] 请确保在项目虚拟环境中运行", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[错误] 微信搜索失败: {e}", file=sys.stderr)
        return []


def search_redbook(keyword: str, limit: int = 5) -> List[Dict]:
    """
    搜索小红书笔记（带相关性筛选）

    搜索流程：
    1. 扩大搜索池（搜索 limit * 4 条）
    2. 获取笔记正文内容
    3. 计算与关键词的相关性得分
    4. 按相关性排序，返回 top N

    Args:
        keyword: 搜索关键词（完整主题词）
        limit: 最终返回数量

    Returns:
        搜索结果列表（按相关性排序）
    """
    try:
        # 使用 redbook_collector.py 中的采集器
        from redbook_collector import collect_redbook_notes

        print(f"[小红书] 搜索关键词: {keyword}", file=sys.stderr)

        # 扩大搜索池：搜索 4 倍数量，以便筛选
        search_pool_size = limit * 4
        print(f"[小红书] 搜索池大小: {search_pool_size} 条", file=sys.stderr)

        # 调用采集器，获取正文内容用于相关性计算
        notes = collect_redbook_notes(
            core_keywords=[keyword],
            core_limit=search_pool_size,
            fetch_content=True  # 获取正文内容，用于相关性计算
        )

        print(f"[小红书] 获取到 {len(notes)} 条笔记", file=sys.stderr)

        if not notes:
            return []

        # 计算相关性得分（基于关键词匹配）
        # 中文分词：按字符拆分关键词，提取核心词
        keyword_lower = keyword.lower()
        # 提取可能的核心词（2-4字的组合）
        keyword_parts = []
        if len(keyword) >= 2:
            # 添加完整关键词
            keyword_parts.append(keyword_lower)
            # 添加2字组合
            for i in range(len(keyword) - 1):
                keyword_parts.append(keyword[i:i+2].lower())
            # 添加3字组合
            for i in range(len(keyword) - 2):
                keyword_parts.append(keyword[i:i+3].lower())
            # 添加常见核心词
            core_words = ['电脑', '发展', '历史', '发展史', '进化', '演变', '个人电脑', 'PC', 'mac', '计算机']
            keyword_parts.extend([w.lower() for w in core_words])

        for note in notes:
            title = note.get('title', '').lower()
            content = note.get('content_full', note.get('content', '')).lower()
            score = note.get('relevance_score', 0)

            # 额外的相关性计算
            for kw in keyword_parts:
                if len(kw) >= 2:  # 只考虑2字以上的词
                    if kw in title:
                        score += 5  # 标题匹配 +5
                    if kw in content:
                        score += 2  # 正文匹配 +2

            # 标题长度惩罚（太短的标题可能不够具体）
            if len(note.get('title', '')) < 10:
                score -= 2

            note['final_score'] = score

        # 按相关性得分排序
        notes.sort(key=lambda x: x.get('final_score', 0), reverse=True)

        # 只保留得分 > 0 的结果
        relevant_notes = [n for n in notes if n.get('final_score', 0) > 0]

        print(f"[小红书] 相关性筛选后: {len(relevant_notes)} 条", file=sys.stderr)

        # 如果相关性筛选后结果太少，放宽条件
        if len(relevant_notes) < limit:
            relevant_notes = notes[:limit]
            print(f"[小红书] 相关结果不足，使用前 {limit} 条", file=sys.stderr)
        else:
            relevant_notes = relevant_notes[:limit]

        # 转换为统一格式
        results = []
        for note in relevant_notes:
            result = SearchResult(
                title=note.get('title', ''),
                url=note.get('url', ''),
                source='redbook',
                author=note.get('author', ''),
                snippet=note.get('content', '')[:200] if note.get('content') else note.get('title', '')[:100]
            )
            results.append(asdict(result))
            print(f"[小红书] 筛选结果: {note.get('title', '')[:40]}... (得分: {note.get('final_score', 0)})", file=sys.stderr)

        return results

    except ImportError as e:
        print(f"[错误] 无法导入小红书搜索模块: {e}", file=sys.stderr)
        print("[提示] 请确保 playwright 已安装: pip install playwright && playwright install chromium", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[错误] 小红书搜索失败: {e}", file=sys.stderr)
        return []


def search_all(keyword: str, limit: int = 5) -> Dict[str, List[Dict]]:
    """
    执行全部搜索

    Args:
        keyword: 搜索关键词
        limit: 每个来源的返回数量限制

    Returns:
        包含各来源搜索结果的字典
    """
    results = {
        'weixin': [],
        'redbook': [],
        'summary': {
            'keyword': keyword,
            'total': 0,
            'weixin_count': 0,
            'redbook_count': 0
        }
    }

    # 微信搜索
    print(f"[搜索] 微信公众号: {keyword}", file=sys.stderr)
    weixin_results = search_weixin(keyword, limit)
    results['weixin'] = weixin_results
    results['summary']['weixin_count'] = len(weixin_results)

    # 小红书搜索
    print(f"[搜索] 小红书: {keyword}", file=sys.stderr)
    redbook_results = search_redbook(keyword, limit)
    results['redbook'] = redbook_results
    results['summary']['redbook_count'] = len(redbook_results)

    results['summary']['total'] = len(weixin_results) + len(redbook_results)

    return results


def main():
    parser = argparse.ArgumentParser(description='多源搜索工具')
    parser.add_argument('source', choices=['weixin', 'redbook', 'all'],
                        help='搜索来源: weixin(微信公众号), redbook(小红书), all(全部)')
    parser.add_argument('keyword', help='搜索关键词')
    parser.add_argument('--limit', '-l', type=int, default=5,
                        help='返回数量限制 (默认: 5)')
    parser.add_argument('--format', '-f', choices=['json', 'text'], default='json',
                        help='输出格式 (默认: json)')

    args = parser.parse_args()

    # 执行搜索
    if args.source == 'weixin':
        results = search_weixin(args.keyword, args.limit)
    elif args.source == 'redbook':
        results = search_redbook(args.keyword, args.limit)
    else:
        results = search_all(args.keyword, args.limit)

    # 输出结果
    if args.format == 'json':
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        # 文本格式输出
        if args.source == 'all':
            print(f"\n=== 搜索结果: {args.keyword} ===\n")
            print(f"【微信公众号】({len(results.get('weixin', []))}条)")
            for i, r in enumerate(results.get('weixin', []), 1):
                print(f"  {i}. {r['title']}")
                print(f"     {r['url'][:60]}...")

            print(f"\n【小红书】({len(results.get('redbook', []))}条)")
            for i, r in enumerate(results.get('redbook', []), 1):
                print(f"  {i}. {r['title']}")
                print(f"     {r['url'][:60]}...")
        else:
            print(f"\n=== {args.source} 搜索结果: {args.keyword} ===\n")
            for i, r in enumerate(results, 1):
                print(f"{i}. {r['title']}")
                print(f"   链接: {r['url'][:60]}...")
                if r.get('publish_time'):
                    print(f"   时间: {r['publish_time']}")
                print()


if __name__ == '__main__':
    main()
