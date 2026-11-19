import time

from .conftest import SAMPLE_TEXT, wait_completed


def _file_payload(filename="notes.md", content=SAMPLE_TEXT):
    return {"file": (filename, content.encode("utf-8"), "text/markdown")}


def _ingest_text(client, title="A", content=SAMPLE_TEXT):
    response = client.post("/api/materials/text", json={"title": title, "content": content})
    assert response.status_code == 201, response.text
    material_id = response.json()["material"]["id"]
    assert wait_completed(client, material_id) == "completed"
    return client.get(f"/api/materials/{material_id}").json()


def _wait_cards(client, count: int, timeout: float = 5) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        cards = client.get("/api/cards").json()
        if len(cards) == count:
            return cards
        time.sleep(0.05)
    return client.get("/api/cards").json()


def test_duplicate_file_upload_skips_second_time(client):
    first = client.post("/api/materials/file", files=_file_payload())
    assert first.status_code == 201
    assert first.json()["duplicate"] is False
    assert wait_completed(client, first.json()["material"]["id"]) == "completed"

    second = client.post("/api/materials/file", files=_file_payload())
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["cards"] == []
    assert client.get("/api/stats").json()["materials"] == 1


def test_same_content_across_directories_dedup(client):
    first = client.post("/api/materials/file", files=_file_payload(), data={"source_path": "课程/第一章/notes.md"})
    assert first.status_code == 201
    assert wait_completed(client, first.json()["material"]["id"]) == "completed"

    second = client.post(
        "/api/materials/file",
        files=_file_payload("copy.md"),
        data={"source_path": "课程/第二章/copy.md"},
    )
    assert second.status_code == 200
    assert second.json()["duplicate"] is True


def test_cross_material_card_dedup(client):
    _ingest_text(client)
    assert len(client.get("/api/cards").json()) == 3
    second = client.post(
        "/api/materials/text",
        json={"title": "B", "content": "第二章：间隔重复通过逐步增加复习间隔巩固记忆。这是另一份学习材料。"},
    )
    assert wait_completed(client, second.json()["material"]["id"]) == "completed"
    cards = client.get("/api/cards").json()
    second_cards = [card for card in cards if card["material_id"] == second.json()["material"]["id"]]
    assert [card["kind"] for card in second_cards] == ["概念"]
    assert len(cards) == 4


def test_failed_file_can_be_reimported(client, monkeypatch):
    import backend.main as main_mod
    from backend.llm import LLMError

    original = main_mod.process_material
    calls = {"n": 0}

    async def flaky(db, settings, material_id):
        calls["n"] += 1
        if calls["n"] == 1:
            db.set_material_status(material_id, "failed", "模拟失败")
            raise LLMError("模拟失败")
        return await original(db, settings, material_id)

    monkeypatch.setattr(main_mod, "process_material", flaky)
    first = client.post("/api/materials/file", files=_file_payload())
    assert first.status_code == 201
    assert wait_completed(client, first.json()["material"]["id"]) == "failed"

    second = client.post("/api/materials/file", files=_file_payload())
    assert second.status_code == 201
    assert second.json()["duplicate"] is False
    assert wait_completed(client, second.json()["material"]["id"]) == "completed"


def test_card_edit_duplicate_returns_error(client):
    _ingest_text(client)
    cards = client.get("/api/cards").json()
    qa = next(card for card in cards if card["kind"] == "操作")
    other = next(card for card in cards if card["kind"] != "操作")
    response = client.patch(f"/api/cards/{other['id']}", json={"question": qa["question"]})
    assert response.status_code == 422
    assert "相同" in response.json()["detail"]


def test_regenerate_material_clears_and_rebuilds(client):
    material = _ingest_text(client)
    material_id = material["id"]
    cards = client.get("/api/cards").json()
    client.delete(f"/api/cards/{cards[0]['id']}")
    response = client.post(f"/api/materials/{material_id}/regenerate")
    assert response.status_code == 200
    cards = _wait_cards(client, 3)
    assert len(cards) >= 3


def test_delete_material_cascades_cards(client):
    material = _ingest_text(client)
    material_id = material["id"]
    assert client.delete(f"/api/materials/{material_id}").status_code == 204
    assert client.get("/api/cards").json() == []
    assert client.delete(f"/api/materials/{material_id}").status_code == 404
    assert client.post(f"/api/materials/{material_id}/regenerate").status_code == 404


def test_force_import_overwrites_duplicate(client):
    first = _ingest_text(client)
    first_id = first["id"]
    first_card_id = client.get("/api/cards").json()[0]["id"]

    response = client.post("/api/materials/file", files=_file_payload(), data={"force": "true"})
    assert response.status_code == 201
    assert response.json()["duplicate"] is False
    assert response.json()["material"]["id"] == first_id
    _wait_cards(client, 3)
    assert client.get(f"/api/cards/{first_card_id}").status_code == 404
    assert client.get("/api/stats").json()["materials"] == 1


def test_regenerate_failure_rolls_back_cards(client, monkeypatch):
    import backend.main as main_mod
    from backend.llm import LLMError

    material = _ingest_text(client)
    material_id = material["id"]
    original_cards = client.get("/api/cards").json()
    assert len(original_cards) == 3

    async def flaky(db, settings, material_id):
        raise LLMError("模拟失败")

    monkeypatch.setattr(main_mod, "process_material", flaky)
    response = client.post(f"/api/materials/{material_id}/regenerate")
    assert response.status_code == 200

    cards = _wait_cards(client, 3)
    assert [card["id"] for card in cards] == [card["id"] for card in original_cards]
    assert client.get(f"/api/materials/{material_id}").json()["status"] == "completed"


def test_force_failure_preserves_original(client, monkeypatch):
    import backend.main as main_mod
    from backend.llm import LLMError

    first = client.post("/api/materials/file", files=_file_payload())
    first_id = first.json()["material"]["id"]
    assert wait_completed(client, first_id) == "completed"
    original_cards = client.get("/api/cards").json()
    assert len(original_cards) == 3

    async def flaky(db, settings, material_id):
        raise LLMError("模拟失败")

    monkeypatch.setattr(main_mod, "process_material", flaky)
    response = client.post("/api/materials/file", files=_file_payload(), data={"force": "true"})
    assert response.status_code == 201

    cards = _wait_cards(client, 3)
    assert [card["id"] for card in cards] == [card["id"] for card in original_cards]
    assert client.get(f"/api/materials/{first_id}").json()["status"] == "completed"
