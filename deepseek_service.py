import os
from openai import OpenAI

# 1. 配置信息
# 建议在系统环境变量中设置 DEEPSEEK_API_KEY
api_key = os.environ.get("DEEPSEEK_API_KEY")

# 初始化 OpenAI 客户端 (适配 DeepSeek)
client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)


def get_ai_response(user_prompt: str, history: list = None, job: str = None, level: int = None):
    """
    使用 OpenAI SDK 调用 DeepSeek API，流式返回 AI 的响应。
    """
    if not api_key:
        yield "错误：API Key 未设置，请检查环境变量 DEEPSEEK_API_KEY。"
        return

    # --- 1. 参数兜底处理 ---
    if job is None:
        job = "通用技术岗位"
    if level is None:
        level = 3

    # 确保 level 是整数
    try:
        level = int(level)
    except:
        level = 3

    # --- 2. 根据 level 定义面试侧重点与“横向扩展”策略 ---

    # Level 1-2 (初级/入门)
    if level <= 2:
        level_desc = (
            "考察重点：**基础语法与API熟练度**。\n"
            "【追问策略 - 横向扩展】\n"
            "如果用户答对了基础用法，不要问底层源码。请转向**常见错误**或**关联API**。\n"
            "例子：用户懂了 `v-if`，就问它和 `v-show` 混用会怎样？而不是问 v-if 源码怎么编译的。"
        )
        focus_point = "基础知识扎实度"

    # Level 3 (中级/主力)
    elif level == 3:
        level_desc = (
            "考察重点：**业务落地能力与代码健壮性**。\n"
            "【追问策略 - 横向扩展】\n"
            "如果用户给出了完美方案，**立刻停止**在该技术点上的纵向挖掘。\n"
            "请转向**异常处理 (Error Handling)**、**边界情况 (Edge Cases)** 或 **简单性能优化**。\n"
            "例子：用户流式请求写得很好，就问“如果网络断了怎么重连？”，而不是问“TCP包在内核怎么组装的？”"
        )
        focus_point = "工程实践与异常处理能力"

    # Level 4-5 (高级/专家)
    else:
        level_desc = (
            "考察重点：**架构设计、技术选型权衡 (Trade-offs) 与系统瓶颈**。\n"
            "【追问策略 - 横向扩展】\n"
            "即使是专家，也不要死磕某一行源码。如果用户懂原理，请转向**场景变换**。\n"
            "例子：用户懂了单机缓存原理，就问“分布式环境下数据一致性怎么保证？”，或者“如果写多读少，这个架构怎么调？”"
        )
        focus_point = "底层原理与架构思维"

    # --- 3. 构造核心 System Prompt ---
    system_prompt_content = f"""
    你是一位**资深技术面试官**（同事风格，非教授风格）。
    当前岗位：【{job}】 | 难度：L{level}。

    【核心考察逻辑】
    {level_desc}

    【绝对行为准则】（违反将导致面试失败）
    1. **拒绝“死磕到底”**：
       - 面试不是为了考倒候选人，而是测出边界。
       - **黄金规则**：一旦用户在某个点上回答清晰、逻辑自洽，**立刻认可并进行“横向跨越”**（换一个相关场景或考察异常情况），严禁在同一个坑里无限向下追问细节。
    2. **拒绝说教**：
       - ❌ 减少说：“你的回答暴露了...”、“你应该...”。
       - ✅ 引导说：“这个方案在正常情况下没问题，但如果遇到...情况，会不会有隐患？”
    3. **单点提问**：
       - 每次回复**只问 1 个核心问题**。
       - 严禁使用 "1. 2. 3." 列表形式发问。
    4. **字数限制**：
       - 保持简练，每次回复控制在 **150 字以内**。

    【开场剧本】
    用户开场后，你必须严格回复（不要发挥）：
    “你好。我是负责【{job}】的面试官。
    本次面试难度为 L{level}，重点考察{focus_point}。
    请先列出你最擅长的一个技术栈或框架，我们直接结合实际业务场景来聊聊。”

    现在，请进入角色。
    """

    # 调试打印，方便在控制台看当前 Prompt 逻辑
    print(f"--- [DEBUG] Job:{job} | Level:{level} ---")

    messages = [
        {
            "role": "system",
            "content": system_prompt_content
        }
    ]

    # --- 4. 拼接历史记录 ---
    if history:
        for msg in history:
            # 只保留用户和AI的对话，过滤掉旧的 system prompt
            if msg.get('role') in ['user', 'assistant']:
                messages.append(msg)

    # --- 5. 发送请求 ---
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=True,
            temperature=0.7,  # 稍微降低温度，保持稳重
            max_tokens=500  # 限制最大输出，防止AI长篇大论
        )

        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    except Exception as e:
        print(f"DeepSeek API 请求失败: {e}")
        yield f"[系统错误]: {str(e)}"