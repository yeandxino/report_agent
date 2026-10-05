# -*- coding: utf-8 -*-
"""
举报理由生成 Agent - FastAPI 服务
启动：python app.py  或  uvicorn app:app --host 0.0.0.0 --port 8000

流程：
1. 用户输入链接 / 粘贴文案 / 上传视频文件（三选一或组合）
2. 查询视频 Agent：解析链接（B站等）或 用豆包多模态理解视频文件（抖音等）
3. 写理由 Agent：基于视频信息 + 平台规则生成举报理由
"""
import os
import sys
import uuid
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
from agents.video_agent import VideoQueryAgent
from agents.reason_agent import ReasonAgent
from agents.video_understanding import VideoUnderstandingAgent
from rules import PLATFORM_RULES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("report_agent")

app = FastAPI(title="举报理由生成 Agent")

# 全局单例
video_agent = VideoQueryAgent()
reason_agent = None  # 懒加载（依赖 API Key）
video_understanding = None  # 懒加载（依赖 ARK_API_KEY）

# 上传文件临时目录
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".flv", ".webm", ".m4v", ".wmv", ".mp3", ".m4a", ".wav"}
MAX_UPLOAD_MB = 500


class ReportRequest(BaseModel):
    link: str = ""
    text: str = ""  # 手动粘贴的视频文案/描述


class ReportResponse(BaseModel):
    ok: bool
    video: dict
    reason: str = ""
    msg: str = ""


def _get_reason_agent():
    global reason_agent
    if reason_agent is None:
        reason_agent = ReasonAgent()
    return reason_agent


def _get_video_understanding():
    global video_understanding
    if video_understanding is None:
        video_understanding = VideoUnderstandingAgent()
    return video_understanding


@app.get("/")
def index():
    return FileResponse(str(Path(__file__).parent / "static" / "index.html"))


@app.post("/api/report", response_model=ReportResponse)
async def generate_report(
    link: str = Form(""),
    text: str = Form(""),
    file: UploadFile = File(None),
):
    """主流程：查询视频 Agent（可选豆包视频理解） -> 写理由 Agent"""
    link = (link or "").strip()
    text = (text or "").strip()

    # ---------- 0) 保存上传的视频文件 ----------
    file_path = None
    if file and file.filename:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in ALLOWED_VIDEO_EXTS:
            return ReportResponse(
                ok=False, video={}, reason="",
                msg=f"不支持的文件类型 {suffix}，请上传视频或音频文件（mp4/mov/avi/mkv/flv/webm/m4v/wmv/mp3/m4a/wav）",
            )
        fname = f"{uuid.uuid4().hex}{suffix}"
        file_path = UPLOAD_DIR / fname
        try:
            data = await file.read()
            if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
                return ReportResponse(ok=False, video={}, reason="", msg=f"文件过大，请上传 {MAX_UPLOAD_MB}MB 以内的视频")
            file_path.write_bytes(data)
            logger.info("upload saved: %s (%d bytes)", fname, len(data))
        except Exception as e:
            logger.error("upload failed: %s", e)
            return ReportResponse(ok=False, video={}, reason="", msg=f"文件上传失败：{e}")

    try:
        # ---------- 1) 查询视频 Agent ----------
        if file_path:
            # 优先：豆包多模态理解视频文件
            try:
                vu = _get_video_understanding()
                understood = vu.understand(str(file_path))
                logger.info("豆包理解结果: title=%s desc_len=%d", understood["title"][:40], len(understood["desc"]))
                video = {
                    "link": link or "(已上传视频文件)",
                    "title": understood.get("title") or (link and video_agent._detect_platform(link) or ""),
                    "author": "",
                    "desc": understood.get("desc") or "",
                    "platform": video_agent._detect_platform(link) or "douyin",
                    "video_id": "",
                    "understood": True,
                }
                if text:
                    video["desc"] = (video["desc"] + "\n【用户补充】" + text).strip()
                if not video["title"] and video["desc"]:
                    video["title"] = video["desc"][:60]
                return _finish(video, platform=video["platform"])
            except Exception as e:
                logger.error("豆包视频理解失败: %s", e)
                return ReportResponse(ok=False, video={}, reason="", msg=str(e))
        else:
            # 普通路径：链接解析 + 手动文案
            result = video_agent.query(link, text)
            video = result["info"]
            if not result["ok"]:
                return ReportResponse(ok=False, video=video, reason="", msg=result["msg"])
            return _finish(video, platform=video.get("platform") or "douyin")
    finally:
        # 清理临时文件
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass


def _finish(video: dict, platform: str) -> ReportResponse:
    """第二步：写理由 Agent"""
    rules_text = PLATFORM_RULES.get(platform, PLATFORM_RULES["douyin"])
    try:
        ra = _get_reason_agent()
        reason = ra.generate(video, rules_text, platform)
        return ReportResponse(ok=True, video=video, reason=reason, msg="生成成功")
    except Exception as e:
        logger.error("reason generation failed: %s", e)
        return ReportResponse(ok=False, video=video, reason="", msg=str(e))


# 静态资源（前端）
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
