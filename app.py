# -*- coding: utf-8 -*-
"""
AI Interviewer Server

- 流式面试对话（SSE）
- 多职位类别（技术 / 产品 / 运营 / 销售 / 市场 / 设计 / 数据分析 / HR / 财务 / 通用）
- 面试历史持久化与浏览（SQLite）
- 面试结束自动评分
"""
import json
import os

from dotenv import load_dotenv
load_dotenv()

from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import auth
import db
from deepseek_service import (
    get_ai_response,
    build_system_prompt,
    stream_chat,
    infer_category,
    get_category_label,
    JOB_CATEGORIES,
    score_interview,
)

db.init_db()

app = FastAPI(title="AI Interviewer Server")

# 允许跨域（方便本地前端联调）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# 请求模型
# ----------------------------------------------------------------------

class StartRequest(BaseModel):
    job: str = "通用岗位"
    level: int = 3


class AskRequest(BaseModel):
    user_prompt: str
    session_history: list = []
    job: str = "通用技术岗位"
    level: int = 3
    session_id: Optional[int] = None


class FinishRequest(BaseModel):
    session_id: int


class LoginRequest(BaseModel):
    password: str


# ----------------------------------------------------------------------
# 基础
# ----------------------------------------------------------------------

@app.post("/auth/login")
def login(req: LoginRequest):
    """密码登录（密码即账号）：666666 访客 / 071527 管理员"""
    result = auth.login(req.password)
    if not result:
        raise HTTPException(status_code=401, detail="密码错误")
    return result


@app.post("/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    """登出：作废当前 token"""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token:
        auth.logout(token)
    return {"ok": True}


def _require_admin(authorization: Optional[str] = Header(None)):
    """依赖：仅管理员可调用（访客无法消耗 AI 额度）"""
    role = auth.get_role_from_authorization(authorization)
    if role != "admin":
        raise HTTPException(status_code=403, detail="访客模式仅可浏览历史记录，无法开始面试")
    return True

@app.get("/test")
def test_endpoint():
    return {"message": "连接成功!", "status_code": 200, "is_connected": True}


@app.get("/")
def read_root():
    return {"status": "AI Interviewer Server is ready!"}


@app.get("/interview/job-categories")
def job_categories():
    """支持的职位类别（前端可选职位 + 自动识别说明）"""
    return {"categories": JOB_CATEGORIES}


# ----------------------------------------------------------------------
# 面试流程
# ----------------------------------------------------------------------

def _norm_level(level) -> int:
    try:
        level = int(level)
    except Exception:
        level = 3
    return max(1, min(5, level))


@app.post("/interview/start")
def start_interview(req: StartRequest, _: bool = Depends(_require_admin)):
    """创建面试会话，流式返回开场白。
    SSE 首个事件为会话信息：data: {"type":"session","session_id":1,"category":"tech",...}
    之后为开场白文本流。"""
    job = (req.job or "").strip() or "通用岗位"
    level = _norm_level(req.level)
    category = infer_category(job)

    session_id = db.create_session(job, category, level)
    system = build_system_prompt(job, level, category)

    session_meta = json.dumps({
        "type": "session",
        "session_id": session_id,
        "job": job,
        "category": category,
        "category_label": get_category_label(category),
        "level": level,
    }, ensure_ascii=False)

    def sse_generator():
        yield f"data: {session_meta}\n\n"
        collected = []
        try:
            for text in stream_chat(system, [], "（面试开始）请做开场介绍，然后直接开始第一个问题。"):
                collected.append(text)
                yield f"data: {text}\n\n"
        finally:
            content = "".join(collected).strip()
            if content:
                db.add_message(session_id, "assistant", content)

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


def _clean_content(text: str) -> str:
    """过滤系统错误消息（不参与对话/评分）"""
    t = (text or "").strip()
    if t.startswith("[系统错误]") or t.startswith("错误："):
        return ""
    return t


@app.post("/interview/ask")
async def process_interview_step(req: AskRequest, _: bool = Depends(_require_admin)):
    """面试对话。
    - 带 session_id：服务端持久化（历史以服务端为准，忽略传入 history）
    - 不带 session_id：兼容旧版无状态模式（使用传入 history，不落库）
    """
    prompt = (req.user_prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="user_prompt 不能为空")

    # ---------- 旧版无状态模式 ----------
    if req.session_id is None:
        gen = get_ai_response(req.user_prompt, req.session_history, req.job, req.level)

        def legacy_sse():
            for text in gen:
                yield f"data: {text}\n\n"

        return StreamingResponse(legacy_sse(), media_type="text/event-stream")

    # ---------- 持久化模式 ----------
    session = db.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="面试会话不存在")

    # 已结束的会话允许继续追问（自动回到进行中，评分将作废）
    if session["status"] == "finished":
        db.reactivate_session(req.session_id)

    history = db.get_messages(req.session_id)
    system = build_system_prompt(session["job"], session["level"], session["category"])

    db.add_message(req.session_id, "user", prompt)

    def sse_generator():
        collected = []
        try:
            for text in stream_chat(system, history, prompt):
                collected.append(text)
                yield f"data: {text}\n\n"
        finally:
            content = _clean_content("".join(collected))
            if content:
                db.add_message(req.session_id, "assistant", content)

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.post("/interview/finish")
def finish_interview(req: FinishRequest, _: bool = Depends(_require_admin)):
    """结束面试并评分：AI 依据完整对话输出多维度评分，落库返回"""
    session = db.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="面试会话不存在")

    history = db.get_messages(req.session_id, limit=80)
    valid = [m for m in history if _clean_content(m["content"])]
    rounds = sum(1 for m in valid if m["role"] == "user")
    if rounds < 2:
        raise HTTPException(
            status_code=400,
            detail=f"对话太短（仅 {rounds} 轮回答），至少完成 2 轮后再评分",
        )

    score = score_interview(session["job"], session["level"], session["category"], valid)
    if score.get("error"):
        raise HTTPException(status_code=502, detail=score["error"])

    db.finish_session(req.session_id, score)
    return {
        "session_id": req.session_id,
        "job": session["job"],
        "level": session["level"],
        "category_label": get_category_label(session["category"]),
        "score": score,
    }


# ----------------------------------------------------------------------
# 历史浏览
# ----------------------------------------------------------------------

@app.get("/interview/sessions")
def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    """面试历史列表（新→旧），含总分摘要"""
    data = db.list_sessions(page, page_size)
    for s in data["sessions"]:
        s["category_label"] = get_category_label(s["category"])
        s["score_summary"] = {
            "overall_score": (s["score"] or {}).get("overall_score"),
            "verdict": (s["score"] or {}).get("verdict"),
        } if s["score"] else None
    return data


@app.get("/interview/sessions/{session_id}")
def get_session_detail(session_id: int):
    """单次面试完整记录（含消息与评分）"""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    session["category_label"] = get_category_label(session["category"])
    session["messages"] = db.get_messages(session_id, limit=500)
    return {"session": session}


@app.delete("/interview/sessions/{session_id}")
def remove_session(session_id: int):
    """删除一次面试记录"""
    ok = db.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    return {"ok": True}
