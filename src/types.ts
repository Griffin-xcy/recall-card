export type CardKind = string

export interface Config {
  topics: string[]
  kinds: string[]
}

export interface Card {
  id: number
  material_id: number
  material_title: string
  topic: string
  kind: CardKind
  title: string
  question: string
  answer: string
  tags: string[]
  created_at: string
  updated_at: string
}

export interface TopicCount {
  topic: string
  count: number
}

export interface Stats {
  cards: number
  materials: number
  topics: number
}

export interface Material {
  id: number
  title: string
  source_type: 'file' | 'text' | 'url'
  source_uri: string
  status: 'processing' | 'completed' | 'failed'
  error: string
  created_at: string
  card_count: number
}

export interface Health {
  status: string
  version: string
  model_configured: boolean
  has_api_key: boolean
  provider: string
  model: string
  base_url: string
}

export interface CardChanges {
  topic: string
  kind: CardKind
  title: string
  question: string
  answer: string
  tags: string[]
}
