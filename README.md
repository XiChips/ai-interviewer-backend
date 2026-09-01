# AI Interviewer

AI 模拟面试官：基于 DeepSeek API 的流式面试对话后端服务。

## 功能

- 根据岗位（job）和难度级别（level）模拟真实面试官
- 流式返回 AI 回答（SSE / StreamingResponse）
- 支持携带完整对话历史，实现多轮追问

## 技术栈

- Python 3.8+
- FastAPI + Uvicorn
- DeepSeek API（OpenAI SDK 兼容调用）

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt   # 或使用虚拟环境
python3.8 -m venv .venv && source .venv/bin/activate

# 2. 配置 API Key（环境变量或 .env 文件）
export DEEPSEEK_API_KEY=sk-xxxx
# 或在项目根目录创建 .env：
# DEEPSEEK_API_KEY=sk-xxxx

# 3. 启动服务
uvicorn app:app --host 0.0.0.0 --port 8000
```

## API

### GET /test

连通性测试：

```json
{ "message": "连接成功!", "status_code": 200, "is_connected": true }
```

### POST /interview/ask

流式面试对话（SSE 流式返回）。

请求体：

```json
{
  "user_prompt": "面试者的最新回答",
  "session_history": [
    { "role": "assistant", "content": "请先自我介绍" },
    { "role": "user", "content": "我叫张三，有5年Java经验" }
  ],
  "job": "通用技术岗位",
  "level": 3
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_prompt | string | 是 | 面试者最新回答 |
| session_history | array | 否 | 完整对话历史（默认空） |
| job | string | 否 | 面试岗位（默认"通用技术岗位"） |
| level | int | 否 | 难度级别 1-5（默认 3） |

## 目录结构

```
ai-interviewer/
├── app.py              # FastAPI 入口与路由
├── deepseek_service.py # DeepSeek 流式调用封装
└── .env                # 本地配置（不入库，含 API Key）
```
