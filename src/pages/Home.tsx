import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft, BookOpen, Check, CheckCircle2, Clock3, Download, FileText, Inbox,
  Layers3, LoaderCircle, Pencil, Play, Plus, Search, Settings2, ShieldCheck, Trash2, XCircle,
} from 'lucide-react'
import { api, downloadMarkdown } from '../api'
import EditCardDialog from '../components/EditCardDialog'
import ImportDialog from '../components/ImportDialog'
import Modal from '../components/Modal'
import ReviewDialog from '../components/ReviewDialog'
import SettingsDialog from '../components/SettingsDialog'
import type { Card, Config, Health, Material, Stats, TopicCount } from '../types'

const emptyStats: Stats = { cards: 0, materials: 0, topics: 0, reviewed_cards: 0, known_cards: 0, again_cards: 0 }
const sampleText = `间隔重复是一种通过逐步增加复习间隔来巩固记忆的学习方法。它要求学习者在即将遗忘时再次接触材料，而不是连续重复阅读。

主动回忆指在不查看答案的情况下尝试提取信息。与被动阅读相比，主动回忆能更清楚地暴露知识盲点，并加强记忆路径。

实践时，应先制作问题明确的卡片，再根据自己的回忆质量安排复习。每张卡片只保留一个核心问题，避免把整段笔记直接复制到答案中。`

