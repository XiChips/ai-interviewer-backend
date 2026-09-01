# E:\X\Code\back\ai-interviewer\app.py

from dotenv import load_dotenv
# ----------------------------------------------------------------------
# ⚡️ 1. 关键：在应用初始化前加载 .env 文件中的环境变量（解决 API Key 读取问题）
load_dotenv()
# ----------------------------------------------------------------------

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from deepseek_service import get_ai_response # 确保 deepseek_service.py 文件存在

# 1. 初始化 FastAPI 应用
app = FastAPI(title="AI Interviewer Server")


# 2. 定义前端请求的数据结构 (Pydantic 模型)
class InterviewRequest(BaseModel):
    user_prompt: str  # 面试者的最新回答
    session_history: list = []  # 整个对话历史 (可选，默认为空列表)
    job: str = "通用技术岗位"  # 给个默认值，防止前端没传报错
    level: int = 3  # 给个默认值 3


@app.get("/test")
def test_endpoint():

    return {
        "message": "连接成功!",
        "status_code": 200,
        "is_connected": True
    }

# 3. 定义 API 路由 (POST 请求)
@app.post("/interview/ask")
async def process_interview_step(request: InterviewRequest):
    # 调用我们改好的流式函数
    gen = get_ai_response(request.user_prompt, request.session_history,request.job,request.level)

    # 将生成器包装成 SSE (Server-Sent Events) 格式返回
    def sse_generator():
        for text in gen:
            yield f"data: {text}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


# 4. 定义一个简单的根路径 (用于测试服务器是否启动)
@app.get("/")
def read_root():
    """
    服务器健康检查端点。
    """
    return {"status": "AI Interviewer Server is ready!"}

# 启动命令：uvicorn app:app --reload --host 0.0.0.0 --port 8000