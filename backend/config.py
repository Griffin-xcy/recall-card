from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-flash"
    llm_provider: str = "openai"
    data_dir: Path = ROOT_DIR / "data"
    max_upload_mb: int = 15
    request_timeout_seconds: int = 120

    @property
    def database_path(self) -> Path:
        return self.data_dir / "recall-card.db"

    @property
    def model_configured(self) -> bool:
        return self.llm_provider == "mock" or bool(self.api_key)


TOPICS = ["学习笔记", "技术知识", "求职准备", "工作会议", "研究资料", "其他"]
CARD_KINDS = ["知识点", "问答", "行动项", "决策"]
