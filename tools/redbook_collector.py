"""
小红书笔记采集工具
基于 redbook_mcp 项目（Playwright 浏览器自动化）
"""

import asyncio
import os
import sys
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

# Playwright 相关
from playwright.async_api import async_playwright

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


@dataclass
class RedbookNote:
    """小红书笔记数据结构"""
    title: str
    url: str
    author: str
    content: str
    publish_time: str
    relevance_score: float = 0.0


class RedbookCollector:
    """小红书笔记采集器"""

    BROWSER_DATA_DIR = os.path.join(PROJECT_ROOT, 'redbook_mcp', 'browser_data')

    def __init__(self, months_limit: int = 3):
        """
        初始化采集器

        Args:
            months_limit: 时效限制（月）
        """
        self.months_limit = months_limit
        self.browser_context = None
        self.page = None
        self.is_logged_in = False

        # 确保目录存在
        os.makedirs(self.BROWSER_DATA_DIR, exist_ok=True)

    async def _ensure_browser(self) -> bool:
        """
        确保浏览器已启动并登录

        Returns:
            是否已登录
        """
        if self.browser_context is None:
            playwright_instance = await async_playwright().start()

            self.browser_context = await playwright_instance.chromium.launch_persistent_context(
                user_data_dir=self.BROWSER_DATA_DIR,
                headless=False,
                viewport={"width": 1280, "height": 800},
                timeout=60000
            )

            if self.browser_context.pages:
                self.page = self.browser_context.pages[0]
            else:
                self.page = await self.browser_context.new_page()

            self.page.set_default_timeout(60000)

        # 检查登录状态
        if not self.is_logged_in:
            await self.page.goto("https://www.xiaohongshu.com", timeout=60000)
            await asyncio.sleep(3)

            login_elements = await self.page.query_selector_all('text="登录"')
            if login_elements:
                print("需要登录小红书，请在浏览器窗口扫码登录...")
                print("等待登录完成（最多180秒）...")

                max_wait = 180
                waited = 0
                while waited < max_wait:
                    still_login = await self.page.query_selector_all('text="登录"')
                    if not still_login:
                        print("登录成功！")
                        self.is_logged_in = True
                        break
                    await asyncio.sleep(5)
                    waited += 5

                if not self.is_logged_in:
                    print("登录超时")
                    return False
            else:
                self.is_logged_in = True

        return True

    async def search(self, keyword: str, limit: int = 5) -> List[Dict]:
        """
        搜索小红书笔记

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制

        Returns:
            搜索结果列表
        """
        if not await self._ensure_browser():
            return []

        search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}"
        await self.page.goto(search_url, timeout=60000)
        await asyncio.sleep(5)

        # 获取帖子卡片
        post_cards = await self.page.query_selector_all('section.note-item')

        if not post_cards:
            # 尝试备用选择器
            post_cards = await self.page.query_selector_all('div[data-v-a264b01a]')

        results = []
        for card in post_cards[:limit]:
            try:
                # 获取标题
                title_el = await card.query_selector('a.title span')
                title = await title_el.text_content() if title_el else "未知标题"

                # 获取链接
                link_el = await card.query_selector('a[href*="/search_result/"]')
                href = await link_el.get_attribute('href') if link_el else None
                url = f"https://www.xiaohongshu.com{href}" if href and href.startswith('/') else href

                # 获取作者
                author_el = await card.query_selector('span.name')
                author = await author_el.text_content() if author_el else "未知作者"

                results.append({
                    'title': title.strip() if title else '',
                    'url': url,
                    'author': author.strip() if author else ''
                })

            except Exception as e:
                print(f"解析笔记失败: {e}")

        return results

    async def get_note_content(self, url: str) -> Dict:
        """
        获取笔记详细内容

        Args:
            url: 笔记链接

        Returns:
            笔记详情
        """
        if not await self._ensure_browser():
            return {}

        try:
            await self.page.goto(url, timeout=60000)
            await asyncio.sleep(3)

            # 获取标题
            title_el = await self.page.query_selector('div.title')
            title = await title_el.text_content() if title_el else ""

            # 获取正文
            content_el = await self.page.query_selector('div.desc')
            content = await content_el.text_content() if content_el else ""

            # 获取作者
            author_el = await self.page.query_selector('span.username')
            author = await author_el.text_content() if author_el else ""

            # 获取发布时间
            time_el = await self.page.query_selector('span.date')
            publish_time = await time_el.text_content() if time_el else ""

            return {
                'title': title.strip() if title else '',
                'content': content.strip() if content else '',
                'author': author.strip() if author else '',
                'publish_time': publish_time.strip() if publish_time else '',
                'url': url
            }

        except Exception as e:
            print(f"获取笔记内容失败: {e}")
            return {}

    def _calculate_relevance(self, note: Dict, core_keywords: List[str], refined_keywords: List[str]) -> float:
        """
        计算笔记相关性得分

        Args:
            note: 笔记信息
            core_keywords: 核心关键词
            refined_keywords: 细化关键词

        Returns:
            相关性得分
        """
        score = 0.0
        title = note.get('title', '').lower()
        content = note.get('content', '').lower()

        # 标题命中核心词 +3
        for kw in core_keywords:
            if kw.lower() in title:
                score += 3

        # 标题命中细化词 +2
        for kw in refined_keywords:
            if kw.lower() in title:
                score += 2

        # 正文命中核心词 +1
        for kw in core_keywords:
            if kw.lower() in content:
                score += 1

        return score

    async def collect(
        self,
        core_keywords: List[str],
        refined_keywords: List[str] = None,
        core_limit: int = 5,
        refined_limit: int = 3,
        fetch_content: bool = True
    ) -> List[RedbookNote]:
        """
        采集笔记

        Args:
            core_keywords: 核心关键词列表
            refined_keywords: 细化关键词列表
            core_limit: 核心关键词每个取 top N
            refined_limit: 细化关键词每个取 top N
            fetch_content: 是否获取详细内容

        Returns:
            采集到的笔记列表
        """
        all_notes = []
        seen_urls = set()

        # 采集核心关键词结果
        for kw in core_keywords:
            results = await self.search(kw, limit=core_limit)
            for item in results:
                url = item.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)

                    # 获取详细内容
                    if fetch_content:
                        detail = await self.get_note_content(url)
                        content = detail.get('content', '')
                        publish_time = detail.get('publish_time', '')
                    else:
                        content = ''
                        publish_time = ''

                    # 计算相关性
                    score = self._calculate_relevance(
                        {'title': item.get('title', ''), 'content': content},
                        core_keywords,
                        refined_keywords or []
                    )

                    note = RedbookNote(
                        title=item.get('title', ''),
                        url=url,
                        author=item.get('author', ''),
                        content=content,
                        publish_time=publish_time,
                        relevance_score=score
                    )
                    all_notes.append(note)

        # 采集细化关键词结果
        if refined_keywords:
            for kw in refined_keywords:
                results = await self.search(kw, limit=refined_limit)
                for item in results:
                    url = item.get('url', '')
                    if url and url not in seen_urls:
                        seen_urls.add(url)

                        if fetch_content:
                            detail = await self.get_note_content(url)
                            content = detail.get('content', '')
                            publish_time = detail.get('publish_time', '')
                        else:
                            content = ''
                            publish_time = ''

                        score = self._calculate_relevance(
                            {'title': item.get('title', ''), 'content': content},
                            core_keywords,
                            refined_keywords
                        )

                        note = RedbookNote(
                            title=item.get('title', ''),
                            url=url,
                            author=item.get('author', ''),
                            content=content,
                            publish_time=publish_time,
                            relevance_score=score
                        )
                        all_notes.append(note)

        # 按相关性排序
        all_notes.sort(key=lambda x: x.relevance_score, reverse=True)

        return all_notes

    async def close(self):
        """关闭浏览器"""
        if self.browser_context:
            await self.browser_context.close()
            self.browser_context = None
            self.page = None
            self.is_logged_in = False

    def to_dict_list(self, notes: List[RedbookNote]) -> List[Dict]:
        """
        转换为字典列表

        Args:
            notes: 笔记列表

        Returns:
            字典列表
        """
        return [
            {
                'title': n.title,
                'url': n.url,
                'author': n.author,
                'source': '小红书',
                'publish_time': n.publish_time,
                'content': n.content[:500] + '...' if len(n.content) > 500 else n.content,
                'content_full': n.content,
                'relevance_score': n.relevance_score
            }
            for n in notes
        ]


