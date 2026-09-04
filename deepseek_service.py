# -*- coding: utf-8 -*-
"""
DeepSeek 调用封装：流式面试对话 + 面试评分。

- 支持多职位类别（技术 / 产品 / 运营 / 销售 / 市场 / 设计 / 数据分析 / HR / 财务 / 通用）
- 按类别自动切换考察重点、追问策略与评分维度
"""
import os
import re
import json
from openai import OpenAI

api_key = os.environ.get("DEEPSEEK_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com",
)

# ----------------------------------------------------------------------
# 职位类别元数据
# ----------------------------------------------------------------------

JOB_CATEGORIES = [
    {
        "key": "tech",
        "label": "技术开发",
        "examples": ["Java 后端", "前端开发", "算法工程师", "测试开发", "运维工程师"],
        "focus": "技术功底、工程实践与架构思维",
    },
    {
        "key": "product",
        "label": "产品经理",
        "examples": ["B端产品经理", "用户产品", "电商产品", "AI 产品经理"],
        "focus": "产品思维、用户洞察与优先级决策",
    },
    {
        "key": "operations",
        "label": "运营",
        "examples": ["用户运营", "内容运营", "活动运营", "新媒体运营"],
        "focus": "运营策略、数据敏感度与执行力",
    },
    {
        "key": "sales",
        "label": "销售 / 商务",
        "examples": ["大客户销售", "电话销售", "渠道商务", "BD 经理"],
        "focus": "销售技巧、客户洞察与抗压能力",
    },
    {
        "key": "marketing",
        "label": "市场 / 品牌",
        "examples": ["市场专员", "品牌策划", "数字营销", "广告投放"],
        "focus": "营销策略、创意能力与品牌理解",
    },
    {
        "key": "design",
        "label": "设计",
        "examples": ["UI 设计师", "UX 设计师", "视觉设计师", "交互设计"],
        "focus": "设计功底、审美创意与设计决策",
    },
    {
        "key": "data",
        "label": "数据分析",
        "examples": ["数据分析师", "商业分析", "BI 工程师"],
        "focus": "分析思维、业务理解与数据工具能力",
    },
    {
        "key": "hr",
        "label": "人力资源",
        "examples": ["招聘专员", "HRBP", "培训发展", "薪酬绩效"],
        "focus": "专业素养、洞察判断与沟通协调",
    },
    {
        "key": "finance",
        "label": "财务 / 会计",
        "examples": ["会计", "财务分析", "审计", "税务"],
        "focus": "专业规范、数据严谨与合规意识",
    },
    {
        "key": "general",
        "label": "通用综合",
        "examples": ["管理培训生", "行政", "客服", "不限岗位"],
        "focus": "结构化思维、沟通表达与综合素质",
    },
]

CATEGORY_MAP = {c["key"]: c for c in JOB_CATEGORIES}

# 非技术岗位的考察重点细节
CATEGORY_FOCUS = {
    "product": "需求分析与优先级、用户痛点洞察、方案设计与数据验证、跨团队推动落地",
    "operations": "目标拆解与策略制定、活动/内容/用户增长打法、数据复盘归因、资源协调执行力",
    "sales": "客户需求挖掘、异议处理与成交推动、客情维护、目标管理与抗压",
    "marketing": "品牌定位与传播策略、创意方案、渠道投放与效果衡量、预算意识",
    "design": "设计规范与还原度、用户场景与可用性、审美与创意表达、设计方案的沟通说服",
    "data": "分析框架与指标拆解、数据洞察与业务建议、统计常识、工具熟练度",
    "hr": "人才识别与面试方法、业务理解与 HRBP 思维、沟通协调、流程合规意识",
    "finance": "会计准则与核算规范、财务分析逻辑、风险与合规意识、数据严谨性",
    "general": "结构化表达、情景应变、学习能力、责任心与职业素养",
}

