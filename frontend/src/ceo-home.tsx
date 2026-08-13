import { FormEvent, useEffect, useRef, useState } from 'react'
import { CircleStop, LoaderCircle, Mic, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'

type Job = { job_id: string; status: string; objective: string; updated_at: string; approval_required: boolean; external_actions_performed: boolean }
type JobPayload = { job_id: string; status: string; result?: Record<string, unknown> }
type CouncilReply = { run_id: string; status: string; final_result?: { final_decision?: { decision?: string; next_action?: string } } | null }
type TranscriptionReply = { text: string; device: string }

const terminalCouncilStates = new Set(['completed', 'degraded', 'failed'])
const statusCopy: Record<string, string> = {
  queued: '開始待ち', researching: '調査中', analysis_researching: '情報収集中', analysis_proposing: '選択肢を作成中',
  analysis_criticizing: '見落とし確認中', analysis_judging: '判断中', cloning: '準備中', implementing: '実行中',
  verifying: '検証中', completed: '完了', degraded: '一部完了', partial: '要確認', awaiting_approval: '承認待ち', failed: '停止',
}

function completionPercent(status?: string) {
  const progress: Record<string, number> = {
    queued: 5, researching: 15, analysis_researching: 25, analysis_proposing: 35, analysis_criticizing: 45,
    analysis_judging: 55, cloning: 65, implementing: 80, verifying: 92, awaiting_approval: 95,
    partial: 90, completed: 100, degraded: 100, failed: 0,
  }
  return status ? progress[status] ?? 10 : 0
}

function nextMove(progress: number, approvals: number) {
  if (approvals > 0) return '保留中の判断を確認する'
  if (progress === 0) return '今週達成したい状態を一文で決める'
  if (progress < 55) return '集めた情報から実行案を一つに絞る'
  if (progress < 80) return '決めた方針を担当と期限のある仕事へ分ける'
  if (progress < 100) return '成果物と根拠を確認して完了を判断する'
  return '結果を確認し、次の重点目標を決める'
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail ? String(payload.detail) : `HTTP ${response.status}`)
  return payload as T
}

