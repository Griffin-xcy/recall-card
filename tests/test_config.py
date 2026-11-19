def test_config_returns_defaults(client):
    config = client.get("/api/config").json()
    assert "学习笔记" in config["topics"]
    assert "概念" in config["kinds"]
    assert "面试考点" in config["kinds"]
    assert len(config["topics"]) == 6
    assert len(config["kinds"]) == 5


def test_add_and_delete_topic(client):
    response = client.post("/api/config/topics", json={"name": "家庭事务"})
    assert response.status_code == 201
    assert "家庭事务" in response.json()["topics"]
    assert client.delete("/api/config/topics/家庭事务").status_code == 204
    assert "家庭事务" not in client.get("/api/config").json()["topics"]


def test_add_and_delete_kind(client):
    response = client.post("/api/config/kinds", json={"name": "灵感"})
    assert response.status_code == 201
    assert "灵感" in response.json()["kinds"]
    assert client.delete("/api/config/kinds/灵感").status_code == 204
    assert "灵感" not in client.get("/api/config").json()["kinds"]


def test_add_duplicate_topic_returns_409(client):
    assert client.post("/api/config/topics", json={"name": "学习笔记"}).status_code == 409


def test_delete_missing_topic_returns_404(client):
    assert client.delete("/api/config/topics/不存在").status_code == 404


def test_legacy_kinds_migrate_to_learning_kinds(tmp_path):
    from backend.config import LEGACY_CARD_KINDS
    from backend.db import Database

    path = tmp_path / "legacy.db"
    db = Database(path)
    with db.connect() as connection:
        connection.execute("DELETE FROM card_kinds")
        connection.executemany(
            "INSERT INTO card_kinds(name, created_at) VALUES (?, '')",
            [(kind,) for kind in LEGACY_CARD_KINDS],
        )
    material = db.create_material("旧材料", "text", "", "旧内容")
    db.add_card(material["id"], {"topic": "学习笔记", "kind": "知识点", "title": "旧卡一", "question": "", "answer": "答案", "tags": []})
    db.add_card(material["id"], {"topic": "学习笔记", "kind": "决策", "title": "旧卡二", "question": "", "answer": "答案", "tags": []})

    migrated = Database(path)
    kinds = migrated.list_kinds()
    assert "概念" in kinds and "面试考点" in kinds
    assert "知识点" not in kinds and "决策" not in kinds
    assert sorted(card["kind"] for card in migrated.list_cards()) == ["原理", "概念"]
