import json
import logging
import re
import time
from typing import Any

import httpx

from .config import KIND_GUIDE, Settings
from .schemas import GeneratedCard

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


def build_system_prompt(topics: list[str], kinds: list[str]) -> str:
    guide = "；".join(f"{name}={desc}" for name, desc in KIND_GUIDE.items() if name in kinds)
    fallback = kinds[0] if kinds else "概念"
    kind_rule = f"判断依据：{guide}。都套不上时用「{fallback}」，不要硬凑。" if guide else ""
    return f"""你是信息整理助手。把材料转成适合长期复习的卡片，不写空泛总结。
只输出 JSON 对象，格式为 {{"cards": [...]}}。每张卡片包含：
- topic：必须从 {topics} 中选择；
- kind：必须从 {kinds} 中选择。{kind_rule}
- title：不超过 30 字的明确主题；
- question：能问成具体问题的写成问答，其他卡可留空；
- answer：准确保留材料中的事实、条件、结论或操作，不补充材料外知识；
- tags：1 到 4 个简短标签。
优先提炼有信息量的内容，合并重复项。没有合适内容时返回空数组。"""


def parse_json(content: str) -> dict[str, Any]:
    stripped = content.strip()
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.DOTALL)
    try:
        result = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise LLMError("模型返回的内容不是有效 JSON") from exc
    if not isinstance(result, dict) or not isinstance(result.get("cards"), list):
        raise LLMError("模型返回的 JSON 缺少 cards 数组")
    return result


def mock_cards(text: str) -> list[dict[str, Any]]:
    """Deterministic local provider for demos and automated tests."""
    sentences = [item.strip() for item in re.split(r"(?<=[。！？.!?])\s+|\n+", text) if len(item.strip()) >= 12]
    if not sentences:
        sentences = [text.strip()[:500]]
    primary = sentences[0][:500]
    detail = sentences[1][:500] if len(sentences) > 1 else primary
    return [
        {"topic": "学习笔记", "kind": "概念", "title": primary[:28], "question": "", "answer": primary, "tags": ["核心概念"]},
        {"topic": "学习笔记", "kind": "操作", "title": "关键内容回顾", "question": "这份材料强调了什么关键内容？", "answer": detail, "tags": ["复习"]},
        {"topic": "学习笔记", "kind": "易错点", "title": "后续行动", "question": "", "answer": f"回顾并确认：{detail}", "tags": ["待办"]},
    ]


async def generate_cards(text: str, source_title: str, settings: Settings, topics: list[str], kinds: list[str]) -> list[GeneratedCard]:
    if settings.llm_provider == "mock":
        raw_cards = mock_cards(text)
    else:
        if not settings.api_key:
            raise LLMError("尚未配置模型 API Key。请复制 .env.example 为 .env 并填写 api_key")
        endpoint = settings.base_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        payload = {
            "model": settings.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": build_system_prompt(topics, kinds)},
                {"role": "user", "content": f"材料标题：{source_title}\n\n材料正文：\n{text}"},
            ],
        }
        last_error = ""
        raw_cards = None
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            for _ in range(2):
                try:
                    response = await client.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {settings.api_key}"},
                        json=payload,
                    )
                    response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]
                    raw_cards = parse_json(content)["cards"]
                    break
                except (httpx.HTTPError, KeyError, IndexError, TypeError, LLMError) as exc:
                    last_error = str(exc)
                    payload["messages"].append({"role": "user", "content": "上次输出无法解析。请严格只返回规定格式的 JSON 对象。"})
        logger.info("LLM 调用完成，耗时 %.2fs，模型 %s", time.monotonic() - started, settings.model)
        if raw_cards is None:
            logger.error("LLM 处理失败：%s", last_error)
            raise LLMError(f"模型处理失败：{last_error}")

    cards: list[GeneratedCard] = []
    for raw in raw_cards:
        try:
            if not isinstance(raw, dict):
                continue
            if raw.get("topic") not in topics:
                raw["topic"] = "其他" if "其他" in topics else (topics[0] if topics else "其他")
            if raw.get("kind") not in kinds:
                raw["kind"] = kinds[0] if kinds else "概念"
            cards.append(GeneratedCard.model_validate(raw))
        except (ValueError, TypeError):
            continue
    return cards
