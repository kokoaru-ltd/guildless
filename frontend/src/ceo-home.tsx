import { FormEvent, useEffect, useRef, useState } from 'react'
import { CircleStop, LoaderCircle, Mic, Send, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'

type Job = { job_id: string; status: string; objective: string; updated_at: string; approval_required: boolean; external_actions_performed: boolean }
type JobPayload = { job_id: string; status: string; result?: Record<string, unknown> }
type Mode = 'consult' | 'council' | 'delegate'
type CouncilReply = { run_id: string; status: string; final_result?: { final_decision?: { decision?: string; next_action?: string } } | null }
type TranscriptionReply = { text: string; device: string }

const terminalCouncilStates = new Set(['completed', 'degraded', 'failed'])
const modeLabels: Record<Mode, string> = { consult: '相談', council: '会議', delegate: '任せる' }
const statusCopy: Record<string, string> = {
  queued: '開始待ち', researching: 'OSSを調査中', analysis_researching: '判断材料を収集中', analysis_proposing: '選択肢を作成中',
  analysis_criticizing: '見落としを確認中', analysis_judging: '経営判断を比較中', cloning: '採用OSSを準備中', implementing: '成果物を作成中',
  verifying: '結果を検証中', completed: '完了', degraded: '一部機能で完了', partial: '確認が必要', awaiting_approval: '承認待ち', failed: '安全停止',
}

function completionPercent(status?: string) {
  const progress: Record<string, number> = {
    queued: 5, researching: 15, analysis_researching: 25, analysis_proposing: 35, analysis_criticizing: 45,
    analysis_judging: 55, cloning: 65, implementing: 80, verifying: 92, awaiting_approval: 95,
    partial: 90, completed: 100, degraded: 100, failed: 0,
  }
  return status ? progress[status] ?? 10 : 0
}

function nextMove(progress: number) {
  if (progress === 0) return '達成したい状態を一文で入力する'
  if (progress < 55) return '選択肢とリスクを比べ、実行案を一つに絞る'
  if (progress < 80) return '選んだ方法を、実行できる仕事へ分解する'
  if (progress < 100) return '成果物と根拠を検証し、人間が承認する'
  return '結果を確認し、次の0→1目標を設定する'
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail ? String(payload.detail) : `HTTP ${response.status}`)
  return payload as T
}

