import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowRight, Check, Eye, RotateCcw, X } from 'lucide-react'
import { api } from '../api'
import type { Card, ReviewState } from '../types'

interface Props {
  cards: Card[]
  title: string
  onClose: () => void
  onReviewed: (card: Card) => void
  onFinish: (summary: { known: number; again: number }) => void
  // 卡片可能因为后台重新生成而不存在了，这时要刷新外部列表
  onStale: () => void
}

export default function ReviewDialog({ cards, title, onClose, onReviewed, onFinish, onStale }: Props) {
  const queue = useMemo(() => cards.filter((card) => card.review_state !== 'known'), [cards])
  const [index, setIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [known, setKnown] = useState(0)
  const [again, setAgain] = useState(0)
  const [done, setDone] = useState(false)

  const current = queue[index]
  const total = queue.length

  const advance = useCallback(() => {
    setRevealed(false)
    setError('')
    if (index + 1 >= total) setDone(true)
    else setIndex(index + 1)
  }, [index, total])

  const mark = useCallback(async (state: ReviewState) => {
    if (!current || busy) return
    setBusy(true)
    try {
      const updated = await api.reviewCard(current.id, state)
      onReviewed(updated)
      if (state === 'known') setKnown((value) => value + 1)
      else setAgain((value) => value + 1)
      advance()
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : '保存失败'
      // 卡片被重新生成后 id 会变，这时提示用户刷新，别让人以为是程序坏了
      if (message.includes('不存在')) {
        onStale()
        setError('这张卡片已经被重新生成，列表已刷新，请重新开始复习')
      } else {
        setError(message)
      }
    } finally {
      setBusy(false)
    }
  }, [advance, busy, current, onReviewed, onStale])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (done) return
      if (event.key === ' ' || event.key === 'Enter') {
        event.preventDefault()
        if (!revealed) setRevealed(true)
        return
      }
      if (!revealed) return
      if (event.key === '1') void mark('known')
      if (event.key === '2') void mark('again')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [done, mark, revealed])

  const finish = () => {
    onFinish({ known, again })
    onClose()
  }

  if (total === 0) {
    return (
      <div className="review-overlay" role="dialog" aria-modal="true">
        <div className="review-panel">
          <div className="review-finished">
            <Check size={40} />
            <h2>这份材料已经全部会了</h2>
            <p>想重新过一遍，可以在卡片上把「已掌握」改回未复习。</p>
            <button type="button" className="button button-primary" onClick={onClose}>知道了</button>
          </div>
        </div>
      </div>
    )
  }

  if (done) {
    return (
      <div className="review-overlay" role="dialog" aria-modal="true">
        <div className="review-panel">
          <div className="review-finished">
            <Check size={40} />
            <h2>这一轮过完了</h2>
            <p className="review-summary">
              <span className="review-score known">会了 {known}</span>
              <span className="review-score again">再看看 {again}</span>
            </p>
            <p>标记为「再看看」的卡片下次还会出现在复习队列里。</p>
            <button type="button" className="button button-primary" onClick={finish}>完成</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="review-overlay" role="dialog" aria-modal="true">
      <div className="review-panel">
        <header className="review-header">
          <div>
            <span className="review-source">{title}</span>
            <span className="review-progress-text">{index + 1} / {total}</span>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="退出复习"><X size={18} /></button>
        </header>

        <div className="review-bar"><span style={{ width: `${(index / total) * 100}%` }} /></div>

        <div className="review-body">
          <div className="review-meta"><span>{current.kind}</span><span>{current.topic}</span></div>
          <h2 className="review-question">{current.question || current.title}</h2>
          {current.question && <p className="review-title-hint">{current.title}</p>}

          {revealed ? (
            <div className="review-answer">
              <div className="review-answer-label">答案</div>
              <p>{current.answer}</p>
              {current.tags.length > 0 && <div className="tag-list">{current.tags.map((tag) => <span key={tag}>#{tag}</span>)}</div>}
            </div>
          ) : (
            <button type="button" className="review-reveal" onClick={() => setRevealed(true)}>
              <Eye size={18} />显示答案
              <span className="review-hint">空格键</span>
            </button>
          )}

          {error && <div className="form-error" role="alert">{error}</div>}
        </div>

        <footer className="review-actions">
          {revealed ? (
            <>
              <button type="button" className="button review-again" onClick={() => void mark('again')} disabled={busy}>
                <RotateCcw size={17} />再看看
                <span className="review-hint">2</span>
              </button>
              <button type="button" className="button review-known" onClick={() => void mark('known')} disabled={busy}>
                <Check size={17} />会了
                <span className="review-hint">1</span>
              </button>
            </>
          ) : (
            <button type="button" className="button button-ghost" onClick={advance} disabled={busy}>
              跳过这张<ArrowRight size={16} />
            </button>
          )}
        </footer>
      </div>
    </div>
  )
}
