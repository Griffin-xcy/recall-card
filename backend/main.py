import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .config import BUNDLE_DIR, FROZEN, Settings
from .db import Database, content_fingerprint
from .demo import seed_demo
from .export import build_markdown_zip
from .extractor import ExtractionError, extract_pdf, extract_text, extract_webpage
from .pipeline import process_material
from .schemas import (
    BulkIdsInput,
    BulkUpdateInput,
    CardUpdate,
    KindInput,
    ModelSettingsInput,
    ReviewInput,
    TextMaterialInput,
    TopicInput,
    UrlMaterialInput,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("recall-card")


def _should_seed_demo() -> bool:
    """打包版首次启动自动填示例卡片；源码运行和测试默认不填。

    想手动验证可以设置 RECALL_CARD_SEED_DEMO=1。
    """
    forced = os.environ.get("RECALL_CARD_SEED_DEMO")
    if forced is not None:
        return forced.strip().lower() not in ("", "0", "false", "no")
    return FROZEN


def create_app() -> FastAPI:
    settings = Settings()
    db = Database(settings.database_path)
    for key, value in db.get_settings().items():
        if key in {"base_url", "api_key", "model", "llm_provider"} and value:
            setattr(settings, key, value)
    if _should_seed_demo():
        try:
            if seed_demo(db):
                logger.info("首次启动，已写入示例卡片")
        except Exception:  # 示例卡片失败不能影响正常启动
            logger.exception("写入示例卡片失败")
    application = FastAPI(title="拾记 Recall Card", version="0.6.0")

    async def regenerate_safely(material_id: int) -> list[dict]:
        """重新生成卡片；失败时回滚到原卡片，避免数据丢失。"""
        material = db.get_material(material_id)
        backup = db.backup_cards(material_id)
        db.clear_cards(material_id)
        try:
            return await process_material(db, settings, material_id)
        except Exception as exc:
            db.restore_cards(backup)
            db.set_material_status(material_id, material["status"], material["error"])
            raise exc

    def _schedule(material_id: int, regen: bool = False) -> None:
        async def run() -> None:
            try:
                if regen:
                    await regenerate_safely(material_id)
                else:
                    await process_material(db, settings, material_id)
            except Exception:
                pass

        asyncio.create_task(run())

    @application.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "version": "0.6.0",
            "model_configured": settings.model_configured,
            "has_api_key": bool(settings.api_key),
            "provider": settings.llm_provider,
            "model": settings.model if settings.llm_provider != "mock" else "local-demo",
            "base_url": settings.base_url,
        }

    @application.put("/api/settings")
    def save_model_settings(payload: ModelSettingsInput) -> dict:
        base_url = payload.base_url.strip().rstrip("/")
        if not base_url.startswith(("https://", "http://")):
            raise HTTPException(422, "接口地址必须以 https:// 或 http:// 开头")
        values = {"base_url": base_url, "model": payload.model.strip(), "llm_provider": "openai"}
        if payload.api_key.strip():
            values["api_key"] = payload.api_key.strip()
        for key, value in values.items():
            setattr(settings, key, value)
        settings.llm_provider = "openai"
        db.save_settings(values)
        return health()

    @application.get("/api/stats")
    def stats() -> dict:
        return db.stats()

    @application.get("/api/topics")
    def topics() -> list[dict]:
        return db.topic_counts()

    @application.get("/api/config")
    def config() -> dict:
        return {"topics": db.list_topics(), "kinds": db.list_kinds()}

    @application.post("/api/config/topics", status_code=201)
    def add_topic(payload: TopicInput) -> dict:
        name = payload.name.strip()
        if db.add_topic(name):
            return {"topics": db.list_topics()}
        raise HTTPException(409, "该主题已存在")

    @application.delete("/api/config/topics/{name}", status_code=204)
    def remove_topic(name: str) -> Response:
        if db.delete_topic(name):
            return Response(status_code=204)
        raise HTTPException(404, "主题不存在")

    @application.post("/api/config/kinds", status_code=201)
    def add_kind(payload: KindInput) -> dict:
        name = payload.name.strip()
        if db.add_kind(name):
            return {"kinds": db.list_kinds()}
        raise HTTPException(409, "该类型已存在")

    @application.delete("/api/config/kinds/{name}", status_code=204)
    def remove_kind(name: str) -> Response:
        if db.delete_kind(name):
            return Response(status_code=204)
        raise HTTPException(404, "类型不存在")

    @application.get("/api/materials")
    def materials() -> list[dict]:
        return db.list_materials()

    @application.get("/api/cards")
    def cards(topic: str = "", kind: str = "", q: str = "", state: str = "") -> list[dict]:
        return db.list_cards(topic=topic, kind=kind, query=q.strip(), state=state)

    @application.post("/api/materials/file", status_code=201)
    async def upload_material(response: Response, file: UploadFile = File(...), source_path: str = Form(default=""), force: bool = Form(default=False)) -> dict:
        filename = file.filename or "未命名材料"
        extension = Path(filename).suffix.lower()
        content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
        if len(content) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"文件超过 {settings.max_upload_mb} MB 限制")
        try:
            text = extract_pdf(content) if extension == ".pdf" else extract_text(content)
        except ExtractionError as exc:
            raise HTTPException(422, str(exc)) from exc
        content_hash = content_fingerprint(text)
        source_uri = source_path.strip()[:1000] or filename
        if force:
            existing = db.find_material_by_hash(content_hash)
            if existing is not None:
                db.update_material_source(existing["id"], source_uri)
                _schedule(existing["id"], regen=True)
                return {"material": db.get_material(existing["id"]), "cards": [], "duplicate": False}
        elif (duplicate := db.find_material_by_hash(content_hash)) is not None:
            response.status_code = 200
            return {"material": duplicate, "cards": [], "duplicate": True}
        material = db.create_material(Path(filename).stem, "file", source_uri, text)
        _schedule(material["id"])
        return {"material": db.get_material(material["id"]), "cards": [], "duplicate": False}

    @application.post("/api/materials/text", status_code=201)
    async def create_text_material(payload: TextMaterialInput) -> dict:
        material = db.create_material(payload.title.strip(), "text", "", payload.content.strip())
        _schedule(material["id"])
        return {"material": db.get_material(material["id"]), "cards": []}

    @application.post("/api/materials/url", status_code=201)
    async def create_url_material(payload: UrlMaterialInput) -> dict:
        url = str(payload.url)
        try:
            title, text = await extract_webpage(url)
        except ExtractionError as exc:
            raise HTTPException(422, str(exc)) from exc
        material = db.create_material(title, "url", url, text)
        _schedule(material["id"])
        return {"material": db.get_material(material["id"]), "cards": []}

    @application.get("/api/cards/{card_id}")
    def get_card(card_id: int) -> dict:
        try:
            return db.get_card(card_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    @application.patch("/api/cards/{card_id}")
    def update_card(card_id: int, payload: CardUpdate) -> dict:
        try:
            return db.update_card(card_id, payload.model_dump(exclude_unset=True))
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @application.delete("/api/cards/{card_id}", status_code=204)
    def delete_card(card_id: int) -> Response:
        try:
            db.delete_card(card_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        return Response(status_code=204)

    @application.post("/api/cards/{card_id}/review")
    def review_card(card_id: int, payload: ReviewInput) -> dict:
        try:
            return db.set_review_state(card_id, payload.state)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    @application.get("/api/review/queue")
    def review_queue(limit: int = Query(default=20, ge=1, le=100)) -> dict:
        return db.review_queue(limit)

    @application.post("/api/cards/bulk-update")
    def bulk_update_cards(payload: BulkUpdateInput) -> dict:
        try:
            updated = db.bulk_update(payload.ids, payload.review_state, payload.topic, payload.kind)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"updated": updated}

    @application.post("/api/cards/bulk-delete")
    def bulk_delete_cards(payload: BulkIdsInput) -> dict:
        return {"deleted": db.bulk_delete(payload.ids)}

    @application.get("/api/materials/{material_id}")
    def get_material(material_id: int) -> dict:
        try:
            return db.get_material_with_count(material_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    @application.delete("/api/materials/{material_id}", status_code=204)
    def remove_material(material_id: int) -> Response:
        try:
            db.delete_material(material_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        return Response(status_code=204)

    @application.post("/api/materials/{material_id}/regenerate")
    async def regenerate_material(material_id: int) -> dict:
        try:
            db.get_material(material_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        _schedule(material_id, regen=True)
        return {"material": db.get_material(material_id), "cards": []}

    @application.get("/api/export/markdown")
    def export_markdown(topic: str = Query(default="")) -> Response:
        selected = db.list_cards(topic=topic)
        if not selected:
            raise HTTPException(404, "当前筛选范围没有可导出的卡片")
        archive = build_markdown_zip(selected)
        filename = "recall-cards.zip"
        return Response(
            content=archive,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    dist_dir = BUNDLE_DIR / "dist"
    if dist_dir.exists():
        application.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")
    return application


app = create_app()
