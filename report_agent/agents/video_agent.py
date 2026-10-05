# -*- coding: utf-8 -*-
"""
查询视频 Agent：根据用户提供的链接，尽力解析视频/帖子的信息。
支持策略：
1. 抖音链接：尝试 douyin-mcp 解析 + 分享页信息提取（可能受反爬限制）
2. 通用链接：尝试提取网页 og 元信息（标题/描述）
3. 兜底：解析失败时返回提示，引导用户手动粘贴文案
"""
import re
import requests
import logging

logger = logging.getLogger("video_agent")

UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


class VideoQueryAgent:
    """查询视频 Agent：输入链接 -> 输出结构化视频信息"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA})

    def query(self, link: str, manual_text: str = "") -> dict:
        """主入口：解析链接，返回视频信息；manual_text 为用户手动粘贴的文案兜底"""
        link = (link or "").strip()
        manual_text = (manual_text or "").strip()

        info = {"link": link, "title": "", "author": "", "desc": "", "platform": ""}
        if not link and not manual_text:
            return {"ok": False, "info": info, "msg": "请提供视频链接或粘贴视频文案"}

        # 1) 识别平台
        platform = self._detect_platform(link)
        info["platform"] = platform
        logger.info("platform=%s link=%s", platform, link[:60])

        # 2) 尝试自动解析
        parsed = False
        if link:
            if platform == "douyin":
                parsed = self._parse_douyin(link, info)
            else:
                parsed = self._parse_generic(link, info)

        # 3) 兜底：手动文案
        if manual_text:
            if not info["title"]:
                info["title"] = manual_text[:80]
            if not info["desc"]:
                info["desc"] = manual_text
            parsed = True

        if parsed and (info["title"] or info["desc"]):
            return {"ok": True, "info": info, "msg": "解析成功"}
        return {
            "ok": False,
            "info": info,
            "msg": "未能自动解析该链接（平台反爬或链接失效）。请在下方粘贴视频标题/文案/描述后重试。",
        }

    # ---------- 平台识别 ----------
    def _detect_platform(self, link: str) -> str:
        if not link:
            return ""
        if "douyin.com" in link or "iesdouyin.com" in link:
            return "douyin"
        if "bilibili.com" in link or "b23.tv" in link:
            return "bilibili"
        if "xiaohongshu.com" in link or "xhslink.com" in link:
            return "xiaohongshu"
        if "zhihu.com" in link:
            return "zhihu"
        if "weibo.com" in link or "weibo.cn" in link:
            return "weibo"
        return "other"

    # ---------- 抖音解析 ----------
    def _parse_douyin(self, link: str, info: dict) -> bool:
        """抖音：先取真实分享页，尝试 _ROUTER_DATA 与 og 信息；再尝试 douyin-mcp"""
        try:
            r = self.session.get(link, timeout=15, allow_redirects=True)
            url = r.url
            info["link"] = url
            html = r.text

            # a) og 元信息
            og_title = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', html)
            og_desc = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', html)
            if og_title:
                info["title"] = og_title.group(1).strip()
            if og_desc:
                info["desc"] = og_desc.group(1).strip()

            # b) _ROUTER_DATA 里的 itemId / 可能的描述
            m = re.search(r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", html, re.DOTALL)
            if m:
                import json
                try:
                    data = json.loads(m.group(1).strip())
                    page = data.get("loaderData", {}).get("video_(id)/page", {})
                    if page.get("itemId"):
                        info["video_id"] = str(page["itemId"])
                        info["link"] = f"https://www.douyin.com/video/{info['video_id']}"
                except Exception:
                    pass

            # c) 尝试 douyin-mcp 官方 API 解析（可能被风控）
            if not info["title"]:
                try:
                    from douyin_mcp.server import parse_douyin_share
                    result = parse_douyin_share(link)
                    mt = re.search(r"视频标题：(.+)", result)
                    ma = re.search(r"作者昵称：(.+)", result)
                    if mt:
                        info["title"] = mt.group(1).strip().replace("无描述", "")
                    if ma:
                        info["author"] = ma.group(1).strip()
                except Exception as e:
                    logger.info("douyin-mcp parse failed: %s", e)

            return bool(info["title"] or info["desc"])
        except Exception as e:
            logger.warning("douyin parse error: %s", e)
            return False

    # ---------- 通用解析（og 元信息） ----------
    def _parse_generic(self, link: str, info: dict) -> bool:
        try:
            r = self.session.get(link, timeout=15, allow_redirects=True)
            html = r.text
            og_title = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', html)
            og_desc = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', html)
            title_tag = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
            if og_title:
                info["title"] = og_title.group(1).strip()
            elif title_tag:
                info["title"] = title_tag.group(1).strip()[:120]
            if og_desc:
                info["desc"] = og_desc.group(1).strip()
            return bool(info["title"])
        except Exception as e:
            logger.warning("generic parse error: %s", e)
            return False