# 便捷函数（同步包装）
def collect_redbook_notes(
    core_keywords: List[str],
    refined_keywords: List[str] = None,
    core_limit: int = 5,
    refined_limit: int = 3,
    fetch_content: bool = True
) -> List[Dict]:
    """
    采集小红书笔记（便捷函数，同步）

    Args:
        core_keywords: 核心关键词
        refined_keywords: 细化关键词
        core_limit: 核心词每个取 top N
        refined_limit: 细化词每个取 top N
        fetch_content: 是否获取详细内容

    Returns:
        笔记列表
    """
    async def _collect():
        collector = RedbookCollector()
        try:
            notes = await collector.collect(
                core_keywords=core_keywords,
                refined_keywords=refined_keywords,
                core_limit=core_limit,
                refined_limit=refined_limit,
                fetch_content=fetch_content
            )
            return collector.to_dict_list(notes)
        finally:
            await collector.close()

    return asyncio.run(_collect())


if __name__ == "__main__":
    # 测试
    notes = collect_redbook_notes(
        core_keywords=["Claude AI"],
        refined_keywords=["Claude 教程"],
        core_limit=3,
        refined_limit=2,
        fetch_content=False  # 快速测试不获取详情
    )

    print(f"采集到 {len(notes)} 篇笔记:\n")
    for i, n in enumerate(notes, 1):
        print(f"{i}. {n['title']}")
        print(f"   作者: {n['author']}")
        print(f"   相关性: {n['relevance_score']}")
        print()
