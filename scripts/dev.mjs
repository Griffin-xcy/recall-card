import { spawn } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const env = { ...process.env }
if (existsSync(path.join(root, '.env'))) {
  for (const line of readFileSync(path.join(root, '.env'), 'utf8').split(/\r?\n/)) {
    const match = line.match(/^([A-Z_]+)=(.*)$/)
    if (match && !env[match[1]]) env[match[1]] = match[2].replace(/^['"]|['"]$/g, '')
  }
}

const python = existsSync(path.join(root, '.venv', 'Scripts', 'python.exe'))
  ? path.join(root, '.venv', 'Scripts', 'python.exe')
  : existsSync(path.join(root, '.venv', 'bin', 'python'))
    ? path.join(root, '.venv', 'bin', 'python')
    : 'python'
const port = env.PORT || '8000'
const vite = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')

const children = [
  spawn(python, ['-m', 'uvicorn', 'backend.main:app', '--host', '0.0.0.0', '--port', port], { cwd: root, env, stdio: 'inherit' }),
  spawn(process.execPath, [vite, ...process.argv.slice(2)], { cwd: root, env, stdio: 'inherit' }),
]
let stopping = false
function stop(code = 0) {
  if (stopping) return
  stopping = true
  for (const child of children) if (!child.killed) child.kill('SIGTERM')
  setTimeout(() => process.exit(code), 150).unref()
}
for (const child of children) child.on('exit', (code) => stop(code || 0))
process.on('SIGINT', () => stop(0))
process.on('SIGTERM', () => stop(0))
