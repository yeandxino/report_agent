# -*- coding: utf-8 -*-
"""
豆包（火山方舟）视频理解 Agent：
上传抖音/其他平台的视频文件，用豆包多模态大模型理解视频画面+语音内容，
提取标题、内容描述等结构化信息，供「写理由 Agent」生成贴合内容的举报理由。

官方文档：https://docs.volcengine.com/docs/82379/1895586
模型：doubao-seed-2-1-pro-260628（支持视频理解）
"""
import os
import time
import logging
from openai import OpenAI

logger = logging.getLogger("video_understanding")

DEFAULT_MODEL = "doubao-seed-2-1-pro-260628"
DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

UNDERSTAND_PROMPT = """请仔细观看这条视频，并输出以下信息（用 JSON 格式）：
1. title：视频标题或视频想表达的主题（一句话，如果没有标题就根据内容概括）
2. description：视频内容的客观详细描述，包括：画面内容、场景、人物及其言行、语音/台词/旁白内容、字幕文字。如果视频包含语音或台词，请尽量逐句转写关键内容。
3. text_overlay：视频画面中出现的文字、字幕、标题文字（如有）
4. is_controversial：视频内容是否存在违法违规、不实信息、网络暴力、色情低俗、侵犯隐私等风险（true/false），并说明理由
5. reason_evidence：如果存在违规风险，指出具体违规点（如"传播不实信息"、"人身攻击"、"泄露隐私"等）

注意：请客观描述视频实际内容，不要主观评价，不要编造视频中不存在的信息。"""


class VideoUnderstandingAgent:
    """豆包多模态视频理解 Agent：输入视频文件 -> 输出结构化视频内容信息"""

    def __init__(self, api_key: str = "", model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE_URL):
        self.api_key = api_key or os.environ.get("ARK_API_KEY", "")
        self.model = model
        self.base_url = base_url
        if not self.api_key:
            raise ValueError("缺少火山方舟 ARK_API_KEY，请到火山方舟控制台创建（https://console.volcengine.com/ark）")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def understand(self, file_path: str, max_wait: int = 180) -> dict:
        """上传视频文件并用豆包理解内容，返回结构化信息"""
        # 1) 上传视频文件到方舟 Files API
        try:
            with open(file_path, "rb") as f:
                file = self.client.files.create(
                    file=f,
                    purpose="user_data",
                    preprocess_configs={"video": {"fps": 0.5}},
                )
            logger.info("file uploaded: id=%s status=%s", file.id, file.status)
        except Exception as e:
            raise RuntimeError(f"视频文件上传失败：{e}")

        # 2) 等待文件处理完成（status 变为 active/processed）
        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                st = self.client.files.retrieve(file.id)
                if st.status in ("active", "processed", "success"):
                    logger.info("file processed: id=%s status=%s", file.id, st.status)
                    break
                logger.info("file processing: status=%s", st.status)
            except Exception:
                pass
            time.sleep(3)
        else:
            raise RuntimeError("视频文件处理超时，请稍后重试")

        # 3) 调用豆包多模态模型理解视频
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "video_url", "video_url": {"file_id": file.id}},
                            {"type": "text", "text": UNDERSTAND_PROMPT},
                        ],
                    }
                ],
                max_tokens=2000,
                temperature=0.2,
            )
            content = resp.choices[0].message.content
            if not content or not content.strip():
                raise RuntimeError("豆包未能理解视频内容，请重试")
            logger.info("understanding ok: %d chars", len(content))
            return self._parse_output(content)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"豆包视频理解调用失败：{e}")

    def _parse_output(self, content: str) -> dict:
        """从模型输出中解析 JSON，失败则回退为纯文本描述"""
        content = content.strip()
        # 尝试提取 JSON 块
        import json
        import re

        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, dict):
                    return {
                        "title": str(data.get("title") or "").strip(),
                        "desc": str(data.get("description") or "").strip(),
                        "text_overlay": str(data.get("text_overlay") or "").strip(),
                        "risk": data.get("is_controversial"),
                        "evidence": str(data.get("reason_evidence") or "").strip(),
                    }
            except Exception:
                pass
        # 回退：整段作为描述
        return {"title": "", "desc": content, "text_overlay": "", "risk": None, "evidence": ""}


# 便捷入口
def understand_video(file_path: str, api_key: str = "") -> dict:
    agent = VideoUnderstandingAgent(api_key=api_key)
    return agent.understand(file_path)
