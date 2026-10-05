# -*- coding: utf-8 -*-
"""
写理由 Agent：基于视频信息 + 平台规则，调用大模型生成贴合内容的举报理由。
使用 ModelScope 上的 DeepSeek 模型（OpenAI 兼容接口）。
"""
import os
import logging
from openai import OpenAI

logger = logging.getLogger("reason_agent")

DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4.1-Flash"
DEFAULT_BASE_URL = "https://api-inference.modelscope.cn/v1"

REASON_SYSTEM_PROMPT = """你是短视频平台内容审核与社区治理专家，熟悉《抖音社区自律公约》。
根据用户提供的视频/帖子真实信息，生成一份专业、具体、贴合内容的举报理由。
要求：
1. 只基于用户提供的真实内容，不编造视频中不存在的细节。
2. 明确引用公约对应的违规类别。
3. 结构清晰、措辞客观专业，便于审核人员快速定位违规点。
4. 全文控制在 400 字以内。"""


class ReasonAgent:
    """写理由 Agent：输入视频信息 -> 输出举报理由"""

    def __init__(self, api_key: str = "", model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE_URL):
        self.api_key = api_key or os.environ.get("MODELSCOPE_API_KEY", "")
        self.model = model
        self.base_url = base_url
        if not self.api_key:
            raise ValueError("缺少 ModelScope API Key，请设置环境变量 MODELSCOPE_API_KEY 或在初始化时传入")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate(self, video_info: dict, platform_rules: str, platform: str = "douyin") -> str:
        """生成举报理由"""
        link = video_info.get("link", "")
        title = video_info.get("title", "")
        author = video_info.get("author", "")
        desc = video_info.get("desc", "")

        user_content = f"""【目标平台】{platform}
【视频标题】{title}
【作者】{author}
【视频文案/描述】{desc}
【视频链接】{link}

【平台规则参考】
{platform_rules}

请根据以上真实信息，为这条视频生成一份可以直接提交给平台的举报理由。"""

        # 首次调用 + 一次空返回重试（ModelScope 偶发返回空）
        for attempt in range(2):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": REASON_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                )
                content = resp.choices[0].message.content
                if content and content.strip():
                    return content.strip()
                logger.warning("LLM 返回空内容 (attempt %d)", attempt + 1)
            except Exception as e:
                logger.error("LLM 调用失败 (attempt %d): %s", attempt + 1, e)
                if attempt == 1:
                    raise RuntimeError(f"生成举报理由失败：{e}")

        raise RuntimeError("生成举报理由失败：模型多次返回空内容，请重试")
