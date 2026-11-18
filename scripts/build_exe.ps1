# 一键打包 Windows 单文件 exe
# 用法：在仓库根目录执行  pwsh -File scripts/build_exe.ps1
# 产物：release\RecallCard.exe

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[1/5] 安装前端依赖" -ForegroundColor Cyan
& npm.cmd ci

Write-Host "[2/5] 构建前端" -ForegroundColor Cyan
& npm.cmd run build

Write-Host "[3/5] 准备 Python 环境" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt pyinstaller

Write-Host "[4/5] 生成图标" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe scripts\make_icon.py

Write-Host "[5/5] 打包 exe" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m PyInstaller recall-card.spec --noconfirm --distpath release --workpath build\pyinstaller

$exe = Join-Path $root "release\RecallCard.exe"
if (Test-Path $exe) {
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "完成：$exe（$size MB）" -ForegroundColor Green
} else {
    throw "打包失败：没有找到 $exe"
}