export default function Home() {
  const [cards, setCards] = useState<Card[]>([])
  const [topics, setTopics] = useState<TopicCount[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [stats, setStats] = useState<Stats>(emptyStats)
  const [health, setHealth] = useState<Health | null>(null)
  const [config, setConfig] = useState<Config>({ topics: [], kinds: [] })
  const [selectedTopic, setSelectedTopic] = useState('')
  const [selectedKind, setSelectedKind] = useState('')
  const [query, setQuery] = useState('')
  const [view, setView] = useState<'cards' | 'materials'>('cards')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [importOpen, setImportOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [editing, setEditing] = useState<Card | null>(null)
  const [deleting, setDeleting] = useState<Card | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [toast, setToast] = useState('')
  const [reviewQueue, setReviewQueue] = useState<{ cards: Card[]; title: string } | null>(null)
  const toastTimer = useRef<number | undefined>(undefined)

  const notify = useCallback((message: string) => {
    window.clearTimeout(toastTimer.current)
    setToast(message)
    toastTimer.current = window.setTimeout(() => setToast(''), 3500)
  }, [])

  const refreshMeta = useCallback(async () => {
    try {
      const [nextStats, nextTopics, nextMaterials, nextHealth, nextConfig] = await Promise.all([
        api.stats(), api.topics(), api.materials(), api.health(), api.config(),
      ])
      setStats(nextStats)
      setTopics(nextTopics)
      setMaterials(nextMaterials)
      setHealth(nextHealth)
      setConfig(nextConfig)
    } catch (caught) {
      setLoadError(caught instanceof Error ? caught.message : '无法连接本地服务')
    }
  }, [])

  const loadCards = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setLoadError('')
    try {
      const result = await api.cards(selectedTopic, selectedKind, query.trim())
      if (!signal?.aborted) setCards(result)
    } catch (caught) {
      if (!signal?.aborted) setLoadError(caught instanceof Error ? caught.message : '卡片加载失败')
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [selectedTopic, selectedKind, query])

  useEffect(() => {
    void refreshMeta()
  }, [refreshMeta])

  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => void loadCards(controller.signal), query ? 250 : 0)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [loadCards, query])

  useEffect(() => () => window.clearTimeout(toastTimer.current), [])

  const openImport = (text = '') => {
    setImportText(text)
    setImportOpen(true)
  }

  const imported = async (count: number, close = true, message = '') => {
    if (close) setImportOpen(false)
    setSelectedTopic('')
    setSelectedKind('')
    setQuery('')
    setView('cards')
    await Promise.all([refreshMeta(), loadCards()])
    notify(message || (count > 0 ? `已生成 ${count} 张卡片，可以开始整理了` : '没有新增卡片，可能内容重复或未提取到有效内容'))
  }

  const saved = async (updated: Card) => {
    setEditing(null)
    setCards((current) => current.map((card) => card.id === updated.id ? updated : card))
    await Promise.all([refreshMeta(), loadCards()])
    notify('卡片修改已保存')
  }

  const remove = async () => {
    if (!deleting) return
    setDeleteBusy(true)
    try {
      await api.deleteCard(deleting.id)
      setCards((current) => current.filter((card) => card.id !== deleting.id))
      setDeleting(null)
      await refreshMeta()
      notify('卡片已删除')
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : '删除失败')
    } finally {
      setDeleteBusy(false)
    }
  }

  const exportCards = async () => {
    setExporting(true)
    try {
      await downloadMarkdown(selectedTopic)
      notify('Markdown 文件已按主题打包导出')
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : '导出失败')
    } finally {
      setExporting(false)
    }
  }

  const showAll = () => {
    setSelectedTopic('')
    setView('cards')
  }

  // 卡片按来源材料分组，最新的材料排在最前面。
  // 导入完成后不需要额外跳转，新分组天然就在顶部。
  const groups = useMemo(() => {
    const map = new Map<number, { id: number; title: string; date: string; cards: Card[] }>()
    for (const card of cards) {
      const group = map.get(card.material_id)
      if (group) group.cards.push(card)
      else map.set(card.material_id, { id: card.material_id, title: card.material_title, date: card.created_at, cards: [card] })
    }
    return [...map.values()]
      .map((group) => ({ ...group, cards: [...group.cards].sort((a, b) => a.id - b.id) }))
      .sort((a, b) => (a.date === b.date ? b.id - a.id : a.date < b.date ? 1 : -1))
  }, [cards])

  const startReview = (target: Card[], title: string) => {
    const pending = target.filter((card) => card.review_state !== 'known')
    if (pending.length === 0) {
      notify('这些卡片都已经标记为会了')
      return
    }
    setReviewQueue({ cards: pending, title })
  }

  const reviewed = (updated: Card) => {
    setCards((current) => current.map((card) => (card.id === updated.id ? updated : card)))
  }

  const finishedReview = (summary: { known: number; again: number }) => {
    setReviewQueue(null)
    void refreshMeta()
    notify(`本轮：会了 ${summary.known} 张，再看看 ${summary.again} 张`)
  }

  const pageTitle = view === 'materials' ? '导入记录' : selectedTopic || '全部卡片'
  const pageSubtitle = view === 'materials'
    ? '每份材料的处理状态都留在这里'
    : selectedTopic ? `这个主题下有 ${stats.cards ? cards.length : 0} 张当前筛选卡片` : '把读过的东西，变成记得住的内容'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button type="button" className="brand" onClick={showAll} aria-label="拾记首页">
          <span className="brand-mark"><Layers3 size={22} /></span>
          <span><strong>拾记</strong><small>RECALL CARD</small></span>
        </button>
        <button type="button" className="button button-primary sidebar-import" onClick={() => openImport()}><Plus size={18} />导入材料</button>
        <nav className="main-nav" aria-label="主导航">
          <button type="button" className={view === 'cards' && !selectedTopic ? 'nav-item active' : 'nav-item'} onClick={showAll}><BookOpen size={18} /><span>全部卡片</span><span className="nav-count">{stats.cards}</span></button>
          <button type="button" className={view === 'materials' ? 'nav-item active' : 'nav-item'} onClick={() => setView('materials')}><FileText size={18} /><span>导入记录</span><span className="nav-count">{stats.materials}</span></button>
        </nav>
        <div className="topic-nav">
          <div className="nav-label">主题目录</div>
          {topics.length === 0 ? <p className="topic-empty">导入材料后，主题会出现在这里。</p> : topics.map((topic) => (
            <button type="button" key={topic.topic} className={view === 'cards' && selectedTopic === topic.topic ? 'topic-item active' : 'topic-item'} onClick={() => { setSelectedTopic(topic.topic); setView('cards') }}>
              <span>{topic.topic}</span><span>{topic.count}</span>
            </button>
          ))}
        </div>
        <div className="privacy-note"><ShieldCheck size={17} /><span>数据保存在本机<br />模型 Key 由你掌握</span></div>
      </aside>

      <main className="workspace">
        <header className="workspace-header">
          <div className="heading-group">
            {view === 'cards' && selectedTopic && <button type="button" className="back-button" onClick={showAll}><ArrowLeft size={16} />全部卡片</button>}
            <h1>{pageTitle}</h1>
            <p>{pageSubtitle}</p>
          </div>
          <div className="header-actions">
            <button type="button" className={`button settings-button ${health && !health.model_configured ? 'button-primary' : 'button-secondary'}`} onClick={() => setSettingsOpen(true)} title={health?.model_configured ? '模型设置' : '第一步：连接用于生成卡片的模型'}><Settings2 size={18} /><span>{health?.model_configured ? '模型设置' : '连接模型'}</span></button>
            <button type="button" className="button button-secondary review-start" onClick={() => startReview(cards, selectedTopic || '全部卡片')} disabled={stats.cards === 0} title="逐张复习，标记会了或再看看"><Play size={17} /><span>开始复习</span></button>
            <button type="button" className="button button-secondary export-button" onClick={exportCards} disabled={exporting || stats.cards === 0} title={stats.cards === 0 ? '暂无卡片可导出' : '按主题导出 Markdown ZIP'}>
              {exporting ? <LoaderCircle size={17} className="spin" /> : <Download size={17} />}<span>导出 Markdown</span>
            </button>
            <button type="button" className="button button-primary header-import" onClick={() => openImport()}><Plus size={18} /><span>导入材料</span></button>
          </div>
        </header>

        {health && !health.model_configured && <div className="setup-banner"><div><span><strong>第 1 步：连接模型</strong><span className="setup-step">第 2 步：导入材料，生成卡片</span></span><button type="button" className="setup-action" onClick={() => setSettingsOpen(true)}>连接模型</button></div><span>支持 DeepSeek、Kimi、OpenAI、通义千问、智谱和本地 Ollama</span></div>}

        <section className="stats-strip" aria-label="内容统计">
          <div><strong>{stats.cards}</strong><span>张卡片</span></div>
          <div><strong>{stats.known_cards}</strong><span>张已掌握</span></div>
          <div><strong>{stats.again_cards}</strong><span>待再看</span></div>
          <div><strong>{stats.materials}</strong><span>份材料</span></div>
          <p><span className={`status-dot ${health?.status === 'ok' ? 'online' : ''}`} />{health?.provider === 'mock' ? '本地演示模式' : health?.model_configured ? '模型已就绪' : '等待模型配置'}</p>
        </section>

        {view === 'cards' ? (
          <>
            <div className="filter-bar">
              <label className="search-box"><Search size={18} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索标题、内容或标签" aria-label="搜索卡片" />{query && <button type="button" onClick={() => setQuery('')} aria-label="清空搜索">清除</button>}</label>
              <div className="kind-filters" aria-label="按类型筛选">
                <button type="button" className={selectedKind === '' ? 'filter-chip active' : 'filter-chip'} onClick={() => setSelectedKind('')}>全部类型</button>
                {config.kinds.map((kind) => <button type="button" key={kind} className={selectedKind === kind ? 'filter-chip active' : 'filter-chip'} onClick={() => setSelectedKind(kind)}>{kind}</button>)}
              </div>
            </div>

            <div className="content-area">
              {loading ? <div className="loading-state" role="status"><LoaderCircle size={28} className="spin" /><span>正在读取卡片…</span></div>
                : loadError ? <div className="empty-state"><XCircle size={36} /><h2>暂时连不上本地服务</h2><p>{loadError}</p><button type="button" className="button button-primary" onClick={() => { void loadCards(); void refreshMeta() }}>重新连接</button></div>
                  : cards.length === 0 ? (
                    <div className="empty-state">
                      <div className="empty-illustration"><Inbox size={38} /></div>
                      <h2>{stats.cards === 0 ? health && !health.model_configured ? '先连接你的模型' : '从第一份材料开始' : '没有找到匹配的卡片'}</h2>
                      <p>{stats.cards === 0 ? health && !health.model_configured ? '选择 DeepSeek、Kimi、OpenAI 等服务商，或使用本地 Ollama。连接后再导入材料。' : '上传一份 PDF，或粘贴一段笔记。拾记会提取真正值得复习的内容。' : '试试更换主题、类型或搜索关键词。'}</p>
                      {stats.cards === 0 ? health && !health.model_configured ? <button type="button" className="button button-primary" onClick={() => setSettingsOpen(true)}><Settings2 size={17} />连接模型</button> : <div className="empty-actions"><button type="button" className="button button-primary" onClick={() => openImport()}><Plus size={17} />导入第一份材料</button><button type="button" className="button button-ghost" onClick={() => openImport(sampleText)}>使用示例文本</button></div> : <button type="button" className="button button-secondary" onClick={() => { setQuery(''); setSelectedKind(''); setSelectedTopic('') }}>清除筛选</button>}
                    </div>
                  ) : (
                    <div className="card-groups">
                      {groups.map((group) => {
                        const known = group.cards.filter((card) => card.review_state === 'known').length
                        const pending = group.cards.length - known
                        return (
                          <section className="card-group" key={group.id}>
                            <header className="group-header">
                              <div className="group-title">
                                <FileText size={16} />
                                <h2 title={group.title}>{group.title}</h2>
                                <span className="group-meta">{group.cards.length} 张 · {new Date(group.date).toLocaleDateString('zh-CN')}</span>
                              </div>
                              <div className="group-actions">
                                <span className="group-progress">{known}/{group.cards.length} 已掌握</span>
                                <button type="button" className="button button-ghost group-review" onClick={() => startReview(group.cards, group.title)} disabled={pending === 0}>
                                  <Play size={15} />{pending === 0 ? '已全部掌握' : `复习这份（剩 ${pending}）`}
                                </button>
                              </div>
                            </header>
                            <div className="card-grid">
                              {group.cards.map((card) => (
                                <article className="study-card" key={card.id}>
                                  <div className="card-topline"><span className={`kind-badge kind-${(Math.max(config.kinds.indexOf(card.kind), 0) % 4) + 1}`}>{card.kind}</span><span className="card-topic">{card.topic}</span>{card.review_state === 'known' && <span className="review-badge known">已掌握</span>}{card.review_state === 'again' && <span className="review-badge again">再看看</span>}<div className="card-tools"><button type="button" className="icon-button" onClick={() => setEditing(card)} aria-label={`编辑 ${card.title}`}><Pencil size={16} /></button><button type="button" className="icon-button delete-tool" onClick={() => setDeleting(card)} aria-label={`删除 ${card.title}`}><Trash2 size={16} /></button></div></div>
                                  <h2>{card.title}</h2>
                                  {card.question && <p className="card-question">{card.question}</p>}
                                  <p className="card-answer">{card.answer}</p>
                                  {card.tags.length > 0 && <div className="tag-list">{card.tags.map((tag) => <span key={tag}>#{tag}</span>)}</div>}
                                  <footer><span className="card-source" title={group.title}>{card.review_state === 'known' ? '已掌握' : card.review_state === 'again' ? '再看看' : '待复习'}</span><span>{new Date(card.created_at).toLocaleDateString('zh-CN')}</span></footer>
                                </article>
                              ))}
                            </div>
                          </section>
                        )
                      })}
                    </div>
                  )}
            </div>
          </>
        ) : (
          <div className="content-area materials-view">
            {materials.length === 0 ? <div className="empty-state"><FileText size={36} /><h2>还没有导入记录</h2><p>文件、文本和网页的处理状态会集中显示在这里。</p><button type="button" className="button button-primary" onClick={() => openImport()}>导入材料</button></div>
              : <div className="material-list">{materials.map((material) => <article className="material-row" key={material.id}><div className="material-icon"><FileText size={20} /></div><div className="material-info"><h2>{material.title}</h2><p>{material.source_type === 'url' ? '网页链接' : material.source_type === 'file' ? '本地文件' : '粘贴文本'} · {new Date(material.created_at).toLocaleString('zh-CN')}</p>{material.error && <p className="material-error">{material.error}</p>}</div><div className={`material-status status-${material.status}`}>{material.status === 'completed' ? <CheckCircle2 size={16} /> : material.status === 'failed' ? <XCircle size={16} /> : <Clock3 size={16} />}{material.status === 'completed' ? `${material.card_count} 张卡片` : material.status === 'failed' ? '处理失败' : '处理中'}</div></article>)}</div>}
          </div>
        )}
      </main>

      {importOpen && <ImportDialog health={health} initialText={importText} onClose={() => setImportOpen(false)} onImported={(count, close) => void imported(count, close)} onOpenSettings={() => { setImportOpen(false); setSettingsOpen(true) }} />}
      {settingsOpen && <SettingsDialog health={health} topics={config.topics} kinds={config.kinds} onClose={() => setSettingsOpen(false)} onSaved={(updated) => { setHealth(updated); setSettingsOpen(false); notify('模型设置已保存，可以开始生成') }} onConfigSaved={() => void refreshMeta()} />}
      {editing && <EditCardDialog card={editing} topics={config.topics} kinds={config.kinds} onClose={() => setEditing(null)} onSaved={(card) => void saved(card)} />}
      {deleting && <Modal title="删除这张卡片？" description="删除后无法恢复，原始导入材料仍会保留。" onClose={() => setDeleting(null)}><div className="delete-preview"><strong>{deleting.title}</strong><span>{deleting.topic} · {deleting.kind}</span></div><div className="modal-actions"><button type="button" className="button button-ghost" onClick={() => setDeleting(null)} disabled={deleteBusy}>取消</button><button type="button" className="button button-danger" onClick={() => void remove()} disabled={deleteBusy}>{deleteBusy ? <LoaderCircle size={17} className="spin" /> : <Check size={17} />}确认删除</button></div></Modal>}
      {reviewQueue && <ReviewDialog cards={reviewQueue.cards} title={reviewQueue.title} onClose={() => setReviewQueue(null)} onReviewed={reviewed} onFinish={finishedReview} />}
      {toast && <div className="toast" role="status"><CheckCircle2 size={18} />{toast}</div>}
    </div>
  )
}
