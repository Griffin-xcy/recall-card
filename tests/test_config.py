def test_config_returns_defaults(client):
    config = client.get("/api/config").json()
    assert "学习笔记" in config["topics"]
    assert "知识点" in config["kinds"]
    assert len(config["topics"]) == 6
    assert len(config["kinds"]) == 4


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