# 评分维度（每类 5 项，含加权说明）
CATEGORY_DIMS = {
    "tech": ["技术深度", "代码与工程能力", "问题解决", "沟通表达", "学习潜力"],
    "product": ["产品思维", "用户理解", "需求优先级决策", "数据分析", "沟通表达"],
    "operations": ["运营策略", "数据敏感度", "执行力", "用户思维", "沟通表达"],
    "sales": ["销售技巧", "客户洞察", "抗压与韧性", "沟通说服", "目标感"],
    "marketing": ["营销策略", "创意能力", "品牌理解", "数据驱动", "沟通表达"],
    "design": ["设计功底", "审美与创意", "用户同理心", "设计决策", "沟通表达"],
    "data": ["分析思维", "业务理解", "统计与工具", "数据严谨性", "沟通表达"],
    "hr": ["专业素养", "洞察判断", "沟通协调", "流程思维", "职业操守"],
    "finance": ["财务专业", "数据严谨", "合规意识", "分析能力", "沟通表达"],
    "general": ["专业匹配度", "逻辑思维", "沟通表达", "学习能力", "综合素质"],
}

# 关键词 → 类别
_CATEGORY_KEYWORDS = [
    ("tech", ["java", "python", "go", "前端", "后端", "开发", "算法", "测试", "运维", "技术",
              "工程师", "架构", "c++", "php", "node", "react", "vue", "android", "ios", "嵌入式",
              "数据仓库", "etl", "程序员", "coding", "sde", "软件"]),
    ("product", ["产品", "pm", "需求分析"]),
    ("operations", ["运营", "增长", "新媒体", "内容运营", "用户运营", "活动运营"]),
    ("sales", ["销售", "商务", "bd", "客户经理", "渠道", "招商", "导购", "营业员"]),
    ("marketing", ["市场", "品牌", "营销", "广告", "投放", "公关", "推广"]),
    ("design", ["设计", "ui", "ux", "视觉", "交互", "美工", "原画"]),
    ("data", ["数据", "分析", "bi", "商业分析"]),
    ("hr", ["hr", "人力", "人事", "招聘", "培训", "薪酬", "绩效", "行政"]),
    ("finance", ["财务", "会计", "审计", "税务", "出纳", "核算"]),
]

# 难度等级标签
LEVEL_LABEL = {1: "初级", 2: "初中级", 3: "中级", 4: "高级", 5: "专家级"}


def infer_category(job: str) -> str:
    """根据岗位名称推断类别；无法判断时返回 general"""
    if not job:
        return "general"
    text = job.lower()
    for key, words in _CATEGORY_KEYWORDS:
        for w in words:
            if w in text:
                return key
    return "general"


def get_category_label(category: str) -> str:
    meta = CATEGORY_MAP.get(category)
    return meta["label"] if meta else "通用综合"


# ----------------------------------------------------------------------
# Prompt 构建
# ----------------------------------------------------------------------

def _tech_level_desc(level: int) -> str:
    """技术岗：按难度定义考察重点与横向扩展策略（沿用原版精心调优逻辑）"""
    if level <= 2:
        return (
            "考察重点：**基础语法与API熟练度**。\n"
            "【追问策略 - 横向扩展】\n"
            "如果用户答对了基础用法，不要问底层源码。请转向**常见错误**或**关联API**。\n"
            "例子：用户懂了 `v-if`，就问它和 `v-show` 混用会怎样？而不是问 v-if 源码怎么编译的。"
        )
    if level == 3:
        return (
            "考察重点：**业务落地能力与代码健壮性**。\n"
            "【追问策略 - 横向扩展】\n"
            "如果用户给出了完美方案，**立刻停止**在该技术点上的纵向挖掘。\n"
            "请转向**异常处理 (Error Handling)**、**边界情况 (Edge Cases)** 或 **简单性能优化**。\n"
            "例子：用户流式请求写得很好，就问“如果网络断了怎么重连？”，而不是问“TCP包在内核怎么组装的？”"
        )
    return (
        "考察重点：**架构设计、技术选型权衡 (Trade-offs) 与系统瓶颈**。\n"
        "【追问策略 - 横向扩展】\n"
        "即使是专家，也不要死磕某一行源码。如果用户懂原理，请转向**场景变换**。\n"
        "例子：用户懂了单机缓存原理，就问“分布式环境下数据一致性怎么保证？”，或者“如果写多读少，这个架构怎么调？”"
    )


