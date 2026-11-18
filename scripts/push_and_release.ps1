# 一键推送并触发自动打包
# 双击桌面上的「发布拾记.bat」即可运行
# 需要登录 GitHub 时，会弹出登录窗口，登录一次以后就记住

param(
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"
$repo = "D:\Program Files\openclaw\DSHopenclaw\tmp\recall-card"
$tag = "v0.1.0"

Set-Location $repo

Write-Host ""
Write-Host "=== 拾记 Recall Card 发布 ===" -ForegroundColor Cyan
Write-Host ""

# 0. 先确认没有未提交的改动
$dirty = git status --porcelain
if ($dirty) {
    Write-Host "还有没提交的改动：" -ForegroundColor Yellow
    Write-Host $dirty
    Write-Host ""
    $answer = Read-Host "要先帮你提交吗？(Y/n)"
    if ($answer -ne "n") {
        git add -A
        git commit -m "chore: 发布前提交"
        Write-Host "已提交" -ForegroundColor Green
    }
}

if ($NoPush) {
    Write-Host "[演练模式] 会执行：git push origin main / git tag $tag / git push origin $tag" -ForegroundColor Yellow
    exit 0
}

# 1. 推送代码
Write-Host "[1/3] 推送代码到 GitHub ..." -ForegroundColor Cyan
Write-Host "      如果弹出登录窗口，正常登录即可" -ForegroundColor DarkGray
git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "推送失败。常见原因：" -ForegroundColor Red
    Write-Host "  1. 登录窗口被取消或账号密码错误"
    Write-Host "  2. GitHub 密码不能直接用，要输入 Personal Access Token"
    Write-Host "  3. 网络不通"
    exit 1
}
Write-Host "      代码已推送" -ForegroundColor Green

# 2. 打标签（本地已有就不重复打）
Write-Host "[2/3] 准备标签 $tag ..." -ForegroundColor Cyan
$localTag = git tag -l $tag
if ($localTag) {
    Write-Host "      本地已有 $tag，跳过" -ForegroundColor DarkGray
} else {
    git tag $tag
    Write-Host "      已创建标签" -ForegroundColor Green
}

# 3. 推送标签，触发自动打包
Write-Host "[3/3] 推送标签，触发 GitHub 自动打包 ..." -ForegroundColor Cyan
$remoteTag = git ls-remote --tags origin $tag
if ($remoteTag) {
    Write-Host "      远端已有 $tag，不重复触发" -ForegroundColor DarkGray
    Write-Host "      想重新发一版，可以改用 v0.1.1" -ForegroundColor DarkGray
} else {
    git push origin $tag
    if ($LASTEXITCODE -ne 0) {
        Write-Host "标签推送失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "      标签已推送" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== 全部完成 ===" -ForegroundColor Green
Write-Host ""
Write-Host "GitHub 现在正在自动构建 exe，大概要 5 到 10 分钟。"
Write-Host "进度看这里：https://github.com/Griffin-xcy/recall-card/actions"
Write-Host "构建完成后 exe 会出现在这里：https://github.com/Griffin-xcy/recall-card/releases"
Write-Host ""
