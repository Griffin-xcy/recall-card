import { useState, type FormEvent } from 'react'
import { LoaderCircle } from 'lucide-react'
import { api } from '../api'
import type { Card } from '../types'
import Modal from './Modal'

interface Props {
  card: Card
  topics: string[]
  kinds: string[]
  onClose: () => void
  onSaved: (card: Card) => void
}

export default function EditCardDialog({ card, topics, kinds, onClose, onSaved }: Props) {
  const [title, setTitle] = useState(card.title)
  const [kind, setKind] = useState(card.kind)
  const [topic, setTopic] = useState(card.topic)
  const [question, setQuestion] = useState(card.question)
  const [answer, setAnswer] = useState(card.answer)
  const [tags, setTags] = useState(card.tags.join('，'))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!title.trim() || !answer.trim() || !topic.trim()) return setError('标题、主题和内容不能为空')
    setBusy(true)
    setError('')
    try {
      const updated = await api.updateCard(card.id, {
        title: title.trim(), kind, topic: topic.trim(), question: question.trim(), answer: answer.trim(),
        tags: tags.split(/[,，]/).map((tag) => tag.trim()).filter(Boolean).slice(0, 6),
      })
      onSaved(updated)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '保存失败')
      setBusy(false)
    }
  }

  return (
    <Modal title="编辑卡片" description={`来源：${card.material_title}`} onClose={busy ? () => undefined : onClose} wide>
      <form onSubmit={submit} className="edit-form">
        <div className="form-row">
          <label>卡片类型<select value={kind} onChange={(event) => setKind(event.target.value)} disabled={busy}>{kinds.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>主题<input list="topic-options" value={topic} onChange={(event) => setTopic(event.target.value)} maxLength={60} disabled={busy} /><datalist id="topic-options">{topics.map((item) => <option key={item}>{item}</option>)}</datalist></label>
        </div>
        <label>标题<input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} disabled={busy} /></label>
        <label>问题（能问成具体问题的卡片填这里）<textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={2} disabled={busy} placeholder="例如：什么是主动回忆？" /></label>
        <label>卡片内容<textarea value={answer} onChange={(event) => setAnswer(event.target.value)} rows={7} disabled={busy} /></label>
        <label>标签<input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="用逗号分隔，例如：学习，记忆" disabled={busy} /></label>
        {error && <div className="form-error" role="alert">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>取消</button>
          <button type="submit" className="button button-primary" disabled={busy}>{busy ? <><LoaderCircle size={17} className="spin" />保存中…</> : '保存修改'}</button>
        </div>
      </form>
    </Modal>
  )
}
