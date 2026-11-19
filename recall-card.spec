# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：把后端、前端静态文件和 Python 运行时打成单个 exe。

打包命令（不要直接用 pyinstaller recall-card.spec，会用到默认的 dist 目录）：
    .venv\\Scripts\\python -m PyInstaller recall-card.spec --noconfirm --distpath release --workpath build/pyinstaller
"""

from PyInstaller.utils.hooks import collect_submodules

# uvicorn 的 loop / protocol 实现是运行时按名字动态导入的，必须显式收集
hiddenimports = collect_submodules("uvicorn")

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=[("dist", "dist")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "_pytest", "reportlab", "playwright", "PyInstaller"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="RecallCard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="build/icon.ico",
    version="scripts/version_info.txt",
)
