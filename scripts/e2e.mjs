import { chromium, expect } from '@playwright/test'
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const artifacts = path.join(root, '..', 'verification')
const dataDir = path.join(root, '..', 'data-e2e')
rmSync(dataDir, { recursive: true, force: true })
mkdirSync(artifacts, { recursive: true })
const fixtureRoot = path.join(dataDir, 'folder-fixtures', '课程资料')
mkdirSync(path.join(fixtureRoot, '第一章'), { recursive: true })
mkdirSync(path.join(fixtureRoot, '第二章', '深入'), { recursive: true })
const sampleFor = (label) => `${label}：主动回忆要求学习者在不查看答案时提取信息。间隔重复通过逐步增加复习间隔巩固记忆。这些方法比反复阅读更容易发现知识盲点。`
writeFileSync(path.join(fixtureRoot, '第一章', 'readme.py'), sampleFor('第一章'))
writeFileSync(path.join(fixtureRoot, '第二章', '深入', 'retry.md'), sampleFor('重试材料'))
writeFileSync(path.join(fixtureRoot, '第二章', '深入', 'notes.txt'), sampleFor('第二章'))
const server = spawn(process.execPath, ['scripts/dev.mjs', '--host', '127.0.0.1', '--port', '7100'], {
  cwd: root,
  env: { ...process.env, LLM_PROVIDER: 'mock', DATA_DIR: '../data-e2e', API_KEY: '' },
  stdio: 'inherit',
})
let browser

