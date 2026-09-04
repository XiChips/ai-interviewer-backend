# AI Interviewer

AI 模拟面试官：基于 DeepSeek API 的流式面试后端服务。

## 功能

- **多职位类别**：技术开发 / 产品经理 / 运营 / 销售·商务 / 市场·品牌 / 设计 / 数据分析 / 人力资源 / 财务·会计 / 通用综合
  - 按岗位名称**自动识别类别**（也可显式指定），每类有独立的考察重点、追问策略与开场
- **多难度级别**：L1-L5，不同级别自动切换考察深度与"横向扩展"策略
- **流式回答**：SSE（Server-Sent Events）
- **历史持久化**：面试会话与消息落库（SQLite），可浏览历史、查看单次完整记录
- **自动评分**：结束面试后 AI 按类别维度打分（0-100），输出亮点 / 不足 / 建议 / 结论

## 技术栈

- Python 3.8+ / FastAPI / Uvicorn
- DeepSeek API（OpenAI SDK 兼容调用）
- SQLite（持久化，文件 `interviewer.db`，自动创建）

## 快速开始

```bash
# 1. 安装依赖
python3.8 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 配置 API Key（环境变量或 .env 文件）
export DEEPSEEK_API_KEY=sk-xxxx

# 3. 启动服务（systemd: ai-interviewer.service）
uvicorn app:app --host 0.0.0.0 --port 8000
```

## API

### GET /test · GET /

连通性测试。

### GET /interview/job-categories

支持的职位类别列表（`key / label / examples`），前端职位选择器可直接渲染。

### POST /interview/start —— 开始面试（推荐）

创建会话并**流式返回开场白**。SSE 首个事件是会话元信息，之后是开场白文本流：

```json
data: {"type":"session","session_id":1,"job":"B端产品经理","category":"product","category_label":"产品经理","level":3}

data: 你好，我是今天的产品面试官…
```

请求体：

```json
{ "job": "B端产品经理", "level": 3 }
```

### POST /interview/ask —— 对话

**持久化模式（推荐）**：带 `session_id`，历史以服务端为准，前端只需发最新回答：

```json
{ "session_id": 1, "user_prompt": "我的做法是按客户规模分层…" }
```

返回 SSE 文本流（`data: <文本片段>`）。已结束（评分过）的会话可继续追问，会自动回到"进行中"并作废旧评分。

**旧版无状态模式（兼容）**：不带 `session_id`，使用传入的完整历史，不落库：

```json
{
  "user_prompt": "面试者的最新回答",
  "session_history": [ { "role": "assistant", "content": "…" }, { "role": "user", "content": "…" } ],
  "job": "通用技术岗位",
  "level": 3
}
```

### POST /interview/finish —— 结束并评分

```json
{ "session_id": 1 }
```

要求至少完成 2 轮回答。返回评分结果（落库）：

```json
{
  "session_id": 1,
  "job": "B端产品经理",
  "level": 3,
  "category_label": "产品经理",
  "score": {
    "overall_score": 72,
    "dimensions": [ { "name": "产品思维", "score": 70, "comment": "…" } ],
    "strengths": ["…"],
    "weaknesses": ["…"],
    "suggestion": "…",
    "verdict": "通过 | 待定 | 不通过（一句话理由）"
  }
}
```

### GET /interview/sessions —— 历史列表

`?page=1&page_size=10`（page_size ≤ 50），按新→旧：

```json
{
  "total": 12,
  "sessions": [
    {
      "id": 12, "job": "Java后端开发", "category": "tech", "category_label": "技术开发",
      "level": 3, "status": "finished", "message_count": 9,
      "created_at": "…", "finished_at": "…",
      "score_summary": { "overall_score": 78, "verdict": "通过" }
    }
  ]
}
```

### GET /interview/sessions/{id} —— 单次完整记录

含全部消息（`messages: [{role, content, created_at}]`）与完整评分（`score`）。

### DELETE /interview/sessions/{id}

删除一次记录。

## 前端对接建议

1. 进入面试页 → `POST /interview/start`，解析首个 `session` 事件拿到 `session_id`，随后渲染文本流；
2. 每轮对话 → `POST /interview/ask`（带 `session_id`），只传最新回答；
3. 点"结束面试" → `POST /interview/finish` 展示评分；
4. 历史页 → `GET /interview/sessions` 列表 + `GET /interview/sessions/{id}` 详情。

## 目录结构

```
ai-interviewer/
├── app.py               # FastAPI 入口与路由
├── deepseek_service.py  # DeepSeek 调用：多类别 Prompt / 流式 / 评分
├── db.py                # SQLite 存储层（会话 + 消息 + 评分）
├── interviewer.db       # 数据文件（自动创建，不入库）
└── .env                 # 本地配置（不入库，含 API Key）
```
