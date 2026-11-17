import time

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


SAMPLE_TEXT = """# 高效学习

间隔重复是一种通过逐步增加复习间隔来巩固记忆的学习方法。它要求学习者在即将遗忘时再次接触材料，而不是连续重复阅读。

主动回忆指在不查看答案的情况下尝试提取信息。与被动阅读相比，主动回忆能更清楚地暴露知识盲点，并加强记忆路径。

实践时，应先制作问题明确的卡片，再根据自己的回忆质量安排复习。每张卡片只保留一个核心问题，避免把整段笔记直接复制到答案中。
"""


def wait_completed(client, material_id: int, timeout: float = 10) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/api/materials/{material_id}").json()["status"]
        if status in ("completed", "failed"):
            return status
        time.sleep(0.05)
    raise TimeoutError(f"材料 {material_id} 未在 {timeout}s 内完成")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("API_KEY", "")
    with TestClient(create_app()) as test_client:
        yield test_client
