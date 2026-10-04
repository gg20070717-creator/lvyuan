"""Tool definitions for all agents in the system.
Each agent registers tools that other agents can call via function calling."""

from brain_of_cloud.tools.types import ToolDef

# --- Knowledge Retrieval ---
SEARCH_KNOWLEDGE = ToolDef(
    name="search_knowledge",
    description="搜索导游知识库（3796 个技能点：全国导游教材、跨文化、入境游实战、真实岗位实务、旅游定制师、入境游接待等）。当学员问到专业知识、法规、历史、文化、旅游地理、跨文化或入境游实操时调用。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索查询（用中文描述想查的知识点）"},
            "knowledge_point_ids": {
                "type": "array", "items": {"type": "string"},
                "description": "限定技能点 ID 范围，空数组表示搜索全部",
            },
        },
        "required": ["query"],
    },
)

# --- Content Generation ---
GENERATE_MATERIAL = ToolDef(
    name="generate_material",
    description="根据知识库证据生成学习材料文件（讲义、考点总结、笔记、文档、实操指南、答题模板等）。"
    "学员要求「讲义/笔记/总结/文档/材料/指南/模板/考点整理/整理成文档/做成文件/复习资料」时**必须**调用，"
    "生成后必须调用 review_material 审查。生成后材料自动保存为学习中心资产。",
    parameters={
        "type": "object",
        "properties": {
            "request": {"type": "string", "description": "学员的具体需求描述"},
            "evidence": {"type": "string", "description": "从search_knowledge获取的证据 JSON 字符串，原样传入（可只取前 2 条结果以节省空间）"},
        },
        "required": ["request", "evidence"],
    },
)

# --- Quality Review ---
REVIEW_MATERIAL = ToolDef(
    name="review_material",
    description="对生成的训练材料进行六帽质量审查（白帽事实/黑帽逻辑/绿帽创意/黄帽激励/红帽个性适配/蓝帽协调）。在交付材料给学员前必须调用。",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "待审查的训练材料全文"},
        },
        "required": ["content"],
    },
)

# --- Training ---
ACTIVATE_SKILL = ToolDef(
    name="activate_skill",
    description=(
        "根据学员的真实学习进度点亮技能树节点。当学员在对话或训练中确认掌握了某个能力"
        "（如讲明白了某类知识点、连续答对相关题目、训练获得高分）时主动调用；"
        "技能树由系统根据学习进度自动生长，学员不需要任何手动操作。"
        "节点 ID 参考：L1-L4 语言表达 / E1-E4 文化礼仪 / G1-G4 讲解带团 / M1-M4 应急处置 / "
        "D1-D4 数字工具 / A1-A4 美学素养 / S1-S4 服务设计 / T1-T4 团队管理。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "node_id": {"type": "string", "description": "技能节点 ID（如 L1/E2/G3/M1）"},
            "reason": {"type": "string", "description": "点亮理由：学员掌握了什么（一句话）"},
        },
        "required": ["node_id", "reason"],
    },
)

SET_TEACHING_TOPIC = ToolDef(
    name="set_teaching_topic",
    description=(
        "锁定或切换当前教学主题（一对一教学的「这节课学什么」）。"
        "开始讲解一个新知识点、或学员明确表示要换一个主题学时调用；"
        "knowledge_point_ids 用 search_knowledge 结果里的技能点 ID（通常 1-3 个）。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "knowledge_point_ids": {
                "type": "array", "items": {"type": "string"},
                "description": "本次教学主题的技能点 ID 列表（来自 search_knowledge 结果的 knowledge_point_ids）",
            },
        },
        "required": ["knowledge_point_ids"],
    },
)

QUIZ_USER = ToolDef(
    name="quiz_user",
    description=(
        "从 30944 道导游考试题库题目中为学员抽题测试。教学铁律：必须先完成讲解并确认学员理解，"
        "才能出题；knowledge_point_ids 必须传当前教学主题的技能点 ID，禁止空数组随机抽题。"
        "唯一例外：仅当学员明确要求「随机考/摸底/随便考」时，才可传空数组并设 random_mode='explicit'。"
        "难度不传则自动按学员掌握度适配。题目会以答题卡片自动展示，出题后不要在聊天里复述题干或选项原文。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "knowledge_point_ids": {
                "type": "array", "items": {"type": "string"},
                "description": "要测试的技能点 ID（必须来自当前教学主题）；仅随机模式传空数组",
            },
            "difficulty": {
                "type": "string",
                "description": "难度：intro/basic/advanced/comprehensive，留空自动适配",
            },
            "random_mode": {
                "type": "string",
                "description": "仅当学员明确要求随机抽题/摸底时传 'explicit'，其余情况必须留空",
            },
        },
        "required": [],
    },
)