export function CeoHome({ jobs, selectedJob, onDelegate }: {
  jobs: Job[]; selectedJob: JobPayload | null; onDelegate: (objective?: string) => void
}) {
  const [mode, setMode] = useState<Mode>('consult')
  const [prompt, setPrompt] = useState('')
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [voiceMessage, setVoiceMessage] = useState('')
  const [run, setRun] = useState<CouncilReply | null>(null)
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const current = jobs[0]
  const approvalCount = jobs.filter(item => item.approval_required || item.status === 'awaiting_approval').length
  const answer = run?.final_result?.final_decision
  const currentStatus = selectedJob?.status || current?.status
  const progress = completionPercent(currentStatus)
  const phase = progress < 25 ? 0 : progress < 55 ? 1 : progress < 92 ? 2 : 3

  useEffect(() => {
    if (!run?.run_id || terminalCouncilStates.has(run.status)) return
    const timer = window.setInterval(async () => {
      try {
        const latest = await requestJson<CouncilReply>(`/v1/council/runs/${run.run_id}`)
        setRun(latest)
        if (terminalCouncilStates.has(latest.status)) setAsking(false)
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : '回答を取得できませんでした')
        setAsking(false)
      }
    }, 1300)
    return () => window.clearInterval(timer)
  }, [run?.run_id, run?.status])

  useEffect(() => () => {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
    streamRef.current?.getTracks().forEach(track => track.stop())
  }, [])

  const transcribe = async (blob: Blob) => {
    setTranscribing(true); setVoiceMessage('文字にしています')
    try {
      const form = new FormData(); form.append('file', blob, 'guildless-voice.webm'); form.append('language', 'ja')
      const response = await fetch('/v1/audio/transcriptions', { method: 'POST', body: form })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`)
      const result = body as TranscriptionReply
      setPrompt(value => value.trim() ? `${value.trim()}\n${result.text}` : result.text)
      setVoiceMessage(`${result.device}で完了`); inputRef.current?.focus()
    } catch (reason) { setVoiceMessage(reason instanceof Error ? reason.message : '文字起こしに失敗しました') }
    finally { setTranscribing(false) }
  }

  const toggleVoice = async () => {
    if (recording) { recorderRef.current?.stop(); return }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') { setVoiceMessage('ChromeまたはEdgeで開いてください'); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 64_000 })
      streamRef.current = stream; recorderRef.current = recorder; chunksRef.current = []
      recorder.ondataavailable = event => { if (event.data.size) chunksRef.current.push(event.data) }
      recorder.onstop = () => {
        setRecording(false); stream.getTracks().forEach(track => track.stop())
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType }); chunksRef.current = []
        if (blob.size) void transcribe(blob)
      }
      recorder.start(250); setRecording(true); setVoiceMessage('録音中')
    } catch (reason) { setVoiceMessage(reason instanceof Error ? reason.message : 'マイクを開始できません') }
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault(); const question = prompt.trim(); if (!question) return
    if (mode === 'delegate') { onDelegate(question); return }
    setError(''); setAsking(true); setRun(null)
    try {
      setRun(await requestJson<CouncilReply>('/v1/council/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        task_type: 'general', mode: mode === 'council' ? 'fast' : 'local', question,
        context: { source: 'guildless_ceo_desk', interaction_mode: mode },
        allowed_providers: mode === 'council' ? ['deepseek', 'codex'] : ['deepseek'],
      }) }))
    } catch (reason) { setError(reason instanceof Error ? reason.message : '相談できませんでした'); setAsking(false) }
  }

  return <div className='grid h-[calc(100svh-8rem)] min-h-[620px] grid-rows-[1fr_auto] gap-3 overflow-hidden'>
    <section className='grid min-h-0 gap-3 md:grid-cols-[1.3fr_.7fr]'>
      <div className='flex min-h-0 flex-col rounded-[22px] border border-[#dedbd4] bg-white p-6'>
        <div className='flex items-start justify-between gap-4'><div><p className='text-[10px] font-semibold tracking-[.14em] text-[#817d76]'>0 → 1 MAP</p><h1 className='mt-1 text-2xl font-semibold tracking-[-.045em]'>頭の中を、実行できる形にする</h1></div><span className='rounded-full bg-[#edf5f1] px-3 py-1.5 text-xs font-medium text-[#276453]'>外部作用 0</span></div>

        <div className='mt-6 rounded-2xl bg-[#f5f3ef] p-5'>
          <div className='flex items-end justify-between gap-4'><div><p className='text-xs font-semibold text-[#817d76]'>完成を100%とした現在地</p><p className='mt-1 text-sm font-medium'>{statusCopy[currentStatus || ''] || '目標待ち'}</p></div><p className='text-5xl font-semibold tracking-[-.08em]'>{progress}<span className='ml-1 text-base text-[#817d76]'>%</span></p></div>
          <div className='mt-4 h-3 overflow-hidden rounded-full bg-white'><div className='h-full rounded-full bg-[#ff6b32] transition-[width] duration-500' style={{ width: `${progress}%` }} /></div>
          <div className='mt-5 grid grid-cols-4 gap-2'>{['目的', '判断', '実行', '検証'].map((label, index) => <div key={label} className={`rounded-xl border px-3 py-3 ${index === phase ? 'border-[#ff6b32] bg-white' : index < phase ? 'border-[#d7e5df] bg-[#edf5f1]' : 'border-transparent bg-white/60'}`}><div className='flex items-center gap-2'><span className={`grid size-6 place-items-center rounded-full text-[10px] font-semibold ${index <= phase ? 'bg-[#171513] text-white' : 'bg-[#e4e1da] text-[#817d76]'}`}>{index}</span><p className='text-xs font-semibold'>{label}</p></div><p className='mt-2 text-[10px] text-[#817d76]'>{progress === 100 || index < phase ? '完了' : index === phase ? '現在地' : '次へ'}</p></div>)}</div>
        </div>

        <div className='mt-4 grid min-h-0 flex-1 grid-cols-2 gap-3'>
          <div className='min-h-0 rounded-2xl border border-[#dedbd4] p-4'><p className='text-[10px] font-semibold text-[#817d76]'>目的</p><p className='mt-2 line-clamp-4 text-sm font-semibold leading-6'>{current?.objective || '達成したい状態を入力してください。'}</p></div>
          <div className='min-h-0 rounded-2xl border border-[#efc8b7] bg-[#fff6f1] p-4'><p className='text-[10px] font-semibold text-[#b94b1b]'>次の一手</p><p className='mt-2 text-sm font-semibold leading-6'>{nextMove(progress)}</p>{approvalCount > 0 && <p className='mt-2 text-[10px] text-[#b94b1b]'>人間の判断待ち {approvalCount}件</p>}</div>
        </div>
      </div>

      <div className='grid min-h-0 grid-rows-[1fr_auto] gap-3'>
        <section className='flex min-h-0 flex-col rounded-[22px] bg-[#171513] p-6 text-white'>
          <div className='flex items-start justify-between'><div><p className='text-[10px] font-semibold tracking-[.14em] text-white/45'>GUILDLESS NOW</p><h2 className='mt-2 text-lg font-semibold'>{asking ? '経営判断を作成中' : answer ? '回答ができました' : statusCopy[currentStatus || ''] || '待機中'}</h2></div><div className='grid size-16 place-items-center rounded-full border border-white/15 text-lg font-semibold'>{progress}%</div></div>
          {asking ? <div className='grid flex-1 place-items-center'><LoaderCircle className='size-6 animate-spin text-[#ff7a45]' /></div> : answer ? <><p className='mt-5 min-h-0 flex-1 overflow-hidden text-sm leading-6 text-white/75'>{answer.decision}</p>{answer.next_action && <div className='mt-3 rounded-xl bg-white/[.07] p-3'><p className='text-[10px] text-white/45'>次の一手</p><p className='mt-1 text-xs leading-5'>{answer.next_action}</p></div>}</> : <div className='mt-5'><p className='text-[10px] text-white/45'>いま扱っているテーマ</p><p className='mt-2 line-clamp-7 text-sm leading-6 text-white/70'>{current?.objective || '入力を待っています。'}</p></div>}
        </section>
        <section className='flex items-center gap-3 rounded-[18px] border border-[#cfe0d9] bg-[#edf5f1] px-4 py-3 text-[#276453]'><ShieldCheck className='size-5 shrink-0' /><div><p className='text-xs font-semibold'>安全に停止できる状態</p><p className='text-[10px]'>送信・契約・支払いは承認まで行いません</p></div></section>
      </div>
    </section>

    <form onSubmit={submit} className='rounded-[18px] border border-[#dedbd4] bg-white p-3 shadow-[0_10px_35px_rgba(44,35,29,.07)]'>
      <div className='flex items-center gap-2'>
        <div className='flex shrink-0 gap-1'>{(Object.keys(modeLabels) as Mode[]).map(item => <button key={item} type='button' onClick={() => setMode(item)} className={`rounded-full px-3 py-2 text-xs font-medium ${mode === item ? 'bg-[#171513] text-white' : 'text-[#77736d] hover:bg-[#f2f0ec]'}`}>{modeLabels[item]}</button>)}</div>
        <textarea ref={inputRef} value={prompt} onChange={event => setPrompt(event.target.value)} placeholder='会社について話す、または任せたい仕事を入力' aria-label='Guildlessへの相談内容' className='h-12 min-w-0 flex-1 resize-none border-0 bg-transparent px-3 py-3 text-sm outline-none placeholder:text-[#aaa69e]' />
        <button type='button' onClick={toggleVoice} disabled={transcribing} aria-label={recording ? '録音を止める' : '音声で話す'} className={`grid size-10 shrink-0 place-items-center rounded-xl border ${recording ? 'border-[#ff4801] bg-[#fff0e9] text-[#c43c00]' : 'border-[#dedbd4] bg-[#faf9f7] text-[#5f5b55]'}`}>{transcribing ? <LoaderCircle className='size-4 animate-spin' /> : recording ? <CircleStop className='size-4' /> : <Mic className='size-4' />}</button>
        <Button type='submit' disabled={!prompt.trim() || asking} className='h-10 shrink-0 rounded-xl bg-[#ff4801] px-4 text-white hover:bg-[#e54100]'>{asking ? <LoaderCircle className='size-4 animate-spin' /> : <Send className='size-4' />}{mode === 'delegate' ? '任せる' : '送る'}</Button>
      </div>
      {(error || voiceMessage) && <p className={`mt-1 px-2 text-[10px] ${error ? 'text-red-700' : 'text-[#817d76]'}`}>{error || voiceMessage}</p>}
    </form>
  </div>
}
