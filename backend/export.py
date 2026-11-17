import io
import re
import zipfile
from collections import defaultdict
from datetime import date


def safe_filename(value: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "-", value).strip() or "未命名"


def escape_markdown(text: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+\-.!>|~])", r"\\\1", text)


def markdown_for_topic(topic: str, cards: list[dict]) -> str:
    lines = [f"# {escape_markdown(topic)}", "", f"> 由拾记导出，共 {len(cards)} 张卡片。", ""]
    for card in cards:
        lines.extend([
            f"## {escape_markdown(card['title'])}", "",
            f"**类型**：{escape_markdown(card['kind'])}  ",
            f"**来源**：{escape_markdown(card['material_title'])}  ",
        ])
        if card["tags"]:
            lines.append(f"**标签**：{escape_markdown('、'.join(card['tags']))}  ")
        lines.append("")
        if card["question"]:
            lines.extend([f"**问**：{escape_markdown(card['question'])}", ""])
        lines.extend([escape_markdown(card["answer"]), "", "---", ""])
    return "\n".join(lines)


def build_markdown_zip(cards: list[dict]) -> bytes:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for card in cards:
        grouped[card["topic"]].append(card)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        index = ["# 拾记卡片导出", "", f"导出日期：{date.today().isoformat()}", "", f"共 {len(cards)} 张卡片，{len(grouped)} 个主题。", "", "## 主题目录", ""]
        for topic, topic_cards in sorted(grouped.items()):
            filename = f"topics/{safe_filename(topic)}.md"
            index.append(f"- [{topic}]({filename})（{len(topic_cards)} 张）")
            archive.writestr(filename, markdown_for_topic(topic, topic_cards))
        archive.writestr("README.md", "\n".join(index) + "\n")
    return buffer.getvalue()
