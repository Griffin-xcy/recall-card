import { useRef, useState, type DragEvent, type FormEvent } from 'react'
import { CheckCircle2, Copy, FileText, FolderOpen, Link2, LoaderCircle, RotateCcw, UploadCloud, XCircle } from 'lucide-react'
import { api } from '../api'
import type { Health, Material } from '../types'
import Modal from './Modal'

async function pollMaterial(materialId: number): Promise<Material> {
  while (true) {
    const material = await api.getMaterial(materialId)
    if (material.status === 'completed' || material.status === 'failed') return material
    await new Promise((resolve) => setTimeout(resolve, 400))
  }
}

type ImportMode = 'file' | 'folder' | 'text' | 'url'
type BatchStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'duplicate'
interface BatchItem {
  file: File
  path: string
  status: BatchStatus
  error: string
  cardCount: number
  materialId: number
}

interface ImportDialogProps {
  health: Health | null
  initialText?: string
  onClose: () => void
  onImported: (count: number, close?: boolean, message?: string) => void
  onOpenSettings: () => void
}

const directoryProps = { webkitdirectory: '', directory: '' }

export default function ImportDialog({ health, initialText = '', onClose, onImported, onOpenSettings }: ImportDialogProps) {
  const [mode, setMode] = useState<ImportMode>(initialText ? 'text' : 'file')
  const [file, setFile] = useState<File | null>(null)
  const [items, setItems] = useState<BatchItem[]>([])
  const [skipped, setSkipped] = useState(0)
  const [generatedCount, setGeneratedCount] = useState(0)
  const [title, setTitle] = useState(initialText ? '高效学习示例' : '')
  const [content, setContent] = useState(initialText)
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)

  const chooseFile = (selected?: File) => {
    if (!selected) return
    if (selected.size > 15 * 1024 * 1024) {
      setError('文件不能超过 15 MB')
      return
    }
    setError('')
    setFile(selected)
  }

  const chooseFolder = (selected: FileList | null) => {
    if (!selected) return
    const allFiles = Array.from(selected)
    const eligible = allFiles.filter((item) => item.size <= 15 * 1024 * 1024)
    setItems(eligible.map((item) => ({
      file: item,
      path: item.webkitRelativePath || item.name,
      status: 'pending',
      error: '',
      cardCount: 0,
      materialId: 0,
    })))
    setSkipped(allFiles.length - eligible.length)
    setGeneratedCount(0)
    setError(eligible.length ? '' : '文件夹中没有不超过 15 MB 的可导入文件')
  }

  const updateItem = (path: string, changes: Partial<BatchItem>) => {
    setItems((current) => current.map((item) => item.path === path ? { ...item, ...changes } : item))
  }

  const runBatch = async () => {
    const retrying = items.length > 0 && items.every((item) => item.status !== 'pending')
    const targets = items.filter((item) => retrying ? item.status === 'failed' : item.status === 'pending')
    if (!targets.length) return
    setBusy(true)
    setError('')
    const outcomes = new Map(items.map((item) => [item.path, item.status]))
    let newCards = 0
    for (const item of targets) {
      updateItem(item.path, { status: 'processing', error: '' })
      outcomes.set(item.path, 'processing')
      try {
        const result = await api.importFile(item.file, item.path)
        if (result.duplicate) {
          updateItem(item.path, { status: 'duplicate', cardCount: 0, materialId: result.material?.id ?? 0 })
          outcomes.set(item.path, 'duplicate')
          continue
        }
        const material = await pollMaterial(result.material!.id)
        if (material.status === 'failed') {
          updateItem(item.path, { status: 'failed', error: material.error || '处理失败' })
          outcomes.set(item.path, 'failed')
          continue
        }
        newCards += material.card_count
        updateItem(item.path, { status: 'completed', cardCount: material.card_count })
        outcomes.set(item.path, 'completed')
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : '处理失败'
        updateItem(item.path, { status: 'failed', error: message })
        outcomes.set(item.path, 'failed')
      }
    }
    const nextGenerated = generatedCount + newCards
    setGeneratedCount(nextGenerated)
    setBusy(false)
    const failed = Array.from(outcomes.values()).filter((status) => status === 'failed').length
    const duplicates = Array.from(outcomes.values()).filter((status) => status === 'duplicate').length
    const message = failed === 0 && newCards === 0 && duplicates > 0 ? '重复文件已跳过，未重复生成卡片' : undefined
    onImported(newCards, failed === 0 && duplicates === 0, message)
  }

  const skipDuplicate = (path: string) => {
    setItems((current) => current.filter((item) => item.path !== path))
  }

  const resolveDuplicate = async (item: BatchItem, action: 'regenerate' | 'overwrite') => {
    if (busy) return
    setBusy(true)
    try {
      const result = action === 'regenerate'
        ? await api.regenerateMaterial(item.materialId)
        : await api.importFile(item.file, item.path, true)
      const material = await pollMaterial(result.material!.id)
      if (material.status === 'failed') {
        updateItem(item.path, { status: 'failed', error: material.error || '处理失败' })
      } else {
        setGeneratedCount((current) => current + material.card_count)
        updateItem(item.path, { status: 'completed', cardCount: material.card_count, error: '' })
      }
    } catch (caught) {
      updateItem(item.path, { status: 'failed', error: caught instanceof Error ? caught.message : '处理失败' })
    } finally {
      setBusy(false)
    }
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (mode === 'folder') {
      if (!items.length) return setError('请先选择一个文件夹')
      await runBatch()
      return
    }
    if (mode === 'file' && !file) return setError('请先选择一份材料')
    if (mode === 'text' && (!title.trim() || content.trim().length < 20)) return setError('请填写标题，并输入至少 20 个字符的正文')
    if (mode === 'url' && !/^https?:\/\//i.test(url)) return setError('请输入以 http:// 或 https:// 开头的网页链接')
    setBusy(true)
    try {
      const result = mode === 'file'
        ? await api.importFile(file!)
        : mode === 'text'
          ? await api.importText(title.trim(), content.trim())
          : await api.importUrl(url.trim())
      const material = await pollMaterial(result.material!.id)
      if (material.status === 'failed') {
        setError(material.error || '处理失败')
        setBusy(false)
        return
      }
      onImported(material.card_count)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '处理失败，请重试')
      setBusy(false)
    }
  }

  const drop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    chooseFile(event.dataTransfer.files[0])
  }

  const completed = items.filter((item) => item.status === 'completed').length
  const failed = items.filter((item) => item.status === 'failed').length
  const duplicates = items.filter((item) => item.status === 'duplicate').length
  const processed = completed + failed + duplicates
  const progress = items.length ? Math.round(processed / items.length * 100) : 0
  const retrying = items.length > 0 && items.every((item) => item.status !== 'pending')

  return (
    <Modal title="把材料变成卡片" description="本地保存材料，模型只负责提取，不替你补充知识。" onClose={busy ? () => undefined : onClose} wide>
      {health && !health.model_configured && (
        <div className="config-notice"><span>第 1 步还未完成：请先连接模型，再导入材料。</span><button type="button" className="config-action" onClick={onOpenSettings}>连接模型</button></div>
      )}
      <div className="import-tabs" role="tablist" aria-label="材料类型">
        <button type="button" role="tab" aria-selected={mode === 'file'} className={mode === 'file' ? 'active' : ''} onClick={() => { setMode('file'); setError('') }} disabled={busy}><UploadCloud size={17} />上传文件</button>
        <button type="button" role="tab" aria-selected={mode === 'folder'} className={mode === 'folder' ? 'active' : ''} onClick={() => { setMode('folder'); setError('') }} disabled={busy}><FolderOpen size={17} />选择文件夹</button>
        <button type="button" role="tab" aria-selected={mode === 'text'} className={mode === 'text' ? 'active' : ''} onClick={() => { setMode('text'); setError('') }} disabled={busy}><FileText size={17} />粘贴文本</button>
        <button type="button" role="tab" aria-selected={mode === 'url'} className={mode === 'url' ? 'active' : ''} onClick={() => { setMode('url'); setError('') }} disabled={busy}><Link2 size={17} />网页链接</button>
      </div>
      <form onSubmit={submit} className="import-form">
        {mode === 'file' && (
          <>
            <input ref={fileInput} type="file" className="visually-hidden" onChange={(event) => chooseFile(event.target.files?.[0])} />
            <button type="button" className={`drop-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`} onClick={() => fileInput.current?.click()} onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={drop} disabled={busy}>
              <UploadCloud size={30} />
              {file ? <><strong>{file.name}</strong><span>{(file.size / 1024).toFixed(1)} KB · 点击可重新选择</span></> : <><strong>拖拽文件到这里，或点击选择</strong><span>支持 PDF、文本和任意扩展名的代码文件，最大 15 MB</span></>}
            </button>
            <p className="field-hint">扫描版 PDF、图片、Office 文档等需要专用解析；请勿上传包含密码等敏感信息的材料。</p>
          </>
        )}
        {mode === 'folder' && (
          <>
            <input ref={folderInput} {...directoryProps} type="file" className="visually-hidden" aria-label="选择材料文件夹" onChange={(event) => { chooseFolder(event.target.files); event.target.value = '' }} />
            <button type="button" className="drop-zone folder-zone" onClick={() => folderInput.current?.click()} disabled={busy}>
              <FolderOpen size={30} />
              <strong>{items.length ? `已选择 ${items.length} 份材料` : '选择一个文件夹，自动读取所有子目录'}</strong>
              <span>读取所有文件并尝试提取文本，单文件不超过 15 MB</span>
            </button>
            {items.length > 0 && (
              <div className="batch-panel">
                <div className="batch-summary"><span>共 {items.length} 份 · 已完成 {processed} 份</span><strong>{progress}%</strong></div>
                <div className="batch-progress" role="progressbar" aria-label="文件夹导入进度" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{ width: `${progress}%` }} /></div>
                <div className="batch-list" aria-label="批量材料处理状态">
                  {items.map((item) => (
                    <div className={`batch-item batch-${item.status}`} key={item.path}>
                      <span className="batch-item-icon">{item.status === 'processing' ? <LoaderCircle size={16} className="spin" /> : item.status === 'completed' ? <CheckCircle2 size={16} /> : item.status === 'failed' ? <XCircle size={16} /> : item.status === 'duplicate' ? <Copy size={16} /> : <FileText size={16} />}</span>
                      <div>
                        <span title={item.path}>{item.path}</span>
                        {item.error && <small>{item.error}</small>}
                        {item.status === 'duplicate' && (
                          <div className="batch-dup-actions">
                            <button type="button" onClick={() => skipDuplicate(item.path)} disabled={busy}>跳过</button>
                            <button type="button" onClick={() => void resolveDuplicate(item, 'regenerate')} disabled={busy}>重新生成</button>
                            <button type="button" onClick={() => void resolveDuplicate(item, 'overwrite')} disabled={busy}>覆盖旧版本</button>
                          </div>
                        )}
                      </div>
                      <strong>{item.status === 'processing' ? '处理中' : item.status === 'completed' ? `${item.cardCount} 张` : item.status === 'failed' ? '失败' : item.status === 'duplicate' ? '重复跳过' : '等待'}</strong>
                    </div>
                  ))}
                </div>
                {skipped > 0 && <p className="field-hint">已跳过 {skipped} 个超过 15 MB 的文件。</p>}
                {!busy && processed > 0 && (
                  <p className={`batch-result ${failed ? 'has-failures' : ''}`} role="status">本次已生成 {generatedCount} 张卡片{failed ? `，${failed} 份失败，可只重试失败项。` : ''}{duplicates ? `，${duplicates} 份重复已跳过。` : ''}{failed === 0 && duplicates === 0 ? '，全部处理完成。' : ''}</p>
                )}
              </div>
            )}
          </>
        )}
        {mode === 'text' && (
          <>
            <label>材料标题<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：第三章 · 记忆与学习" maxLength={200} disabled={busy} /></label>
            <label>正文<textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="粘贴课程笔记、会议转写或任何想复习的文字……" rows={9} disabled={busy} /><span className="field-hint">{content.length} 字，至少 20 字</span></label>
          </>
        )}
        {mode === 'url' && (
          <label>网页地址<input type="url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com/article" disabled={busy} /><span className="field-hint">将自动提取正文，尽量去掉导航、广告和页脚。</span></label>
        )}
        {error && <div className="form-error" role="alert">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>取消</button>
          <button type="submit" className="button button-primary" disabled={busy || Boolean(health && !health.model_configured)} title={health && !health.model_configured ? '请先连接模型' : undefined}>
            {busy ? <><LoaderCircle size={17} className="spin" />{mode === 'folder' ? `正在处理 ${Math.min(processed + 1, items.length)} / ${items.length}` : '正在提取卡片…'}</> : mode === 'folder' ? retrying && failed ? <><RotateCcw size={17} />重试失败文件（{failed}）</> : '开始批量生成' : health && !health.model_configured ? '请先连接模型' : '开始生成'}
          </button>
        </div>
        {busy && <p className="processing-note" role="status">{mode === 'folder' ? '正在逐份处理，单份失败不会中断队列，请不要关闭页面。' : '正在分块并整理内容，较长材料可能需要一两分钟，请不要关闭页面。'}</p>}
      </form>
    </Modal>
  )
}
