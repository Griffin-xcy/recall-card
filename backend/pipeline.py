import logging
import re

from .config import Settings
from .db import Database
from .llm import generate_cards

logger = logging.getLogger(__name__)


def chunk_text(text: str, limit: int = 3_500) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        while len(paragraph) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(paragraph[:limit])
            paragraph = paragraph[limit:]
        if len(current) + len(paragraph) + 2 > limit and current:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks


def fingerprint(text: str) -> str:
    return re.sub(r"\W+", "", text).lower()


async def process_material(db: Database, settings: Settings, material_id: int) -> list[dict]:
    material = db.get_material(material_id)
    chunks = chunk_text(material["content"])
    topics = db.list_topics()
    kinds = db.list_kinds()
    logger.info("材料 #%s 开始处理，共 %d 个分块", material_id, len(chunks))
    seen: set[str] = set()
    duplicate_cards = 0
    try:
        for chunk in chunks:
            generated = await generate_cards(chunk, material["title"], settings, topics, kinds)
            logger.info("材料 #%s 分块生成 %d 张卡片", material_id, len(generated))
            for card in generated:
                data = card.model_dump()
                key = fingerprint(data["question"] or data["title"])
                if not key or key in seen:
                    continue
                seen.add(key)
                if db.add_card(material_id, data) is None:
                    duplicate_cards += 1
        result = db.cards_for_material(material_id)
        if not result and duplicate_cards == 0:
            raise ValueError("模型没有从材料中提取出有效卡片，请换一份更具体的材料")
        db.set_material_status(material_id, "completed")
        logger.info("材料 #%s 处理完成，共 %d 张卡片", material_id, len(result))
        return result
    except Exception as exc:
        logger.error("材料 #%s 处理失败：%s", material_id, exc)
        db.set_material_status(material_id, "failed", str(exc))
        raise
