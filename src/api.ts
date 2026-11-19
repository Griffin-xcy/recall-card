import type { Card, CardChanges, Config, Health, Material, ReviewState, Stats, TopicCount } from './types'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options)
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail[0]?.msg || message
    } catch {
      // Keep the HTTP fallback message.
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/api/health'),
  saveSettings: (base_url: string, api_key: string, model: string) => request<Health>('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ base_url, api_key, model }),
  }),
  stats: () => request<Stats>('/api/stats'),
  topics: () => request<TopicCount[]>('/api/topics'),
  config: () => request<Config>('/api/config'),
  addTopic: (name: string) => request<{ topics: string[] }>('/api/config/topics', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  }),
  deleteTopic: (name: string) => request<void>(`/api/config/topics/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  addKind: (name: string) => request<{ kinds: string[] }>('/api/config/kinds', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  }),
  deleteKind: (name: string) => request<void>(`/api/config/kinds/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  materials: () => request<Material[]>('/api/materials'),
  getMaterial: (id: number) => request<Material>(`/api/materials/${id}`),
  cards: (topic: string, kind: string, query: string, state = '') => {
    const params = new URLSearchParams()
    if (topic) params.set('topic', topic)
    if (kind) params.set('kind', kind)
    if (query) params.set('q', query)
    if (state) params.set('state', state)
    return request<Card[]>(`/api/cards?${params}`)
  },
  importText: (title: string, content: string) => request<{ material: Material; cards: Card[] }>('/api/materials/text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, content }),
  }),
  importUrl: (url: string) => request<{ material: Material; cards: Card[] }>('/api/materials/url', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  }),
  importFile: (file: File, sourcePath = '', force = false) => {
    const body = new FormData()
    body.append('file', file)
    if (sourcePath) body.append('source_path', sourcePath)
    if (force) body.append('force', 'true')
    return request<{ material?: Material; cards: Card[]; duplicate?: boolean }>('/api/materials/file', { method: 'POST', body })
  },
  deleteMaterial: (id: number) => request<void>(`/api/materials/${id}`, { method: 'DELETE' }),
  regenerateMaterial: (id: number) => request<{ material: Material; cards: Card[] }>(`/api/materials/${id}/regenerate`, { method: 'POST' }),
  updateCard: (id: number, changes: CardChanges) => request<Card>(`/api/cards/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  }),
  deleteCard: (id: number) => request<void>(`/api/cards/${id}`, { method: 'DELETE' }),
  reviewCard: (id: number, state: ReviewState) => request<Card>(`/api/cards/${id}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ state }),
  }),
  bulkUpdate: (ids: number[], changes: { review_state?: ReviewState; topic?: string; kind?: string }) => request<{ updated: number }>('/api/cards/bulk-update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids, ...changes }),
  }),
  bulkDelete: (ids: number[]) => request<{ deleted: number }>('/api/cards/bulk-delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  }),
}

export async function downloadMarkdown(topic: string): Promise<void> {
  const params = new URLSearchParams()
  if (topic) params.set('topic', topic)
  const response = await fetch(`/api/export/markdown?${params}`)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail || '导出失败，请稍后重试')
  }
  const blob = await response.blob()
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = topic ? `拾记-${topic}.zip` : '拾记-全部卡片.zip'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(href)
}
