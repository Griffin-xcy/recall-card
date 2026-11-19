"""升级路径测试：用旧版本结构建库，再用当前代码打开，确认能平滑迁移。"""

import sqlite3

from backend.db import Database


OLD_SCHEMA = """
CREATE TABLE materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_uri TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'processing',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    question TEXT NOT NULL DEFAULT '',
    answer TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE topics (name TEXT PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE card_kinds (name TEXT PRIMARY KEY, created_at TEXT NOT NULL);
PRAGMA user_version = 1;
"""


def _make_old_database(path):
    connection = sqlite3.connect(path)
    connection.executescript(OLD_SCHEMA)
    connection.executemany(
        "INSERT INTO card_kinds(name, created_at) VALUES (?, '')",
        [("知识点",), ("问答",), ("行动项",), ("决策",)],
    )
    connection.execute("INSERT INTO topics(name, created_at) VALUES ('学习笔记', '')")
    connection.execute(
        "INSERT INTO materials(title, source_type, source_uri, content, content_hash, status, error, created_at)"
        " VALUES ('老材料', 'text', '', '内容', 'hash', 'completed', '', '2026-01-01T00:00:00+00:00')"
    )
    connection.executemany(
        "INSERT INTO cards(material_id, fingerprint, topic, kind, title, question, answer, tags, created_at, updated_at)"
        " VALUES (1, ?, '学习笔记', ?, ?, '', ?, '[]', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
        [
            ("旧卡一", "知识点", "旧卡一", "旧答案一"),
            ("旧卡二", "问答", "旧卡二", "旧答案二"),
            ("旧卡三", "行动项", "旧卡三", "旧答案三"),
            ("旧卡四", "决策", "旧卡四", "旧答案四"),
        ],
    )
    connection.commit()
    connection.close()


def test_old_database_upgrades_cleanly(tmp_path):
    path = tmp_path / "old.db"
    _make_old_database(path)

    db = Database(path)

    # 列补齐
    with db.connect() as connection:
        card_columns = {row["name"] for row in connection.execute("PRAGMA table_info(cards)")}
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert {"review_state", "reviewed_at"} <= card_columns
    assert version == 2

    # 分类换成学习场景，旧卡片按映射改类
    assert db.list_kinds() == ["概念", "原理", "操作", "易错点", "面试考点"]
    kinds = sorted(card["kind"] for card in db.list_cards())
    assert kinds == sorted(["原理", "概念", "概念", "操作"])

    # 新字段有默认值，不会因为旧数据报错
    assert {card["review_state"] for card in db.list_cards()} == {"new"}
    assert db.stats()["cards"] == 4
    assert db.review_queue()["total"] == 4


def test_custom_kinds_are_not_overwritten(tmp_path):
    path = tmp_path / "custom.db"
    _make_old_database(path)
    connection = sqlite3.connect(path)
    connection.execute("INSERT INTO card_kinds(name, created_at) VALUES ('灵感', '')")
    connection.commit()
    connection.close()

    db = Database(path)
    kinds = db.list_kinds()
    # 用户加过自定义类别，就完全不碰他的配置：不换类、不映射、不塞新默认
    assert "灵感" in kinds
    assert "知识点" in kinds
    assert set(kinds) & {"概念", "原理", "操作", "易错点", "面试考点"} == set()
    assert sorted(card["kind"] for card in db.list_cards()) == sorted(["决策", "知识点", "问答", "行动项"])
