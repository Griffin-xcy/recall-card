import io
import zipfile

from reportlab.pdfgen import canvas

from .conftest import SAMPLE_TEXT, wait_completed


def ingest_text(client, title="高效学习", content=SAMPLE_TEXT):
    response = client.post("/api/materials/text", json={"title": title, "content": content})
    assert response.status_code == 201, response.text
    material_id = response.json()["material"]["id"]
    assert wait_completed(client, material_id) == "completed"
    return client.get(f"/api/materials/{material_id}").json()


def test_health_and_empty_state(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["model_configured"] is True
    assert client.get("/api/cards").json() == []
    stats = client.get("/api/stats").json()
    assert (stats["cards"], stats["materials"], stats["topics"]) == (0, 0, 0)
    assert stats["known_cards"] == 0 and stats["again_cards"] == 0


def test_text_ingestion_generates_cards(client):
    material = ingest_text(client)
    assert material["status"] == "completed"
    cards = client.get("/api/cards").json()
    assert len(cards) >= 3
    assert {card["kind"] for card in cards} >= {"知识点", "问答"}
    assert client.get("/api/stats").json()["cards"] == len(cards)
    assert client.get("/api/topics").json()[0]["count"] >= 1


def test_card_filter_edit_and_delete(client):
    ingest_text(client)
    card = client.get("/api/cards").json()[0]
    response = client.patch(
        f"/api/cards/{card['id']}",
        json={"title": "间隔重复", "topic": "技术知识", "tags": ["学习", "记忆"]},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "间隔重复"
    assert response.json()["topic"] == "技术知识"
    assert client.get("/api/cards", params={"topic": "技术知识", "q": "间隔"}).json()[0]["id"] == card["id"]
    assert client.delete(f"/api/cards/{card['id']}").status_code == 204
    assert client.get(f"/api/cards/{card['id']}").status_code == 404


def test_markdown_upload_and_export(client):
    response = client.post(
        "/api/materials/file",
        files={"file": ("notes.md", SAMPLE_TEXT.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 201, response.text
    assert wait_completed(client, response.json()["material"]["id"]) == "completed"
    exported = client.get("/api/export/markdown")
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        names = archive.namelist()
        assert "README.md" in names
        topic_file = next(name for name in names if name.startswith("topics/"))
        content = archive.read(topic_file).decode("utf-8")
        assert "来源" in content
        assert "notes" in content


def test_directory_upload_preserves_relative_source_path(client):
    response = client.post(
        "/api/materials/file",
        data={"source_path": "课程/第三章/notes.md"},
        files={"file": ("notes.md", SAMPLE_TEXT.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["material"]["source_uri"] == "课程/第三章/notes.md"


def test_python_source_upload(client):
    source = b"""def spaced_repetition():\n    # Review information just before it is likely to be forgotten.\n    return 'Schedule increasingly spaced reviews to strengthen long-term memory.'\n"""
    response = client.post(
        "/api/materials/file",
        files={"file": ("study.py", source, "text/x-python")},
    )
    assert response.status_code == 201, response.text
    material_id = response.json()["material"]["id"]
    assert wait_completed(client, material_id) == "completed"
    assert response.json()["material"]["title"] == "study"
    assert len(client.get("/api/cards").json()) >= 3


def test_pdf_upload(client):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 760, "Spaced repetition strengthens memory by scheduling reviews over time.")
    pdf.drawString(72, 730, "Active recall helps learners identify gaps in their knowledge.")
    pdf.save()
    response = client.post(
        "/api/materials/file",
        files={"file": ("learning.pdf", buffer.getvalue(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    material_id = response.json()["material"]["id"]
    assert wait_completed(client, material_id) == "completed"
    assert response.json()["material"]["source_type"] == "file"
    assert len(client.get("/api/cards").json()) >= 3


def test_web_url_entry(client, monkeypatch):
    async def fake_extract(url):
        return "示例网页", SAMPLE_TEXT

    monkeypatch.setattr("backend.main.extract_webpage", fake_extract)
    response = client.post("/api/materials/url", json={"url": "https://example.com/article"})
    assert response.status_code == 201, response.text
    material_id = response.json()["material"]["id"]
    assert wait_completed(client, material_id) == "completed"
    assert response.json()["material"]["source_uri"] == "https://example.com/article"


def test_invalid_inputs_have_clear_errors(client):
    assert client.post("/api/materials/text", json={"title": "短", "content": "太短"}).status_code == 422
    response = client.post(
        "/api/materials/file", files={"file": ("bad.exe", b"\x00\x01\x02\x03" * 8, "application/octet-stream")}
    )
    assert response.status_code == 422
    assert "不是可读取的文本或代码文件" in response.json()["detail"]


def test_model_settings_save_without_echo_and_persist(client):
    response = client.put(
        "/api/settings",
        json={"base_url": "https://api.deepseek.com/v1/", "api_key": "test-secret-key", "model": "deepseek-chat"},
    )
    assert response.status_code == 200
    assert response.json()["model_configured"] is True
    assert response.json()["provider"] == "openai"
    assert response.json()["base_url"] == "https://api.deepseek.com/v1"
    assert "test-secret-key" not in response.text

    from fastapi.testclient import TestClient
    from backend.main import create_app

    with TestClient(create_app()) as restarted:
        health = restarted.get("/api/health")
        assert health.json()["model_configured"] is True
        assert health.json()["model"] == "deepseek-chat"
        assert "test-secret-key" not in health.text


def test_model_settings_reject_invalid_url(client):
    response = client.put("/api/settings", json={"base_url": "not-a-url", "api_key": "key", "model": "model"})
    assert response.status_code == 422


def test_review_state_roundtrip(client):
    material = ingest_text(client)
    assert material["status"] == "completed"
    card_id = client.get("/api/cards").json()[0]["id"]

    known = client.post(f"/api/cards/{card_id}/review", json={"state": "known"})
    assert known.status_code == 200
    assert known.json()["review_state"] == "known"
    assert known.json()["reviewed_at"], "标记后应该有复习时间"

    again = client.post(f"/api/cards/{card_id}/review", json={"state": "again"}).json()
    assert again["review_state"] == "again"
    assert client.get("/api/stats").json()["again_cards"] == 1

    reset = client.post(f"/api/cards/{card_id}/review", json={"state": "new"}).json()
    assert reset["review_state"] == "new"
    assert reset["reviewed_at"] == ""
    assert client.get("/api/stats").json()["reviewed_cards"] == 0

    assert client.post("/api/cards/999999/review", json={"state": "known"}).status_code == 404
    assert client.post(f"/api/cards/{card_id}/review", json={"state": "unknown"}).status_code == 422


def test_bulk_update_and_delete(client):
    ingest_text(client)
    ids = [card["id"] for card in client.get("/api/cards").json()]
    assert len(ids) >= 3

    marked = client.post("/api/cards/bulk-update", json={"ids": ids[:2], "review_state": "known"})
    assert marked.status_code == 200
    assert marked.json()["updated"] == 2
    assert client.get("/api/stats").json()["known_cards"] == 2

    topic = client.get("/api/config").json()["topics"][2]
    moved = client.post("/api/cards/bulk-update", json={"ids": ids, "topic": topic})
    assert moved.json()["updated"] == len(ids)
    assert {card["topic"] for card in client.get("/api/cards").json()} == {topic}

    assert client.post("/api/cards/bulk-update", json={"ids": [], "review_state": "known"}).status_code == 422
    assert client.post("/api/cards/bulk-update", json={"ids": ids, "topic": "不存在的主题"}).status_code == 422
    assert client.post("/api/cards/bulk-update", json={"ids": ids}).status_code == 422

    deleted = client.post("/api/cards/bulk-delete", json={"ids": ids[:2]})
    assert deleted.json()["deleted"] == 2
    assert len(client.get("/api/cards").json()) == len(ids) - 2