def _general_level_desc(category: str, level: int) -> str:
    """非技术岗：按难度定义考察深度"""
    base = CATEGORY_FOCUS.get(category, CATEGORY_FOCUS["general"])
    if level <= 2:
        depth = (
            "考察重点：**岗位基础认知与执行能力**。\n"
            "【追问策略】候选人答出标准做法后，转向**具体场景中的细节与常见坑**，"
            "例如“如果XX数据异常/客户投诉/素材延期，你会怎么处理？”"
        )
    elif level == 3:
        depth = (
            "考察重点：**复杂场景落地与多目标权衡**。\n"
            "【追问策略】候选人给出完整方案后，立刻转向**资源受限/多方冲突/数据不完整**等现实约束，"
            "看ta如何取舍与推进。"
        )
    else:
        depth = (
            "考察重点：**体系搭建、策略规划与全局视角**。\n"
            "【追问策略】在候选人讲清单点方法后，追问**规模化、跨团队协同、长期机制**，"
            "例如“这套方法从0到1没问题，团队到20人/业务翻倍后还成立吗？”"
        )
    return f"【考察领域】{base}\n{depth}"


def build_system_prompt(job: str, level: int, category: str) -> str:
    """构建面试官 System Prompt（区分技术岗 / 非技术岗）"""
    level = max(1, min(5, int(level or 3)))
    category = category or infer_category(job)
    meta = CATEGORY_MAP.get(category, CATEGORY_MAP["general"])
    label = meta["label"]
    level_tag = LEVEL_LABEL.get(level, "中级")

    common_rules = (
        "【绝对行为准则】（违反将导致面试失败）\n"
        "1. **拒绝“死磕到底”**：面试不是为了考倒候选人，而是测出边界。\n"
        "   - **黄金规则**：一旦候选人在某个点上回答清晰、逻辑自洽，**立刻认可并进行“横向跨越”**"
        "（换一个相关场景或考察异常情况），严禁在同一个坑里无限向下追问细节。\n"
        "2. **拒绝说教**：\n"
        "   - ❌ 减少说：“你的回答暴露了...”、“你应该...”。\n"
        "   - ✅ 引导说：“这个方案在正常情况下没问题，但如果遇到...情况，会不会有隐患？”\n"
        "3. **单点提问**：每次回复**只问 1 个核心问题**，严禁使用 1. 2. 3. 列表形式发问。\n"
        "4. **字数限制**：保持简练，每次回复控制在 **150 字以内**。\n"
        "5. **场景化提问**：优先用具体业务/技术场景提问，少问背诵型问题。"
    )

    if category == "tech":
        level_desc = _tech_level_desc(level)
        return f"""
你是一位**资深技术面试官**（同事风格，非教授风格）。
当前岗位：【{job}】 | 难度：L{level}（{level_tag}）。

【核心考察逻辑】
{level_desc}

{common_rules}

【开场】第一次对话时，简短自我介绍（岗位 + L{level} 难度 + 考察方向），然后直接抛出第一个技术问题。
现在，请进入角色。
"""

    # 非技术岗
    level_desc = _general_level_desc(category, level)
    return f"""
你是一位**资深{label}面试官**（同事风格，非教授风格）。
当前岗位：【{job}】 | 类别：{label} | 难度：L{level}（{level_tag}）。

{level_desc}

{common_rules}

【开场】第一次对话时，简短自我介绍（岗位 + L{level} 难度 + 考察方向），然后直接抛出第一个业务场景问题。
现在，请进入角色。
"""


# ----------------------------------------------------------------------
# 流式对话
# ----------------------------------------------------------------------

