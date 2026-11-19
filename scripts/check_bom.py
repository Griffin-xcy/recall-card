"""检查仓库里的文本文件没有 UTF-8 BOM。

Windows 上的编辑器、PowerShell 的 Set-Content 都可能顺手加个 BOM。
Vite 解析带 BOM 的 package.json 会直接报 "Unexpected token '﻿'"，
而且这种问题在 Linux 上根本复现不了。放进 CI 两边都跑一遍。
"""

import sys
from pathlib import Path

ROOT_FILES = [
    "package.json",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
    "vite.config.ts",
    "README.md",
    "README.en.md",
    "CHANGELOG.md",
    "docker-compose.yml",
]
SCAN_DIRS = [".github", "backend", "scripts", "src", "tests"]
SUFFIXES = {".json", ".md", ".yml", ".yaml", ".py", ".ts", ".tsx", ".css", ".html", ".txt"}
SKIP_DIRS = {"node_modules", ".venv", "dist", "release", "build", ".git"}
BOM = b"\xef\xbb\xbf"


def candidates():
    for name in ROOT_FILES:
        path = Path(name)
        if path.exists():
            yield path
    for name in SCAN_DIRS:
        base = Path(name)
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in SUFFIXES and not (set(path.parts) & SKIP_DIRS):
                yield path


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    bad = sorted({str(path) for path in candidates() if path.read_bytes()[:3] == BOM})
    if bad:
        print("发现带 UTF-8 BOM 的文件：")
        for path in bad:
            print("  " + path)
        return 1
    print("BOM 检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