export function CeoHome({ jobs, selectedJob }: { jobs: Job[]; selectedJob: JobPayload | null }) {
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
  const currentStatus = selectedJob?.status || current?.status
  const progress = completionPercent(currentStatus)
  const approvalCount = jobs.filter(item => item.approval_required || item.status === 'awaiting_approval').length
  const activeJobs = jobs.filter(item => !terminalCouncilStates.has(item.status) && !['partial', 'awaiting_approval'].includes(item.status)).slice(0, 3)
  const answer = run?.final_result?.final_decision

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
    setError(''); setAsking(true); setRun(null)
    try {
      setRun(await requestJson<CouncilReply>('/v1/council/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        task_type: 'general', mode: 'local', question, context: { source: 'guildless_company_overview' }, allowed_providers: ['deepseek'],
      }) }))
    } catch (reason) { setError(reason instanceof Error ? reason.message : '相談できませんでした'); setAsking(false) }
  }

  const indicators = [
    ['売上', '未接続'], ['利益', '未接続'], ['現金', '未接続'], ['商談', '0件'], ['要判断', `${approvalCount}件`],
  ]

  return <div className='grid h-[calc(100svh-8rem)] min-h-[620px] grid-rows-[auto_1fr_auto] gap-3 overflow-hidden'>
    <section className='grid grid-cols-5 overflow-hidden rounded-xl border border-[#dedbd4] bg-white'>
      {indicators.map(([label, value], index) => <div key={label} className={`px-4 py-3 ${index ? 'border-l border-[#ece9e3]' : ''}`}><p className='text-[10px] font-medium text-[#817d76]'>{label}</p><p className={`mt-1 text-base font-semibold ${value === '未接続' ? 'text-[#aaa69e]' : ''}`}>{value}</p></div>)}
    </section>

    <section className='grid min-h-0 gap-3 lg:grid-cols-[1.35fr_.65fr]'>
      <div className='grid min-h-0 grid-rows-[auto_1fr] overflow-hidden rounded-xl border border-[#dedbd4] bg-white'>
        <div className='border-b border-[#ece9e3] px-5 py-4'>
          <div className='flex items-center justify-between gap-4'><div><p className='text-xs font-medium text-[#817d76]'>今週の重点</p><h1 className='mt-1 line-clamp-2 text-xl font-semibold leading-7'>{current?.objective || '重点目標が設定されていません'}</h1></div><div className='shrink-0 text-right'><p className='text-sm font-semibold'>{progress}%</p><p className='text-[10px] text-[#817d76]'>{statusCopy[currentStatus || ''] || '未設定'}</p></div></div>
          <div className='mt-3 h-1.5 overflow-hidden rounded-full bg-[#ece9e3]'><div className='h-full rounded-full bg-[#4e6b5c]' style={{ width: `${progress}%` }} /></div>
        </div>

        <div className='grid min-h-0 grid-cols-2 grid-rows-2'>
          <BusinessCell label='目標' value={current?.objective || '今週達成したい状態を入力する'} />
          <BusinessCell label='現状' value={statusCopy[currentStatus || ''] || 'まだ開始していません'} borderLeft />
          <BusinessCell label='障害' value={approvalCount ? `人間の判断待ちが${approvalCount}件あります` : currentStatus === 'failed' ? '処理が停止しています' : '重大な障害は記録されていません'} borderTop />
          <BusinessCell label='次の一手' value={answer?.next_action || nextMove(progress, approvalCount)} borderLeft borderTop />
        </div>
      </div>

      <div className='grid min-h-0 grid-rows-[1fr_1fr] gap-3'>
        <section className='min-h-0 overflow-hidden rounded-xl border border-[#dedbd4] bg-white p-5'>
          <div className='flex items-center justify-between'><h2 className='text-sm font-semibold'>判断待ち</h2><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${approvalCount ? 'bg-[#fff1e9] text-[#a94712]' : 'bg-[#edf5f1] text-[#276453]'}`}>{approvalCount}件</span></div>
          {asking ? <div className='grid h-full place-items-center'><LoaderCircle className='size-5 animate-spin text-[#817d76]' /></div> : answer ? <div className='mt-4'><p className='line-clamp-5 text-sm leading-6'>{answer.decision}</p>{answer.next_action && <p className='mt-3 border-l-2 border-[#4e6b5c] pl-3 text-xs leading-5 text-[#6f6b64]'>{answer.next_action}</p>}</div> : approvalCount ? <p className='mt-4 line-clamp-5 text-sm leading-6'>{current?.objective}</p> : <p className='mt-4 text-sm text-[#817d76]'>現在、確認が必要な判断はありません。</p>}
        </section>

        <section className='min-h-0 overflow-hidden rounded-xl border border-[#dedbd4] bg-white p-5'>
          <div className='flex items-center justify-between'><h2 className='text-sm font-semibold'>進行中の仕事</h2><span className='text-[10px] text-[#817d76]'>{activeJobs.length}件</span></div>
          <div className='mt-3 divide-y divide-[#ece9e3]'>{activeJobs.length ? activeJobs.map(item => <div key={item.job_id} className='flex items-center gap-3 py-2.5'><span className='size-1.5 shrink-0 rounded-full bg-[#4e6b5c]' /><p className='min-w-0 flex-1 truncate text-xs'>{item.objective}</p><span className='shrink-0 text-[10px] text-[#817d76]'>{completionPercent(item.status)}%</span></div>) : <p className='py-2 text-sm text-[#817d76]'>進行中の仕事はありません。</p>}</div>
        </section>
      </div>
    </section>

    <form onSubmit={submit} className='rounded-xl border border-[#dedbd4] bg-white px-3 py-2'>
      <div className='flex items-center gap-2'><textarea ref={inputRef} value={prompt} onChange={event => setPrompt(event.target.value)} placeholder='経営上の迷いや、整理したいことを入力' aria-label='経営相談' className='h-11 min-w-0 flex-1 resize-none border-0 bg-transparent px-2 py-3 text-sm outline-none placeholder:text-[#aaa69e]' /><button type='button' onClick={toggleVoice} disabled={transcribing} aria-label={recording ? '録音を止める' : '音声で話す'} className={`grid size-9 shrink-0 place-items-center rounded-lg border transition-transform duration-150 active:scale-[.97] ${recording ? 'border-[#c66a3b] bg-[#fff1e9] text-[#a94712]' : 'border-[#dedbd4] text-[#6f6b64]'}`}>{transcribing ? <LoaderCircle className='size-4 animate-spin' /> : recording ? <CircleStop className='size-4' /> : <Mic className='size-4' />}</button><Button type='submit' disabled={!prompt.trim() || asking} className='h-9 shrink-0 rounded-lg bg-[#242421] px-4 text-white transition-transform duration-150 hover:bg-black active:scale-[.97]'>{asking ? <LoaderCircle className='size-4 animate-spin' /> : <Send className='size-4' />}相談する</Button></div>
      {(error || voiceMessage) && <p className={`px-2 pb-1 text-[10px] ${error ? 'text-red-700' : 'text-[#817d76]'}`}>{error || voiceMessage}</p>}
    </form>
  </div>
}

function BusinessCell({ label, value, borderLeft = false, borderTop = false }: { label: string; value: string; borderLeft?: boolean; borderTop?: boolean }) {
  return <div className={`min-h-0 p-5 ${borderLeft ? 'border-l border-[#ece9e3]' : ''} ${borderTop ? 'border-t border-[#ece9e3]' : ''}`}><p className='text-[10px] font-medium text-[#817d76]'>{label}</p><p className='mt-2 line-clamp-4 text-sm font-medium leading-6'>{value}</p></div>
}
