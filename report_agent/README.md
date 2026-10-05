# 举报理由生成 Agent

输入视频 / 帖子链接、粘贴文案、**或上传视频文件**，自动完成「查询视频 Agent」+「写理由 Agent」两段式流程，生成贴合内容、引用平台规则的举报理由。手机浏览器可直接使用。

## 功能

- **查询视频 Agent**：解析链接（抖音 / B 站 / 小红书 / 知乎 / 微博 / 通用网页），提取标题、作者、文案、链接
- **豆包多模态视频理解**（抖音推荐方式）：上传视频文件，由豆包大模型（火山方舟 `doubao-seed-2-1-pro-260628`）自动理解视频画面、语音、字幕内容，输出结构化描述——抖音匿名解析受限时的最佳路径
- **写理由 Agent**：调用大模型（ModelScope DeepSeek），结合《抖音社区自律公约》要点，生成结构化举报理由
- **手机可用**：响应式页面，手机 / 电脑浏览器都能用；部署后任何设备可访问

## 运行

```bash
# 1. 安装依赖（系统 Python 3.11）
pip install -r requirements.txt

# 2. 设置 API Key
#    写理由 Agent 需要（ModelScope）：
set MODELSCOPE_API_KEY=你的ModelScope密钥
#    豆包视频理解需要（火山方舟，上传视频文件时必填）：
set ARK_API_KEY=你的火山方舟密钥

# 3. 启动服务
python app.py

# 浏览器打开 http://localhost:8000
```

## 手机访问

手机与电脑连同一 Wi-Fi，手机浏览器打开 `http://<电脑局域网IP>:8000`（Windows 查看 IP：`ipconfig` 中 IPv4 地址）。

## 目录结构

```
report_agent/
├── app.py                      # FastAPI 主入口（/ 前端页面，/api/report 生成接口）
├── rules.py                    # 平台规则库（抖音社区自律公约要点）
├── agents/
│   ├── video_agent.py          # 查询视频 Agent（链接解析 + 兜底）
│   ├── reason_agent.py         # 写理由 Agent（LLM 生成举报理由）
│   └── video_understanding.py  # 豆包多模态视频理解 Agent（火山方舟）
├── static/
│   └── index.html              # 手机响应式前端（支持上传视频文件）
└── requirements.txt
```

## 接口

- `POST /api/report`：`multipart/form-data`，字段 `link`（链接）、`text`（手动文案）、`file`（视频文件，可选）→ 返回 `{ok, video, reason, msg}`
- `GET /`：前端页面

## 豆包视频理解：获取 ARK_API_KEY

1. 打开火山引擎控制台：<https://console.volcengine.com/ark>（需注册火山引擎账号）
2. 左侧「API Key 管理」→「创建 API Key」，复制保存
3. 开通模型：左侧「开通管理」→ 开通 `doubao-seed-2-1-pro-260628`（视频理解，有免费额度）
4. 设置环境变量 `ARK_API_KEY=你的密钥` 后重启服务

> 说明：抖音 App 能直接解析抖音链接，是因为字节内部有登录态 + 内置逐字稿能力，**不开放为公开 API**。火山方舟官方文档明确抖音视频数据需商务对接，个人开发者不可用。因此本工具对抖音采用「上传视频文件 → 豆包多模态理解」的合规路径，B站等平台仍可纯链接自动解析。

## 说明

- 抖音匿名解析受平台反爬限制，自动解析可能失败，此时推荐上传视频文件（豆包自动理解），或粘贴视频文案
- 请仅对真实违规内容使用，勿用于恶意举报