async function waitForServer() {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch('http://127.0.0.1:7100/api/health')
      if (response.ok) return
    } catch {
      // The development processes are still starting.
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

try {
  await waitForServer()
  const edge = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
  browser = await chromium.launch(existsSync(edge) ? { executablePath: edge, headless: true } : { headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true })
  const page = await context.newPage()
  const consoleErrors = []
  const notFound = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text() + ' @ ' + message.location().url) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  page.on('response', (response) => { if (response.status() === 404) notFound.push(response.url()) })

  await page.route('**/api/health', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ status: 'ok', version: '0.1.0', model_configured: false, has_api_key: false, provider: 'openai', model: 'deepseek-flash', base_url: 'https://api.deepseek.com/v1' }),
  }))
  await page.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: '全部卡片', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '先连接你的模型' })).toBeVisible()
  await expect(page.locator('.settings-button')).toHaveText('连接模型')
  await expect(page.locator('.setup-banner')).toContainText('第 1 步：连接模型')
  await page.screenshot({ path: path.join(artifacts, 'desktop-connect.png'), fullPage: true })

  await page.locator('.sidebar-import').click()
  await expect(page.getByRole('button', { name: '请先连接模型' })).toBeDisabled()
  await page.locator('.config-action').click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByLabel('服务商', { exact: true }).locator('option')).toHaveCount(7)
  await page.getByLabel('服务商', { exact: true }).selectOption('kimi')
  await expect(page.getByLabel('接口地址')).toHaveValue('https://api.moonshot.cn/v1')
  await expect(page.getByLabel('模型名称')).toHaveValue('kimi-k3.1-pro')
  await page.getByLabel('服务商', { exact: true }).selectOption('openai')
  await expect(page.getByLabel('模型名称')).toHaveValue('gpt-5.4')
  await page.getByLabel('服务商', { exact: true }).selectOption('qwen')
  await expect(page.getByLabel('接口地址')).toHaveValue('https://WorkspaceId.cn-beijing.maas.aliyuncs.com/compatible-mode/v1')
  await expect(page.getByText(/通义千问：请将接口地址/)).toBeVisible()
  await page.getByLabel('API Key', { exact: true }).fill('e2e-local-only-key')
  await page.getByRole('button', { name: '保存并使用' }).click()
  await expect(page.getByRole('alert')).toContainText('WorkspaceId')
  await page.getByLabel('服务商', { exact: true }).selectOption('zhipu')
  await expect(page.getByLabel('模型名称')).toHaveValue('glm-5.3')
  await page.getByLabel('服务商', { exact: true }).selectOption('ollama')
  await expect(page.getByLabel('接口地址')).toHaveValue('http://localhost:11434/v1')
  await expect(page.getByLabel('API Key', { exact: true })).toHaveValue('ollama')
  await expect(page.getByText(/本地模型：请先启动 Ollama/)).toBeVisible()
  await page.getByLabel('服务商', { exact: true }).selectOption('deepseek')
  await expect(page.getByLabel('API Key', { exact: true })).toHaveValue('')
  await expect(page.getByLabel('模型名称')).toHaveValue('deepseek-flash')
  await page.getByLabel('API Key', { exact: true }).fill('e2e-local-only-key')
  await page.getByRole('button', { name: '显示 API Key' }).click()
  await expect(page.getByLabel('API Key', { exact: true })).toHaveAttribute('type', 'text')
  await page.getByLabel('API Key', { exact: true }).focus()
  await expect(page.getByLabel('API Key', { exact: true })).toHaveCSS('outline-style', 'none')
  await expect(page.locator('.secret-input')).toHaveCSS('box-shadow', 'none')
  await page.getByLabel('接口地址').focus()
  await expect(page.getByLabel('接口地址')).toHaveCSS('box-shadow', 'none')
  await page.getByLabel('API Key', { exact: true }).focus()
  await page.waitForTimeout(250)
  await page.screenshot({ path: path.join(artifacts, 'desktop-settings.png'), fullPage: true })
  await page.keyboard.press('Escape')
  await page.unroute('**/api/health')
  await page.reload({ waitUntil: 'networkidle' })

  await expect(page.getByText('从第一份材料开始')).toBeVisible()
  await page.screenshot({ path: path.join(artifacts, 'desktop-empty.png'), fullPage: true })
  await page.getByRole('button', { name: '使用示例文本' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: '开始生成' }).click()
  await expect(page.getByText(/已生成 \d+ 张卡片/)).toBeVisible({ timeout: 15000 })
  await expect(page.locator('.study-card')).toHaveCount(3)
  await page.screenshot({ path: path.join(artifacts, 'desktop-cards.png'), fullPage: true })

  await page.locator('.study-card').first().getByRole('button', { name: /^编辑/ }).click()
  await page.getByLabel('标题', { exact: true }).fill('间隔重复（已编辑）')
  await page.getByRole('button', { name: '保存修改' }).click()
  await expect(page.getByRole('heading', { name: '间隔重复（已编辑）' })).toBeVisible()

  await page.getByLabel('搜索卡片').fill('绝对没有这条内容')
  await expect(page.getByText('没有找到匹配的卡片')).toBeVisible()
  await page.getByRole('button', { name: '清除筛选' }).click()
  await expect(page.locator('.study-card')).toHaveCount(3)
  await page.getByRole('button', { name: '问答', exact: true }).click()
  await expect(page.locator('.study-card')).toHaveCount(1)
  await page.getByRole('button', { name: '全部类型' }).click()
  await expect(page.locator('.study-card')).toHaveCount(3)

  const downloadEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出 Markdown' }).click()
  const download = await downloadEvent
  expect(download.suggestedFilename()).toMatch(/\.zip$/)
  await download.saveAs(path.join(artifacts, 'export.zip'))

  await page.locator('.study-card').first().getByRole('button', { name: /^删除/ }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: '确认删除' }).click()
  await expect(page.locator('.study-card')).toHaveCount(2)

  await page.route('**/api/materials/file', async (route) => {
    const body = route.request().postDataBuffer()?.toString('utf8') || ''
    if (body.includes('retry.md')) {
      await route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ detail: '模拟单文件失败' }) })
    } else {
      await route.continue()
    }
  })
  await page.locator('.sidebar-import').click()
  await page.getByRole('tab', { name: '选择文件夹' }).click()
  await page.getByLabel('选择材料文件夹').setInputFiles(fixtureRoot)
  await expect(page.locator('.batch-item')).toHaveCount(3)
  await page.getByRole('button', { name: '开始批量生成' }).click()
  await expect(page.locator('.batch-completed')).toHaveCount(2, { timeout: 15000 })
  await expect(page.locator('.batch-failed')).toHaveCount(1)
  await expect(page.getByRole('progressbar', { name: '文件夹导入进度' })).toHaveAttribute('aria-valuenow', '100')
  await expect(page.getByRole('button', { name: '重试失败文件（1）' })).toBeVisible()
  await page.waitForTimeout(250)
  await page.screenshot({ path: path.join(artifacts, 'desktop-folder-retry.png'), fullPage: true })
  await page.unroute('**/api/materials/file')
  await page.getByRole('button', { name: '重试失败文件（1）' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0, { timeout: 15000 })
  await expect(page.locator('.study-card')).toHaveCount(6)
  const materialPaths = await page.evaluate(async () => {
    const response = await fetch('/api/materials')
    return (await response.json()).map((material) => material.source_uri)
  })
  expect(materialPaths.some((source) => source.endsWith('第一章/readme.py'))).toBe(true)
  expect(materialPaths.some((source) => source.endsWith('第二章/深入/retry.md'))).toBe(true)

  await page.getByRole('button', { name: /导入记录/ }).click()
  await expect(page.locator('.material-row')).toHaveCount(4)
  await expect(page.locator('.material-status').first()).toContainText('1 张卡片')

  // 重复导入：再次选择同一文件夹，全部文件应被识别为重复跳过
  await page.locator('.sidebar-import').click()
  await page.getByRole('tab', { name: '选择文件夹' }).click()
  await page.getByLabel('选择材料文件夹').setInputFiles(fixtureRoot)
  await expect(page.locator('.batch-item')).toHaveCount(3)
  await page.getByRole('button', { name: '开始批量生成' }).click()
  await expect(page.locator('.batch-duplicate')).toHaveCount(3, { timeout: 15000 })
  await expect(page.getByText(/重复已跳过/)).toBeVisible()
  await expect(page.getByRole('progressbar', { name: '文件夹导入进度' })).toHaveAttribute('aria-valuenow', '100')
  await page.screenshot({ path: path.join(artifacts, 'desktop-dedup.png'), fullPage: true })
  await page.locator('.batch-duplicate').first().getByRole('button', { name: '重新生成' }).click()
  await expect(page.locator('.batch-duplicate')).toHaveCount(2, { timeout: 15000 })
  await page.locator('.batch-duplicate').first().getByRole('button', { name: '跳过' }).click()
  await expect(page.locator('.batch-item')).toHaveCount(2)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await page.locator('.settings-button').click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.locator('.settings-button')).toHaveText('模型设置')
  await expect(page.getByLabel('服务商', { exact: true })).toHaveValue('deepseek')
  await page.getByLabel('API Key', { exact: true }).fill('e2e-local-only-key')
  await page.getByRole('button', { name: '保存并使用' }).click()
  await expect(page.getByText('模型设置已保存，可以开始生成')).toBeVisible()
  const savedHealth = await page.evaluate(async () => {
    const response = await fetch('/api/health')
    return response.json()
  })
  expect(savedHealth.provider).toBe('openai')
  expect(savedHealth.has_api_key).toBe(true)
  expect(savedHealth.model).toBe('deepseek-flash')
  expect(JSON.stringify(savedHealth)).not.toContain('e2e-local-only-key')
  await page.locator('.settings-button').click()
  await expect(page.getByLabel('API Key', { exact: true })).toHaveAttribute('placeholder', '留空则保留已保存的 Key')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)

  const mobile = await browser.newContext({ viewport: { width: 375, height: 812 } })
  const mobilePage = await mobile.newPage()
  mobilePage.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(`mobile: ${message.text() + ' @ ' + message.location().url}`) })
  mobilePage.on('pageerror', (error) => consoleErrors.push(`mobile: ${error.message}`))
  mobilePage.on('response', (response) => { if (response.status() === 404) notFound.push(response.url()) })
  await mobilePage.goto('http://127.0.0.1:7100', { waitUntil: 'networkidle' })
  await expect(mobilePage.locator('.study-card')).toHaveCount(6)
  const dimensions = await mobilePage.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: window.innerWidth }))
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.viewport)
  await mobilePage.screenshot({ path: path.join(artifacts, 'mobile-cards.png'), fullPage: true })
  await mobilePage.locator('.settings-button').click()
  await expect(mobilePage.getByLabel('服务商', { exact: true })).toBeVisible()
  await mobilePage.waitForTimeout(250)
  await mobilePage.screenshot({ path: path.join(artifacts, 'mobile-settings.png'), fullPage: true })
  await mobilePage.keyboard.press('Escape')
  await mobilePage.getByRole('button', { name: '导入材料', exact: true }).click()
  await expect(mobilePage.getByRole('dialog')).toBeVisible()
  await mobilePage.getByRole('tab', { name: '选择文件夹' }).click()
  await mobilePage.getByLabel('选择材料文件夹').setInputFiles(fixtureRoot)
  await expect(mobilePage.locator('.batch-item')).toHaveCount(3)
  await mobilePage.waitForTimeout(250)
  await mobilePage.screenshot({ path: path.join(artifacts, 'mobile-folder.png'), fullPage: true })
  await mobilePage.keyboard.press('Escape')
  await expect(mobilePage.getByRole('dialog')).toHaveCount(0)

  expect(notFound).toEqual([])
  const unexpectedConsoleErrors = consoleErrors.filter((message) => !message.includes('status of 422') || !message.includes('/api/materials/file'))
  expect(unexpectedConsoleErrors).toEqual([])
  console.log(JSON.stringify({ result: 'passed', cardsTested: 3, folderFilesTested: 3, failureRetry: true, dedupVerified: true, providersTested: ['deepseek', 'kimi', 'openai', 'qwen', 'zhipu', 'ollama'], expectedFaultResponses: consoleErrors.length - unexpectedConsoleErrors.length, consoleErrors: unexpectedConsoleErrors, notFound, mobileWidth: dimensions }, null, 2))
  await context.close()
} catch (error) {
  console.error(error)
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  stopServer()
}
