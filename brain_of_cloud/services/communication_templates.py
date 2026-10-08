"""沟通专项：明确区分电话接待与微信咨询，复用真实游客/导演/评分链。"""
from brain_of_cloud.services.sandbox import CustomerProfile, SandboxStage, SandboxTemplate

TEMPLATES = [
    SandboxTemplate(
        template_id="t_comm_phone", mode="communication", title="电话接待 · 确认行程变更", location="接待服务电话",
        task="通过电话安抚游客对行程变更的担忧，核对需求、说明可行方案，并复述下一步安排。",
        difficulty=2, category="电话沟通",
        opening="你接到一位游客的电话。他的航班延误，担心错过当天的接送与游览安排。",
        situation="你正在给旅行定制师打电话，航班延误让你焦虑。你看不到对方的表情，需要他清楚确认信息、说明方案与时间。不要描述面对面动作，所有互动通过电话进行。",
        stages=[
            SandboxStage("问候与信息核对", "确认游客身份、航班与当前需求，先安抚再询问。", "电话沟通用短句，一次核对一项信息。", ["行前访谈", "接站服务"], min_turns=2),
            SandboxStage("调整方案说明", "提供可行调整方案，说明时间与安排。", "清楚说明已确认和待核实的信息，避免空泛保证。", ["游客服务", "行程调整"], min_turns=2),
            SandboxStage("复述与后续联络", "复述游客选择与下一步安排，确认联络方式。", "结束前复述关键时间、接送方式与跟进责任。", ["游客服务", "接站服务"], min_turns=2),
        ],
        goals=[("表达能力",1.3),("服务意识",1.3),("互动引导",1.2)],
        customer_pool=[CustomerProfile("Emma","英国","32","焦虑但愿意沟通","安稳接送与清晰时间安排","常追问还需要等多久","带着年幼孩子，希望减少等待")],
    ),
    SandboxTemplate(
        template_id="t_comm_wechat", mode="communication", title="微信沟通 · 整理旅行需求", location="微信咨询会话",
        task="通过微信询问游客的旅行期待，逐项确认人数、时间、预算与偏好，形成一份清晰的需求摘要。",
        difficulty=2, category="微信沟通",
        opening="一位首次来华的游客发来微信：想在上海玩几天，能帮我安排一下吗？",
        situation="你正在通过微信文字咨询旅行定制师。最初需求模糊，只会透露对方具体问到的信息。消息短而自然，不描述当面动作，不假定语音或电话交流。",
        stages=[
            SandboxStage("破冰与需求追问", "按一个维度一次询问，确认时间、同伴、预算与兴趣。", "微信中分条表达，一次问一个关键问题。", ["需求访谈", "旅行偏好"], min_turns=2),
            SandboxStage("特殊需求确认", "主动询问饮食禁忌、健康状况与同行人的需求。", "避免只问景点偏好，留意游客尚未主动说出的限制。", ["特殊游客服务", "饮食禁忌"], min_turns=2),
            SandboxStage("需求摘要与下一步", "复述需求清单，约定后续方案交付。", "用简洁清单确认需求，明确下一步和时间。", ["需求卡", "特殊游客服务"], min_turns=2),
        ],
        goals=[("表达能力",1.2),("服务意识",1.3),("互动引导",1.3)],
        customer_pool=[CustomerProfile("Lucas","法国","29","随和，需求不明确","城市漫步与当地美食","消息简短，常遗漏关键信息","同伴对花生过敏，需要主动询问")],
    ),
]
