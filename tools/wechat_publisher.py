"""
微信公众号草稿箱发布工具
将 AutoKafka 生成的文章发布到公众号草稿箱
"""

import os
import re
import json
import time
import sys
import requests
from typing import Dict, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PublishResult:
    """发布结果"""
    success: bool
    media_id: Optional[str] = None
    error: Optional[str] = None


class WeChatPublisher:
    """微信公众号发布器"""

    BASE_URL = "https://api.weixin.qq.com/cgi-bin"

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.appid = self.config.get('WECHAT_APPID', '')
        self.appsecret = self.config.get('WECHAT_APPSECRET', '')
        self.proxies = {}

        if not self.appid or not self.appsecret:
            print("[WeChatPublisher] 警告: 微信公众号配置缺失")
        else:
            print(f"[WeChatPublisher] 已配置，AppID: {self.appid[:10]}...")

        self._token_cache_path = Path(__file__).parent / '.wechat_token_cache.json'

    def _load_config(self, config_path: str = None) -> Dict:
        """加载配置文件"""
        if config_path is None:
            project_root = Path(__file__).parent.parent.parent.parent.parent
            config_path = project_root / 'config.env'

        if not os.path.exists(config_path):
            print(f"[WeChatPublisher] 配置文件不存在: {config_path}")
            return {}

        try:
            config = {}
            with open(config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip().strip('"\'')
            return config
        except Exception as e:
            print(f"[WeChatPublisher] 加载配置失败: {e}")
            return {}

    # ---- Access Token ----

    def get_access_token(self) -> Optional[str]:
        """获取 access_token，带本地文件缓存（有效期 2 小时）"""
        # 读缓存
        if self._token_cache_path.exists():
            try:
                with open(self._token_cache_path, 'r') as f:
                    cache = json.load(f)
                if cache.get('expires_at', 0) > time.time() + 60:
                    return cache['access_token']
            except Exception:
                pass

        # 请求新 token
        url = f"{self.BASE_URL}/token"
        params = {
            'grant_type': 'client_credential',
            'appid': self.appid,
            'secret': self.appsecret
        }

        try:
            resp = requests.get(url, params=params, proxies=self.proxies, timeout=10)
            data = resp.json()

            if 'access_token' in data:
                cache = {
                    'access_token': data['access_token'],
                    'expires_at': time.time() + data.get('expires_in', 7200)
                }
                with open(self._token_cache_path, 'w') as f:
                    json.dump(cache, f)
                print("[WeChatPublisher] access_token 获取成功")
                return data['access_token']
            else:
                print(f"[WeChatPublisher] 获取 token 失败: {data}")
                return None
        except Exception as e:
            print(f"[WeChatPublisher] 请求 token 异常: {e}")
            return None

    # ---- Image Upload ----

    def upload_thumb(self, image_path: str) -> Optional[str]:
        """上传封面图（永久素材），返回 media_id"""
        token = self.get_access_token()
        if not token:
            return None

        url = f"{self.BASE_URL}/material/add_material"
        params = {'access_token': token, 'type': 'thumb'}

        try:
            with open(image_path, 'rb') as f:
                files = {'media': (Path(image_path).name, f, 'image/jpeg')}
                resp = requests.post(url, params=params, files=files, proxies=self.proxies, timeout=30)
                data = resp.json()

            if 'media_id' in data:
                print(f"[WeChatPublisher] 封面上传成功: {data['media_id']}")
                return data['media_id']
            else:
                print(f"[WeChatPublisher] 封面上传失败: {data}")
                return None
        except Exception as e:
            print(f"[WeChatPublisher] 封面上传异常: {e}")
            return None

    def upload_content_image(self, image_path: str) -> Optional[str]:
        """上传正文图片，返回微信 CDN URL"""
        token = self.get_access_token()
        if not token:
            return None

        url = f"{self.BASE_URL}/media/uploadimg"
        params = {'access_token': token}

        try:
            with open(image_path, 'rb') as f:
                files = {'media': (Path(image_path).name, f, 'image/png')}
                resp = requests.post(url, params=params, files=files, proxies=self.proxies, timeout=30)
                data = resp.json()

            if 'url' in data:
                print(f"[WeChatPublisher] 正文图片上传成功: {Path(image_path).name}")
                return data['url']
            else:
                print(f"[WeChatPublisher] 正文图片上传失败: {data}")
                return None
        except Exception as e:
            print(f"[WeChatPublisher] 正文图片上传异常: {e}")
            return None

    # ---- Markdown → WeChat HTML ----

    def markdown_to_wechat_html(self, markdown_text: str) -> str:
        """将 Markdown 转为微信公众号兼容的内联样式 HTML"""
        html = markdown_text

        # 清除 AutoKafka 颜色标注
        html = re.sub(r'🟡\s*HOOK\s*', '', html)
        html = re.sub(r'🟢\s*GOLDEN\s*', '', html)
        html = re.sub(r'🔵\s*ANALOGY\s*', '', html)
        html = re.sub(r'🟣\s*CLOSE\s*', '', html)
        html = re.sub(r'🔴\s*NEED_VERIFY\s*', '', html)
        html = re.sub(r'🟠\s*AI_SMELL\s*', '', html)

        # 代码块（先处理，避免被其他规则干扰）
        html = re.sub(
            r'```\w*\n(.*?)```',
            r'<pre style="background:#f8f8f8;padding:16px;border-radius:4px;overflow-x:auto;font-size:13px;line-height:1.6;"><code>\1</code></pre>',
            html, flags=re.DOTALL
        )

        # 标题
        html = re.sub(
            r'^### (.+)$',
            r'<h3 style="font-size:17px;font-weight:bold;color:#333;margin:24px 0 12px;">\1</h3>',
            html, flags=re.MULTILINE
        )
        html = re.sub(
            r'^## (.+)$',
            r'<h2 style="font-size:20px;font-weight:bold;color:#1a1a1a;margin:32px 0 16px;border-left:4px solid #333;padding-left:12px;">\1</h2>',
            html, flags=re.MULTILINE
        )
        html = re.sub(
            r'^# (.+)$',
            r'<h1 style="font-size:24px;font-weight:bold;color:#1a1a1a;margin:0 0 20px;text-align:center;">\1</h1>',
            html, flags=re.MULTILINE
        )

        # 粗体 / 斜体
        html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

        # 行内代码
        html = re.sub(
            r'`([^`]+)`',
            r'<code style="background:#f5f5f5;padding:2px 6px;border-radius:3px;font-size:14px;color:#c7254e;">\1</code>',
            html
        )

        # 图片占位符 → <img> 标签（src 留空，后续替换）
        html = re.sub(
            r'📍\s*\[插图：(\w+)\s*-\s*([^\]]+)\]',
            r'<p style="text-align:center;margin:20px 0;">'
            r'<img data-image-id="\1" src="" alt="\2" style="max-width:100%;border-radius:4px;" />'
            r'<br/><span style="font-size:12px;color:#999;">\2</span></p>',
            html
        )

        # 无序列表
        html = re.sub(
            r'^- (.+)$',
            r'<li style="margin:4px 0;line-height:1.8;">\1</li>',
            html, flags=re.MULTILINE
        )
        html = re.sub(
            r'((?:<li[^>]*>.*?</li>\n?)+)',
            r'<ul style="padding-left:24px;margin:12px 0;">\1</ul>',
            html
        )

        # 分隔线
        html = re.sub(r'^---+$', r'<hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />', html, flags=re.MULTILINE)

        # 普通段落：非空行且非 HTML 标签开头的行
        lines = html.split('\n')
        result = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                result.append('')
            elif stripped.startswith('<'):
                result.append(line)
            else:
                result.append(f'<p style="margin:12px 0;line-height:1.8;font-size:16px;color:#333;">{stripped}</p>')

        html = '\n'.join(result)
        html = re.sub(r'\n{3,}', '\n\n', html)
        return html

    def _replace_images(self, html: str, image_map: Dict[str, str]) -> str:
        """替换 HTML 中的图片占位符为实际微信 CDN URL"""
        for image_id, url in image_map.items():
            html = html.replace(f'data-image-id="{image_id}" src=""', f'src="{url}"')
        return html

    # ---- Draft Creation ----

    def create_draft(
        self,
        title: str,
        content_html: str,
        thumb_media_id: str,
        author: str = "",
        digest: str = "",
    ) -> PublishResult:
        """创建草稿箱文章"""
        token = self.get_access_token()
        if not token:
            return PublishResult(success=False, error="获取 access_token 失败")

        url = f"{self.BASE_URL}/draft/add"
        params = {'access_token': token}

        article = {
            "title": title,
            "author": author,
            "content": content_html,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
        }
        if digest:
            article["digest"] = digest

        payload = {"articles": [article]}

        try:
            # 必须用 ensure_ascii=False，否则中文标题被转义后超长度限制
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            headers = {'Content-Type': 'application/json; charset=utf-8'}
            resp = requests.post(url, params=params, data=body, headers=headers, proxies=self.proxies, timeout=30)
            data = resp.json()

            if 'media_id' in data:
                print(f"[WeChatPublisher] 草稿创建成功: {data['media_id']}")
                return PublishResult(success=True, media_id=data['media_id'])
            else:
                print(f"[WeChatPublisher] 草稿创建失败: {data}")
                return PublishResult(success=False, error=json.dumps(data, ensure_ascii=False))
        except Exception as e:
            print(f"[WeChatPublisher] 草稿创建异常: {e}")
            return PublishResult(success=False, error=str(e))

    # ---- High-level API ----

    def publish_article(
        self,
        title: str,
        markdown_content: str,
        cover_image_path: str,
        content_images: Dict[str, str] = None,
        author: str = "",
        digest: str = "",
    ) -> PublishResult:
        """
        完整发布流程

        Args:
            title: 文章标题
            markdown_content: Markdown 正文（AutoKafka 产出）
            cover_image_path: 封面图本地路径
            content_images: {image_id: 本地路径} 正文插图映射
            author: 作者名
            digest: 摘要（空则由微信自动截取前54字）
        """
        print(f"\n[WeChatPublisher] === 开始发布: {title} ===")

        # 1. 上传封面
        print("[WeChatPublisher] [1/4] 上传封面图...")
        thumb_id = self.upload_thumb(cover_image_path)
        if not thumb_id:
            return PublishResult(success=False, error="封面图上传失败")

        # 2. Markdown → HTML
        print("[WeChatPublisher] [2/4] 转换正文 Markdown → HTML...")
        html = self.markdown_to_wechat_html(markdown_content)

        # 3. 上传正文图片并替换占位符
        if content_images:
            print(f"[WeChatPublisher] [3/4] 上传 {len(content_images)} 张正文图片...")
            url_map = {}
            for img_id, img_path in content_images.items():
                if not os.path.exists(img_path):
                    print(f"[WeChatPublisher] 图片不存在，跳过: {img_path}")
                    continue
                url = self.upload_content_image(img_path)
                if url:
                    url_map[img_id] = url
                time.sleep(0.5)  # 避免请求过快
            html = self._replace_images(html, url_map)
            print(f"[WeChatPublisher] 成功上传 {len(url_map)}/{len(content_images)} 张")
        else:
            print("[WeChatPublisher] [3/4] 无正文图片，跳过")

        # 4. 创建草稿
        print("[WeChatPublisher] [4/4] 创建草稿...")
        result = self.create_draft(
            title=title,
            content_html=html,
            thumb_media_id=thumb_id,
            author=author,
            digest=digest,
        )

        if result.success:
            print(f"[WeChatPublisher] === 发布完成！草稿 media_id: {result.media_id} ===\n")
        else:
            print(f"[WeChatPublisher] === 发布失败: {result.error} ===\n")

        return result


# ---- CLI ----

def main():
    usage = """微信公众号草稿箱发布工具

用法:
  wechat_publisher.py test                                # 测试 access_token
  wechat_publisher.py publish <title> <md_file> <cover>   # 发布到草稿箱

示例:
  .venv/bin/python3 .claude/skills/autokafka/tools/wechat_publisher.py test
  .venv/bin/python3 .claude/skills/autokafka/tools/wechat_publisher.py publish "文章标题" article.md cover.jpg
"""
    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)

    cmd = sys.argv[1]
    publisher = WeChatPublisher()

    if cmd == 'test':
        token = publisher.get_access_token()
        if token:
            print(f"\n✅ access_token 获取成功: {token[:20]}...")
        else:
            print("\n❌ access_token 获取失败，请检查 AppID / AppSecret / IP白名单")

    elif cmd == 'publish':
        if len(sys.argv) < 5:
            print("用法: wechat_publisher.py publish <title> <md_file> <cover_image>")
            sys.exit(1)

        title = sys.argv[2]
        md_file = sys.argv[3]
        cover = sys.argv[4]

        if not os.path.exists(md_file):
            print(f"❌ 文件不存在: {md_file}")
            sys.exit(1)
        if not os.path.exists(cover):
            print(f"❌ 封面图不存在: {cover}")
            sys.exit(1)

        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()

        result = publisher.publish_article(
            title=title,
            markdown_content=content,
            cover_image_path=cover,
        )

        sys.exit(0 if result.success else 1)

    else:
        print(usage)
        sys.exit(1)


if __name__ == '__main__':
    main()