GENERATE_REPORT = ToolDef(
    name="generate_report",
    description="生成学员的学习报告，包含 3796 个技能点上的掌握度分析和改进建议。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)

GENERATE_PLAN = ToolDef(
    name="generate_plan",
    description="为学员生成个性化备考学习计划（结合画像、薄弱点、掌握度）。当学员问「怎么学」「该学什么」「给我个计划」时调用。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)

SUBMIT_ANSWER = ToolDef(
    name="submit_answer",
    description="提交学员对题目的回答并判分。当学员回答了刚才的测试题后调用："
    "选择题提交选项字母（学员说「我选A」→ answer='A'，question_type 留空/choice）；"
    "简答题提交学员文字回答（学员说「我的回答：…」→ answer=文字，question_type='essay'）。",
    parameters={
        "type": "object",
        "properties": {
            "question_id": {"type": "string", "description": "题目 ID（quiz_user 或 generate_essay_question 返回的 question_id）"},
            "answer": {"type": "string", "description": "学员答案（选择题填选项字母 A/B/C/D，简答题填文字）"},
            "question_type": {
                "type": "string",
                "description": "题目类型：choice（选择题，默认）/ essay（简答题，AI 原创题）",
            },
        },
        "required": ["question_id", "answer"],
    },
)

GENERATE_ESSAY_QUESTION = ToolDef(
    name="generate_essay_question",
    description=(
        "为学员出进阶简答题（AI 根据正在讲的内容原创开放题，比选择题更难）。"
        "教学铁律：仅当当前教学主题的相关选择题已全部做完（quiz_user 返回的 "
        "progress.exhausted=true，或返回消息提示「选择题已全部做完」）时才能调用；"
        "knowledge_point_ids 必须传当前教学主题的技能点 ID，禁止空数组。"
        "出题前先向学员推荐进阶内容并征得同意。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "knowledge_point_ids": {
                "type": "array", "items": {"type": "string"},
                "description": "要出简答题的技能点 ID（必须来自当前教学主题）",
            },
        },
        "required": [],
    },
)

# --- Profile ---
UPDATE_PROFILE = ToolDef(
    name="update_profile",
    description="更新学员画像与长期记忆。当学员提供了关于自己背景/目标/水平/偏好的新信息时调用。",
    parameters={
        "type": "object",
        "properties": {
            "background": {"type": "string", "description": "学员自述背景，尽量包含目标与当前水平"},
        },
        "required": ["background"],
    },
)

FINISH_TOPIC = ToolDef(
    name="finish_topic",
    description="宣告当前技能点题目全部完成并弹出「完成去向卡」（再学一个技能点 / 去5★沙盒实战 / 自由问答）。当选择题与题库简答题都做完，或学员明确表示不再做剩余题目时调用；不要只说收工而不调用本工具。",
    parameters={"type": "object", "properties": {}, "required": []},
)



# --- 先验画像 · 身份题（管家对话式，与出题同款） ---
ASK_IDENTITY_QUESTION = ToolDef(
    name="ask_identity_question",
    description="先验学情画像的固定题卡：向学员出示当前一道身份题（题干+选项，前端以答题卡片展示）。仅当学员尚未完成先验画像且当前对话在做画像身份问答时调用；答完后可继续调用以出下一题。",
    parameters={"type": "object", "properties": {}, "required": []},
)

SUBMIT_IDENTITY_ANSWER = ToolDef(
    name="submit_identity_answer",
    description="记录学员对当前身份题的作答并推进到下一题。学员回答后必须调用；answer 传选项字母（A/B/C/D）或选项原文。",
    parameters={
        "type": "object",
        "properties": {"answer": {"type": "string", "description": "学员答案：选项字母 A/B/C/D 或选项原文"}},
        "required": ["answer"],
    },
)

# All tools available to the Concierge
CONCIERGE_TOOLS = [
    SEARCH_KNOWLEDGE,
    SET_TEACHING_TOPIC,
    ACTIVATE_SKILL,
    GENERATE_MATERIAL,
    REVIEW_MATERIAL,
    QUIZ_USER,
    SUBMIT_ANSWER,
    GENERATE_ESSAY_QUESTION,
    GENERATE_REPORT,
    GENERATE_PLAN,
    UPDATE_PROFILE,
    FINISH_TOPIC,
    ASK_IDENTITY_QUESTION,
    SUBMIT_IDENTITY_ANSWER,
]





