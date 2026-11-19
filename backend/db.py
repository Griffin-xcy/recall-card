import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import CARD_KINDS, KIND_MIGRATION, LEGACY_CARD_KINDS, TOPICS


SCHEMA_VERSION = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def content_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def card_fingerprint(text: str) -> str:
    return re.sub(r"\W+", "", text).lower()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def init(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS materials (
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
                CREATE TABLE IF NOT EXISTS cards (
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
                    updated_at TEXT NOT NULL,
                    review_state TEXT NOT NULL DEFAULT 'new',
                    reviewed_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS topics (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS card_kinds (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.executemany(
                "INSERT OR IGNORE INTO topics(name, created_at) VALUES (?, ?)",
                [(topic, utc_now()) for topic in TOPICS],
            )
            # 旧版本的办公类分类换成学习类分类。
            # 只有类别恰好还是旧默认那四项时才自动迁移，用户自己配过就不碰。
            existing_kinds = {row["name"] for row in connection.execute("SELECT name FROM card_kinds")}
            if existing_kinds == set(LEGACY_CARD_KINDS):
                connection.execute("DELETE FROM card_kinds")
                for old_kind, new_kind in KIND_MIGRATION.items():
                    connection.execute("UPDATE cards SET kind = ? WHERE kind = ?", (new_kind, old_kind))
                existing_kinds = set()
            if not existing_kinds:
                connection.executemany(
                    "INSERT OR IGNORE INTO card_kinds(name, created_at) VALUES (?, ?)",
                    [(kind, utc_now()) for kind in CARD_KINDS],
                )
            material_columns = {row["name"] for row in connection.execute("PRAGMA table_info(materials)")}
            if "content_hash" not in material_columns:
                connection.execute("ALTER TABLE materials ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")
            card_columns = {row["name"] for row in connection.execute("PRAGMA table_info(cards)")}
            if "fingerprint" not in card_columns:
                connection.execute("ALTER TABLE cards ADD COLUMN fingerprint TEXT NOT NULL DEFAULT ''")
            if "review_state" not in card_columns:
                connection.execute("ALTER TABLE cards ADD COLUMN review_state TEXT NOT NULL DEFAULT 'new'")
            if "reviewed_at" not in card_columns:
                connection.execute("ALTER TABLE cards ADD COLUMN reviewed_at TEXT NOT NULL DEFAULT ''")

            materials = connection.execute("SELECT id, content FROM materials WHERE content_hash = ''").fetchall()
            connection.executemany(
                "UPDATE materials SET content_hash = ? WHERE id = ?",
                [(content_fingerprint(row["content"]), row["id"]) for row in materials],
            )
            cards = connection.execute("SELECT id, title, question FROM cards WHERE fingerprint = ''").fetchall()
            connection.executemany(
                "UPDATE cards SET fingerprint = ? WHERE id = ?",
                [(card_fingerprint(row["question"] or row["title"]), row["id"]) for row in cards],
            )
            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_cards_topic ON cards(topic);
                CREATE INDEX IF NOT EXISTS idx_cards_material ON cards(material_id);
                CREATE INDEX IF NOT EXISTS idx_cards_fingerprint ON cards(fingerprint);
                CREATE INDEX IF NOT EXISTS idx_materials_hash ON materials(content_hash);
                """
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def get_settings(self) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute("SELECT key, value FROM app_settings").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def save_settings(self, values: dict[str, str]) -> None:
        with self.connect() as connection:
            connection.executemany(
                "INSERT INTO app_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                list(values.items()),
            )

    @staticmethod
    def _card(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result.pop("fingerprint", None)
        result["tags"] = json.loads(result["tags"])
        return result

    def create_material(self, title: str, source_type: str, source_uri: str, content: str) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO materials(title, source_type, source_uri, content, content_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (title, source_type, source_uri, content, content_fingerprint(content), utc_now()),
            )
            material_id = cursor.lastrowid
        return self.get_material(material_id)

    def find_material_by_hash(self, content_hash: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM materials WHERE content_hash = ? AND status = 'completed' ORDER BY id DESC LIMIT 1",
                (content_hash,),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_material(self, material_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
        if row is None:
            raise KeyError("材料不存在")
        return dict(row)

    def get_material_with_count(self, material_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT m.*, COUNT(c.id) AS card_count FROM materials m
                   LEFT JOIN cards c ON m.id = c.material_id WHERE m.id = ? GROUP BY m.id""",
                (material_id,),
            ).fetchone()
        if row is None:
            raise KeyError("材料不存在")
        return dict(row)

    def list_materials(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT m.id, m.title, m.source_type, m.source_uri, m.status, m.error, m.created_at,
                   COUNT(c.id) AS card_count FROM materials m LEFT JOIN cards c ON m.id = c.material_id
                   GROUP BY m.id ORDER BY m.id DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def set_material_status(self, material_id: int, status: str, error: str = "") -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE materials SET status = ?, error = ? WHERE id = ?", (status, error, material_id)
            )

    def add_card(self, material_id: int, card: dict[str, Any]) -> int | None:
        now = utc_now()
        fingerprint = card_fingerprint(card.get("question", "") or card["title"])
        with self.connect() as connection:
            if fingerprint:
                existing = connection.execute("SELECT id FROM cards WHERE fingerprint = ? LIMIT 1", (fingerprint,)).fetchone()
                if existing is not None:
                    return None
            cursor = connection.execute(
                """INSERT INTO cards(material_id, fingerprint, topic, kind, title, question, answer, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    material_id,
                    fingerprint,
                    card["topic"],
                    card["kind"],
                    card["title"],
                    card.get("question", ""),
                    card["answer"],
                    json.dumps(card.get("tags", []), ensure_ascii=False),
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def get_card(self, card_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT c.*, m.title AS material_title FROM cards c
                   JOIN materials m ON m.id = c.material_id WHERE c.id = ?""",
                (card_id,),
            ).fetchone()
        if row is None:
            raise KeyError("卡片不存在")
        return self._card(row)

    def cards_for_material(self, material_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT c.*, m.title AS material_title FROM cards c
                   JOIN materials m ON m.id = c.material_id WHERE c.material_id = ? ORDER BY c.id DESC""",
                (material_id,),
            ).fetchall()
        return [self._card(row) for row in rows]

    def list_cards(self, topic: str = "", kind: str = "", query: str = "", state: str = "") -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[str] = []
        if topic:
            clauses.append("c.topic = ?")
            params.append(topic)
        if kind:
            clauses.append("c.kind = ?")
            params.append(kind)
        if state in {"new", "known", "again"}:
            clauses.append("c.review_state = ?")
            params.append(state)
        if query:
            clauses.append("(c.title LIKE ? OR c.question LIKE ? OR c.answer LIKE ? OR c.tags LIKE ?)")
            params.extend([f"%{query}%"] * 4)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT c.*, m.title AS material_title FROM cards c
                    JOIN materials m ON m.id = c.material_id {where} ORDER BY c.id DESC""",
                params,
            ).fetchall()
        return [self._card(row) for row in rows]

    def update_card(self, card_id: int, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {"topic", "kind", "title", "question", "answer", "tags"}
        values = {key: value for key, value in changes.items() if key in allowed and value is not None}
        if "tags" in values:
            values["tags"] = json.dumps(values["tags"], ensure_ascii=False)
        if "title" in values or "question" in values:
            current = self.get_card(card_id)
            fingerprint = card_fingerprint(values.get("question", current["question"]) or values.get("title", current["title"]))
            with self.connect() as connection:
                duplicate = connection.execute(
                    "SELECT id FROM cards WHERE fingerprint = ? AND id <> ? LIMIT 1", (fingerprint, card_id)
                ).fetchone()
            if duplicate is not None:
                raise ValueError("已存在相同问题或标题的卡片")
            values["fingerprint"] = fingerprint
        if values:
            values["updated_at"] = utc_now()
            assignments = ", ".join(f"{key} = ?" for key in values)
            with self.connect() as connection:
                connection.execute(
                    f"UPDATE cards SET {assignments} WHERE id = ?", [*values.values(), card_id]
                )
        return self.get_card(card_id)

    def delete_card(self, card_id: int) -> None:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        if cursor.rowcount == 0:
            raise KeyError("卡片不存在")

    def clear_cards(self, material_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM cards WHERE material_id = ?", (material_id,))

    def delete_material(self, material_id: int) -> None:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM materials WHERE id = ?", (material_id,))
        if cursor.rowcount == 0:
            raise KeyError("材料不存在")

    def backup_cards(self, material_id: int) -> list[tuple]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, material_id, fingerprint, topic, kind, title, question, answer, tags, created_at, updated_at FROM cards WHERE material_id = ?",
                (material_id,),
            ).fetchall()
        return [tuple(row) for row in rows]

    def restore_cards(self, cards: list[tuple]) -> None:
        with self.connect() as connection:
            connection.executemany(
                """INSERT INTO cards(id, material_id, fingerprint, topic, kind, title, question, answer, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                cards,
            )

    def update_material_source(self, material_id: int, source_uri: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE materials SET source_uri = ? WHERE id = ?", (source_uri, material_id)
            )

    def topic_counts(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT topic, COUNT(*) AS count FROM cards GROUP BY topic ORDER BY count DESC, topic"
            ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            cards = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            materials = connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
            topics = connection.execute("SELECT COUNT(DISTINCT topic) FROM cards").fetchone()[0]
            counts = {
                row["review_state"]: row["count"]
                for row in connection.execute(
                    "SELECT review_state, COUNT(*) AS count FROM cards GROUP BY review_state"
                ).fetchall()
            }
        return {
            "cards": cards,
            "materials": materials,
            "topics": topics,
            "reviewed_cards": counts.get("known", 0) + counts.get("again", 0),
            "known_cards": counts.get("known", 0),
            "again_cards": counts.get("again", 0),
        }

    def bulk_update(
        self,
        card_ids: list[int],
        review_state: str | None = None,
        topic: str | None = None,
        kind: str | None = None,
    ) -> int:
        """批量改复习状态、主题或类型。返回实际影响的卡片数。"""
        values: dict[str, Any] = {}
        if review_state is not None:
            values["review_state"] = review_state
            values["reviewed_at"] = "" if review_state == "new" else utc_now()
        if topic is not None:
            if topic not in self.list_topics():
                raise ValueError(f"主题「{topic}」不存在")
            values["topic"] = topic
        if kind is not None:
            if kind not in self.list_kinds():
                raise ValueError(f"类型「{kind}」不存在")
            values["kind"] = kind
        if not values:
            raise ValueError("没有要修改的字段")
        placeholders = ",".join("?" for _ in card_ids)
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE cards SET {assignments} WHERE id IN ({placeholders})",
                [*values.values(), *card_ids],
            )
            return cursor.rowcount

    def bulk_delete(self, card_ids: list[int]) -> int:
        placeholders = ",".join("?" for _ in card_ids)
        with self.connect() as connection:
            cursor = connection.execute(f"DELETE FROM cards WHERE id IN ({placeholders})", card_ids)
            return cursor.rowcount

    def review_queue(self, limit: int = 20) -> dict[str, Any]:
        """今天该复习的卡片。

        优先级：
        1. 标过「再看看」的，越久没复习越靠前；
        2. 从没复习过的，越早建的越靠前。
        已经掌握的不再进入队列。
        """
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT c.*, m.title AS material_title FROM cards c
                   JOIN materials m ON m.id = c.material_id
                   WHERE c.review_state <> 'known'
                   ORDER BY CASE c.review_state WHEN 'again' THEN 0 ELSE 1 END,
                            CASE WHEN c.reviewed_at = '' THEN '9999' ELSE c.reviewed_at END,
                            c.id
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            total = connection.execute(
                "SELECT COUNT(*) FROM cards WHERE review_state <> 'known'"
            ).fetchone()[0]
            again = connection.execute(
                "SELECT COUNT(*) FROM cards WHERE review_state = 'again'"
            ).fetchone()[0]
        return {
            "cards": [self._card(row) for row in rows],
            "total": total,
            "again": again,
            "limit": limit,
        }

    def set_review_state(self, card_id: int, state: str) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE cards SET review_state = ?, reviewed_at = ? WHERE id = ?",
                (state, utc_now() if state != "new" else "", card_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"卡片 {card_id} 不存在")
        return self.get_card(card_id)

    def list_topics(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute("SELECT name FROM topics ORDER BY rowid").fetchall()
        return [row["name"] for row in rows]

    def add_topic(self, name: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("INSERT OR IGNORE INTO topics(name, created_at) VALUES (?, ?)", (name, utc_now()))
        return cursor.rowcount > 0

    def delete_topic(self, name: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM topics WHERE name = ?", (name,))
        return cursor.rowcount > 0

    def list_kinds(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute("SELECT name FROM card_kinds ORDER BY rowid").fetchall()
        return [row["name"] for row in rows]

    def add_kind(self, name: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("INSERT OR IGNORE INTO card_kinds(name, created_at) VALUES (?, ?)", (name, utc_now()))
        return cursor.rowcount > 0

    def delete_kind(self, name: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM card_kinds WHERE name = ?", (name,))
        return cursor.rowcount > 0
