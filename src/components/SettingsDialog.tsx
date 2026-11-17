import { useState, type FormEvent } from 'react'
import { Eye, EyeOff, KeyRound, LoaderCircle, Plus, ShieldCheck, X } from 'lucide-react'
import { api } from '../api'
import type { Health } from '../types'
import Modal from './Modal'

interface Props {
  health: Health | null
  topics: string[]
  kinds: string[]
  onClose: () => void
  onSaved: (health: Health) => void
  onConfigSaved: () => void
}

const providers = [
  { id: 'deepseek', name: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-flash' },
  { id: 'kimi', name: 'Kimi（Moonshot AI）', baseUrl: 'https://api.moonshot.cn/v1', model: 'kimi-k3.1-pro' },
  { id: 'openai', name: 'OpenAI', baseUrl: 'https://api.openai.com/v1', model: 'gpt-5.4' },
  { id: 'qwen', name: '通义千问', baseUrl: 'https://WorkspaceId.cn-beijing.maas.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  { id: 'zhipu', name: '智谱 AI', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-5.3' },
  { id: 'ollama', name: 'Ollama（本地模型）', baseUrl: 'http://localhost:11434/v1', model: 'qwen3:8b' },
  { id: 'custom', name: '自定义 OpenAI 兼容接口', baseUrl: '', model: '' },
]

function detectProvider(baseUrl?: string) {
  const normalized = baseUrl?.replace(/\/$/, '')
  return providers.find((provider) => provider.id !== 'custom' && provider.baseUrl === normalized)?.id || 'custom'
}

export default function SettingsDialog({ health, topics, kinds, onClose, onSaved, onConfigSaved }: Props) {
  const initialBaseUrl = health?.base_url || providers[0].baseUrl
  const [provider, setProvider] = useState(() => health?.base_url ? detectProvider(health.base_url) : 'deepseek')
  const [baseUrl, setBaseUrl] = useState(initialBaseUrl)
  const [model, setModel] = useState(health?.model === 'local-demo' ? providers[0].model : health?.model || providers[0].model)
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [newTopic, setNewTopic] = useState('')
  const [newKind, setNewKind] = useState('')

  const changeProvider = (nextId: string) => {
    const next = providers.find((item) => item.id === nextId)
    if (!next) return
    setProvider(nextId)
    setError('')
    if (nextId !== 'custom') {
      setBaseUrl(next.baseUrl)
      setModel(next.model)
    }
    if (nextId !== provider) setApiKey(nextId === 'ollama' ? 'ollama' : '')
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (!/^https?:\/\//i.test(baseUrl.trim())) return setError('接口地址必须以 https:// 或 http:// 开头')
    if (!model.trim()) return setError('请填写模型名称')
    if (provider === 'qwen' && /WorkspaceId/i.test(baseUrl.trim())) return setError('请先将接口地址中的 WorkspaceId 替换为你的阿里云业务空间 ID')
    const retainingSameProviderKey = !apiKey.trim() && health?.has_api_key && provider === detectProvider(health.base_url)
    if (!apiKey.trim() && !retainingSameProviderKey) return setError('请输入模型 API Key')
    setBusy(true)
    try {
      const updated = await api.saveSettings(baseUrl.trim(), apiKey.trim(), model.trim())
      onSaved(updated)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '设置保存失败')
      setBusy(false)
    }
  }

  const addTopic = async () => {
    const name = newTopic.trim()
    if (!name) return
    try {
      await api.addTopic(name)
      setNewTopic('')
      onConfigSaved()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '添加主题失败')
    }
  }

  const removeTopic = async (name: string) => {
    try {
      await api.deleteTopic(name)
      onConfigSaved()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '删除主题失败')
    }
  }

  const addKind = async () => {
    const name = newKind.trim()
    if (!name) return
    try {
      await api.addKind(name)
      setNewKind('')
      onConfigSaved()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '添加类型失败')
    }
  }

  const removeKind = async (name: string) => {
    try {
      await api.deleteKind(name)
      onConfigSaved()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '删除类型失败')
    }
  }

  return (
    <Modal title={health?.model_configured ? '模型设置' : '连接模型'} description="先选择服务商，再填写 API Key。支持云端服务和本地模型。" onClose={busy ? () => undefined : onClose}>
      <form onSubmit={submit} className="edit-form settings-form">
        <div className="settings-local-note"><ShieldCheck size={19} /><span>API Key 仅保存到本机 SQLite 数据库，不会回显到页面，也不会包含在导出文件中。</span></div>
        <label>服务商
          <select aria-label="服务商" value={provider} onChange={(event) => changeProvider(event.target.value)} disabled={busy}>
            {providers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <span className="field-hint">选择后会自动填入接口地址和推荐模型，仍可手动修改。</span>
        </label>
        <div className="field-group"><label htmlFor="api-key">API Key</label>
          <div className="secret-input"><KeyRound size={17} /><input id="api-key" type={showKey ? 'text' : 'password'} value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={provider === 'ollama' ? '本地 Ollama 可保持为 ollama' : health?.has_api_key && provider === detectProvider(health.base_url) ? '留空则保留已保存的 Key' : '输入你的模型 API Key'} autoComplete="off" disabled={busy} /><button type="button" className="icon-button" onClick={() => setShowKey((visible) => !visible)} aria-label={showKey ? '隐藏 API Key' : '显示 API Key'}>{showKey ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>
        </div>
        <label>接口地址<input type="url" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" disabled={busy} /><span className="field-hint">填写 API 根地址，应用会自动追加 /chat/completions。</span></label>
        <label>模型名称<input value={model} onChange={(event) => setModel(event.target.value)} placeholder="输入服务商提供的模型 ID" maxLength={200} disabled={busy} /></label>
        {provider === 'qwen' && <p className="provider-hint">通义千问：请将接口地址中的 WorkspaceId 替换为你的阿里云业务空间 ID。</p>}
        {provider === 'ollama' && <p className="provider-hint">本地模型：请先启动 Ollama 并下载上方模型。API Key 已填为 ollama，本地服务会忽略该值。</p>}
        {error && <div className="form-error" role="alert">{error}</div>}
        <div className="config-section">
          <div className="config-section-title">主题与类型</div>
          <div className="config-group">
            <span className="config-label">主题</span>
            <div className="config-tags">
              {topics.map((topic) => <span key={topic} className="config-tag">{topic}<button type="button" onClick={() => void removeTopic(topic)} aria-label={`删除主题 ${topic}`}><X size={12} /></button></span>)}
            </div>
            <div className="config-add"><input value={newTopic} onChange={(event) => setNewTopic(event.target.value)} placeholder="新主题名称" maxLength={30} /><button type="button" onClick={() => void addTopic()}><Plus size={14} />添加</button></div>
          </div>
          <div className="config-group">
            <span className="config-label">类型</span>
            <div className="config-tags">
              {kinds.map((kind) => <span key={kind} className="config-tag">{kind}<button type="button" onClick={() => void removeKind(kind)} aria-label={`删除类型 ${kind}`}><X size={12} /></button></span>)}
            </div>
            <div className="config-add"><input value={newKind} onChange={(event) => setNewKind(event.target.value)} placeholder="新类型名称" maxLength={30} /><button type="button" onClick={() => void addKind()}><Plus size={14} />添加</button></div>
          </div>
        </div>
        <div className="modal-actions"><button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>取消</button><button type="submit" className="button button-primary" disabled={busy}>{busy ? <><LoaderCircle size={17} className="spin" />保存中…</> : '保存并使用'}</button></div>
      </form>
    </Modal>
  )
}