def stream_chat(system_prompt: str, history: list, user_msg: str):
    """携带 system + 历史，发送用户消息，流式产出 AI 回复文本"""
    if not api_key:
        yield "错误：API Key 未设置，请检查环境变量 DEEPSEEK_API_KEY。"
        return

    messages = [{"role": "system", "content": system_prompt}]
    for msg in (history or []):
        if msg.get("role") in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_msg})

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=500,
        )
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        print(f"DeepSeek API 请求失败: {e}")
        yield f"[系统错误]: {str(e)}"


def get_ai_response(user_prompt: str, history: list = None, job: str = None, level: int = None):
    """兼容旧接口：无状态流式对话（不落库）"""
    job = job or "通用技术岗位"
    try:
        level = int(level or 3)
    except Exception:
        level = 3
    category = infer_category(job)
    system = build_system_prompt(job, level, category)
    yield from stream_chat(system, history or [], user_prompt)


# ----------------------------------------------------------------------
# 面试评分
# ----------------------------------------------------------------------

def _trim_history(history: list, max_msgs: int = 40, max_chars: int = 24000):
    """截断对话：保留最近 max_msgs 条，超长时压缩每条内容"""
    trimmed = history[-max_msgs:]
    total = 0
    result = []
    for msg in reversed(trimmed):
        content = msg["content"]
        if len(content) > 1500:
            content = content[:1500] + "…（截断）"
        total += len(content)
        if total > max_chars:
            break
        result.append({"role": msg["role"], "content": content})
    result.reverse()
    return result


def score_interview(job: str, level: int, category: str, history: list) -> dict:
    """对完整面试对话评分（非流式 JSON 输出）"""
    if not api_key:
        return {"error": "API Key 未设置"}

    category = category or infer_category(job)
    meta = CATEGORY_MAP.get(category, CATEGORY_MAP["general"])
    label = meta["label"]
    dims = CATEGORY_DIMS.get(category, CATEGORY_DIMS["general"])

    dim_lines = "\n".join(f"- {d}：0-100 分，附一句评价" for d in dims)
    history = _trim_history(history or [])

    transcript = "\n".join(
        ("候选人：" if m["role"] == "user" else "面试官：") + m["content"]
        for m in history
    )
    if not transcript.strip():
        transcript = "（无有效对话内容）"

    system = (
        "你是一位严谨、公正的面试评估专家。根据给定的面试对话记录，为候选人评分。\n"
        f"岗位：【{job}】（{label}方向）| 难度 L{int(level or 3)}\n"
        "评分原则：\n"
        "1. 基于对话中的实际表现，不臆测对话之外的能力；\n"
        "2. 回答越具体（有案例、有数据、有思考过程）得分越高；空泛套话得分低；\n"
        "3. 难度 L1-2 侧重基础达标，L3 侧重独立解决问题，L4-5 侧重深度与全局，评分时参考对应标准；\n"
        "4. overall_score 是各维度合理加权后的总分（0-100 整数）。\n"
        f"评分维度：\n{dim_lines}\n"
        "必须只输出一个 JSON 对象：\n"
        "{\n"
        '  "overall_score": 0,\n'
        '  "dimensions": [{"name": "维度名", "score": 0, "comment": "一句话评价"}],\n'
        '  "strengths": ["2-4条亮点"],\n'
        '  "weaknesses": ["2-4条不足"],\n'
        '  "suggestion": "综合提升建议，2-4句",\n'
        '  "verdict": "通过 | 待定 | 不通过（一句话理由）"\n'
        "}"
    )

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": "面试对话记录：\n" + transcript},
            ],
            stream=False,
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content
        data = json.loads(_extract_json(text))
        # 规范化
        data["overall_score"] = max(0, min(100, int(data.get("overall_score") or 0)))
        data.setdefault("dimensions", [])
        data.setdefault("strengths", [])
        data.setdefault("weaknesses", [])
        data.setdefault("suggestion", "")
        data.setdefault("verdict", "待定")
        return data
    except Exception as e:
        print(f"评分调用失败: {e}")
        return {"error": f"评分失败: {e}"}


def _extract_json(text: str) -> str:
    """从模型输出中提取 JSON 字符串（容错 ```json 包裹等）"""
    if not text:
        return "{}"
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text
