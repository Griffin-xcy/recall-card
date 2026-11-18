import os
import sys
import tempfile
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent

# 打包成 exe 后，代码和静态文件会被解压到临时目录（_MEIPASS），
# 所以路径不能直接写 Path(__file__).parent.parent。
FROZEN = bool(getattr(sys, "frozen", False))
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", ROOT_DIR))


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _default_data_dir() -> Path:
    """数据目录：源码运行放仓库下；打包运行优先用户目录，不可写就逐级退让。

    退让顺序：%LOCALAPPDATA%\\RecallCard\\data → exe 同目录 data → 系统临时目录。
    这样在没权限写用户目录的电脑（公司电脑、受限账户）上也能跑起来。
    """
    if not FROZEN:
        return ROOT_DIR / "data"

    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    candidates = [
        Path(base) / "RecallCard" / "data",
        Path(sys.executable).parent / "data",
        Path(tempfile.gettempdir()) / "RecallCard" / "data",
    ]
    for candidate in candidates:
        if _writable(candidate):
            return candidate
    return candidates[-1]


def _env_file() -> Path | None:
    """源码运行读仓库根目录的 .env，打包运行读 exe 旁边的 .env。"""
    candidate = Path(sys.executable).parent / ".env" if FROZEN else ROOT_DIR / ".env"
    return candidate if candidate.exists() else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file(), extra="ignore")

    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-flash"
    llm_provider: str = "openai"
    data_dir: Path = _default_data_dir()
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
