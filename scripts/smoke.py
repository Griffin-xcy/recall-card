"""Cold-start the production FastAPI server and verify its real HTTP responses."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urljoin
from urllib.request import urlopen
import re

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT.parent / "data-smoke"
shutil.rmtree(DATA, ignore_errors=True)
env = {**os.environ, "LLM_PROVIDER": "mock", "DATA_DIR": str(DATA), "API_KEY": ""}
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=ROOT,
    env=env,
)
base = "http://127.0.0.1:8000"
try:
    for _ in range(100):
        try:
            with urlopen(f"{base}/api/health", timeout=1) as response:
                health = json.load(response)
            if health["status"] == "ok":
                break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("生产服务器未在 10 秒内就绪")

    with urlopen(f"{base}/", timeout=3) as response:
        html = response.read().decode("utf-8")
    assert "拾记 Recall Card" in html
    asset = re.search(r'<script[^>]+src="([^"]+)"', html)
    assert asset, "生产 HTML 缺少脚本资源"
    with urlopen(urljoin(base, asset.group(1)), timeout=3) as response:
        assert response.status == 200 and len(response.read()) > 10_000
    with urlopen(f"{base}/favicon.svg", timeout=3) as response:
        assert response.status == 200 and b"<svg" in response.read()
    print(json.dumps({"result": "passed", "mode": "production", "health": health["status"], "asset": asset.group(1)}, ensure_ascii=False))
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)
    shutil.rmtree(DATA, ignore_errors=True)
