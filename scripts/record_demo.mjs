import { chromium } from '@playwright/test'
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, rmSync } from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const framesDir = path.join(root, '..', 'demo-frames')
rmSync(framesDir, { recursive: true, force: true })
mkdirSync(framesDir, { recursive: true })

const dataDir = path.join(root, '..', 'data-demo')
rmSync(dataDir, { recursive: true, force: true })

const server = spawn(process.execPath, ['scripts/dev.mjs', '--host', '127.0.0.1', '--port', '7100'], {
  cwd: root,
  env: { ...process.env, LLM_PROVIDER: 'mock', DATA_DIR: '../data-demo', API_KEY: '' },
  stdio: 'ignore',
})

async function waitForServer() {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch('http://127.0.0.1:7100/api/health')
      if (response.ok) return
    } catch {
      // 开发服务仍在启动。
    }
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  throw new Error('开发服务器未在 20 秒内就绪')
}

function stopServer() {
  if (!server.pid || server.killed) return
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(server.pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    server.kill('SIGTERM')
  }
}

let browser

try {
  await waitForServer()
  const edge = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
  browser = await chromium.launch(existsSync(edge) ? { executablePath: edge, headless: true } : { headless: true })
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })

  let index = 0
  const shot = async (name) => {
    index += 1
    await page.screenshot({ path: path.join(framesDir, `${String(index).padStart(2, '0')}-${name}.png`) })
  }

  await page.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  await page.waitForTimeout(400)
  await shot('empty')

  await page.getByRole('button', { name: '使用示例文本' }).click()
  await page.waitForTimeout(400)
  await shot('import')

  await page.getByRole('button', { name: '开始生成' }).click()
  await page.locator('.study-card').first().waitFor({ timeout: 15000 })
  await page.waitForTimeout(400)
  await shot('cards')

  await page.getByRole('button', { name: '问答', exact: true }).click()
  await page.waitForTimeout(400)
  await shot('filter')

  await page.getByRole('button', { name: '全部类型' }).click()
  await page.waitForTimeout(400)
  await shot('all')

  console.log(JSON.stringify({ result: 'ok', frames: index, framesDir }))
} finally {
  if (browser) await browser.close()
  stopServer()
  const python = existsSync(path.join(root, '.venv', 'Scripts', 'python.exe'))
    ? path.join(root, '.venv', 'Scripts', 'python.exe')
    : existsSync(path.join(root, '.venv', 'bin', 'python'))
      ? path.join(root, '.venv', 'bin', 'python')
      : 'python'
  spawnSync(python, ['scripts/make_gif.py'], { cwd: root, stdio: 'inherit' })
  rmSync(framesDir, { recursive: true, force: true })
  rmSync(dataDir, { recursive: true, force: true })
}
