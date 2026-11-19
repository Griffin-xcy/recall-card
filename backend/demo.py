"""首次启动时写入的示例卡片。

目的：让没有 API Key 的用户也能立刻看到这个工具长什么样、能干什么。
这些卡片是写死的，不调用任何模型，用户可以随时删掉。
"""

from .db import Database


DEMO_TITLE = "示例：间隔重复怎么用"

DEMO_CONTENT = """间隔重复是一种通过逐步增加复习间隔来巩固记忆的学习方法。它要求学习者在即将遗忘时再次接触材料，而不是连续重复阅读。

主动回忆指在不查看答案的情况下尝试提取信息。与被动阅读相比，主动回忆能更清楚地暴露知识盲点，并加强记忆路径。

实践时，应先制作问题明确的卡片，再根据自己的回忆质量安排复习。每张卡片只保留一个核心问题，避免把整段笔记直接复制到答案中。

材料越具体，提取出的卡片越有用。一份写得含糊的笔记，只会产出看起来正确但没法复习的卡片。"""

DEMO_CARDS = [
    {
        "topic": "学习笔记",
        "kind": "知识点",
        "title": "什么是间隔重复",
        "question": "",
        "answer": "一种通过逐步增加复习间隔来巩固记忆的方法，要求在即将遗忘时再次接触材料，而不是连续重复阅读。",
        "tags": ["学习方法", "记忆"],
    },
    {
        "topic": "学习笔记",
        "kind": "知识点",
        "title": "什么是主动回忆",
        "question": "",
        "answer": "在不查看答案的情况下尝试提取信息。相比被动阅读，它更能暴露知识盲点，并加强记忆路径。",
        "tags": ["学习方法", "自测"],
    },
    {
        "topic": "学习笔记",
        "kind": "问答",
        "title": "为什么主动回忆比重复阅读有效",
        "question": "为什么主动回忆比反复阅读更有效？",
        "answer": "因为提取过程会暴露你真正没掌握的部分，反复阅读只会带来「我好像会了」的错觉。",
        "tags": ["原理", "复习"],
    },
    {
        "topic": "学习笔记",
        "kind": "问答",
        "title": "卡片应该写多长",
        "question": "一张卡片应该写多长？",
        "answer": "一张卡片只保留一个核心问题，不要把整段笔记复制进答案，否则复习时无法判断自己是否真的会。",
        "tags": ["卡片设计"],
    },
    {
        "topic": "学习笔记",
        "kind": "行动项",
        "title": "做卡片前先确认素材质量",
        "question": "",
        "answer": "材料越具体，提取出的卡片越有用；素材含糊，只会产出看起来正确但没法复习的卡片。",
        "tags": ["待办", "质量"],
    },
    {
        "topic": "工作会议",
        "kind": "决策",
        "title": "复习节奏由回忆质量决定",
        "question": "",
        "answer": "不再按固定天数复习，改为根据每次回忆的难易程度决定下一次间隔。",
        "tags": ["决策", "节奏"],
    },
]


def seed_demo(db: Database) -> bool:
    """首次启动写入一份示例材料。返回是否真的写入了。

    用 app_settings 里的 demo_seeded 做标记，防止重复写入：
    用户把示例卡片删光后重启，不应该又冒出来一份。
    """
    if db.get_settings().get("demo_seeded") == "1":
        return False
    db.save_settings({"demo_seeded": "1"})

    if db.list_materials():
        return False

    material = db.create_material(DEMO_TITLE, "text", "", DEMO_CONTENT)
    for card in DEMO_CARDS:
        db.add_card(material["id"], card)
    db.set_material_status(material["id"], "completed")
    return True
