import pytest

from backend.export import escape_markdown
from backend.extractor import _is_private_host, extract_text
from backend.llm import LLMError, parse_json
from backend.pipeline import chunk_text, fingerprint


def test_chunk_text_preserves_all_content():
    text = "\n\n".join(f"第 {index} 段，" + "学习内容" * 100 for index in range(12))
    chunks = chunk_text(text, limit=500)
    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)
    assert "".join(chunks).count("学习内容") == text.count("学习内容")


def test_parse_json_accepts_fenced_object():
    assert parse_json('```json\n{"cards": []}\n```') == {"cards": []}


def test_parse_json_rejects_invalid_shape():
    with pytest.raises(LLMError):
        parse_json('{"result": []}')


def test_fingerprint_ignores_punctuation():
    assert fingerprint("主动回忆，是什么？") == fingerprint("主动回忆是什么")


def test_extract_text_utf16():
    text = "间隔重复是一种学习方法。" * 3
    assert extract_text(text.encode("utf-16")) == text


def test_escape_markdown():
    assert escape_markdown("# 标题") == "\\# 标题"
    assert escape_markdown("a*b") == "a\\*b"


def test_private_host_detection():
    assert _is_private_host("localhost") is True
    assert _is_private_host("127.0.0.1") is True
    assert _is_private_host("192.168.1.1") is True
    assert _is_private_host("example.com") is False
