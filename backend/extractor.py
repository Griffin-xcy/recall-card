import io
import ipaddress
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader


class ExtractionError(ValueError):
    pass


def clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ExtractionError(f"PDF 解析失败：{exc}") from exc
    text = clean_text("\n\n".join(pages))
    if len(text) < 20:
        raise ExtractionError("PDF 中没有足够的可复制文本；扫描件请先进行 OCR")
    return text


def extract_text(content: bytes) -> str:
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = clean_text(content.decode("utf-16"))
        if len(text) >= 20:
            return text
        raise ExtractionError("文本内容太少，至少需要 20 个字符")
    sample = content[:8192]
    controls = sum(byte < 32 and byte not in {9, 10, 12, 13} for byte in sample)
    if b"\x00" in sample or (sample and controls / len(sample) > 0.1):
        raise ExtractionError("该文件不是可读取的文本或代码文件；图片、音视频、压缩包和 Office 文档需要专用解析器")
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = clean_text(content.decode(encoding))
            if len(text) >= 20:
                return text
            raise ExtractionError("文本内容太少，至少需要 20 个字符")
        except UnicodeDecodeError:
            continue
    raise ExtractionError("无法识别文本编码，请转换为 UTF-8 编码后重试")


def _is_private_host(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast


async def extract_webpage(url: str, timeout: int = 30) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ExtractionError("仅支持 HTTP 或 HTTPS 网页")
    if _is_private_host(parsed.hostname or ""):
        raise ExtractionError("出于安全考虑，不支持访问本地或内网地址")
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url, headers={"User-Agent": "RecallCard/0.1"})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ExtractionError(f"网页读取失败：{exc}") from exc
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and content_type:
        raise ExtractionError("链接不是可解析的 HTML 网页")
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
        element.decompose()
    article = soup.find("article") or soup.find("main") or soup.body or soup
    text = clean_text(article.get_text("\n", strip=True))
    if len(text) < 20:
        raise ExtractionError("网页中没有足够的正文内容")
    title = clean_text(soup.title.get_text() if soup.title else "") or parsed.netloc
    return title, text
