import { FormEvent, ReactNode, useEffect, useRef, useState } from 'react'
import { ArrowRight, CheckCircle2, CircleStop, Clock3, LoaderCircle, Mic, Send, ShieldCheck, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'

type Job = { job_id: string; status: string; objective: string; updated_at: string; approval_required: boolean; external_actions_performed: boolean }
type JobPayload = { job_id: string; status: string; result?: Record<string, unknown> }
type Mode = 'consult' | 'council' | 'delegate'
type CouncilReply = { run_id: string; status: string; final_result?: { final_decision?: { decision?: string; next_action?: string; confidence?: number } } | null }
type TranscriptionReply = { text: string; model: string; device: string; latency_seconds: number }

const terminalCouncilStates = new Set(['completed', 'degraded', 'failed'])
const modeLabels: Record<Mode, string> = { consult: '相談', council: '経営会議', delegate: '任せる' }
const currentCopy: Record<string, string> = {
  queued: '仕事を始める準備中', researching: '必要な情報とOSSを調査中', analysis_researching: '判断材料を収集中',
  analysis_proposing: '複数の選択肢を作成中', analysis_criticizing: '見落としを確認中', analysis_judging: '経営判断を比較中',
  cloning: '選んだ方法を準備中', implementing: '成果物を作成中', verifying: '結果を検証中', completed: '提案と成果物の準備が完了',
  degraded: '使える機能だけで完了', partial: '確認が必要な状態で停止', awaiting_approval: 'あなたの承認待ち', failed: '安全に停止',
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail ? String(payload.detail) : `HTTP ${response.status}`)
  return payload as T
}

export function CeoHome({ jobs, selectedJob, onOpenCouncil, onDelegate }: {
  jobs: Job[]; selectedJob: JobPayload | null; onOpenCouncil: () => void; onDelegate: (objective?: string) => void
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
  const activeCount = jobs.filter(item => !['completed', 'degraded', 'partial', 'awaiting_approval', 'failed'].includes(item.status)).length
  const approvalCount = jobs.filter(item => item.approval_required || item.status === 'awaiting_approval').length
  const completedCount = jobs.filter(item => item.status === 'completed').length
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
    setTranscribing(true)
    setVoiceMessage('端末内で文字にしています')
    try {
      const form = new FormData()
      form.append('file', blob, 'guildless-voice.webm')
      form.append('language', 'ja')
      const response = await fetch('/v1/audio/transcriptions', { method: 'POST', body: form })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`)
      const result = body as TranscriptionReply
      setPrompt(value => value.trim() ? `${value.trim()}\n${result.text}` : result.text)
      setVoiceMessage(`${result.device}で文字起こし完了`)
      inputRef.current?.focus()
    } catch (reason) {
      setVoiceMessage(reason instanceof Error ? reason.message : '文字起こしに失敗しました')
    } finally {
      setTranscribing(false)
    }
  }

  const toggleVoice = async () => {
    if (recording) {
      recorderRef.current?.stop()
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setVoiceMessage('ChromeまたはEdgeで開いてください')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 64_000 })
      streamRef.current = stream
      recorderRef.current = recorder
      chunksRef.current = []
      recorder.ondataavailable = event => { if (event.data.size) chunksRef.current.push(event.data) }
      recorder.onstop = () => {
        setRecording(false)
        stream.getTracks().forEach(track => track.stop())
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType })
        chunksRef.current = []
        if (blob.size) void transcribe(blob)
      }
      recorder.start(250)
      setRecording(true)
      setVoiceMessage('録音中。もう一度押すと停止します')
    } catch (reason) {
      setVoiceMessage(reason instanceof Error ? reason.message : 'マイクを開始できません')
    }
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const question = prompt.trim()
    if (!question) return
    if (mode === 'delegate') {
      onDelegate(question)
      return
    }
    setError('')
    setAsking(true)
    setRun(null)
    try {
      setRun(await requestJson<CouncilReply>('/v1/council/runs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
          task_type: 'general', mode: mode === 'council' ? 'fast' : 'local', question,
          context: { source: 'guildless_ceo_desk', interaction_mode: mode },
          allowed_providers: mode === 'council' ? ['deepseek', 'codex'] : ['deepseek'],
        }),
      }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '相談できませんでした')
      setAsking(false)
    }
  }

  return <div className='grid h-[calc(100svh-8rem)] min-h-[600px] gap-4 overflow-hidden xl:grid-cols-[1.35fr_.65fr]'>
    <section className='relative flex min-h-0 flex-col overflow-hidden rounded-[24px] border border-[#dedbd4] bg-[#f6f0e8] p-6 lg:p-8'>
      <img src='/ui-assets/guildless-company-map.png' alt='' className='absolute inset-0 h-full w-full object-cover object-center opacity-75' />
      <div className='absolute inset-0 bg-[linear-gradient(90deg,#f8f3ec_0%,rgba(248,243,236,.96)_46%,rgba(248,243,236,.25)_100%)]' />
      <div className='relative flex min-h-0 flex-1 flex-col'>
        <div><p className='text-[11px] font-semibold tracking-[.12em] text-[#817d76]'>経営デスク</p><h1 className='mt-2 text-[clamp(2rem,4vw,4rem)] font-semibold leading-[1.02] tracking-[-.06em] text-[#171513]'>何を決めますか？</h1><p className='mt-3 max-w-md text-sm leading-6 text-[#6f6b64]'>話すか書くだけ。整理、会議、仕事への変換はGuildlessが行います。</p></div>

        <form onSubmit={submit} className='mt-auto max-w-3xl rounded-[20px] border border-white/80 bg-white/95 p-3 shadow-[0_18px_55px_rgba(44,35,29,.1)] backdrop-blur'>
          <div className='flex gap-1 px-1 pb-2'>{(Object.keys(modeLabels) as Mode[]).map(item => <button key={item} type='button' onClick={() => setMode(item)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${mode === item ? 'bg-[#171513] text-white' : 'text-[#77736d] hover:bg-[#f2f0ec]'}`}>{modeLabels[item]}</button>)}</div>
          <textarea ref={inputRef} value={prompt} onChange={event => setPrompt(event.target.value)} placeholder='例：今月、売上を作るために何を優先する？' aria-label='Guildlessへの相談内容' className='h-24 w-full resize-none border-0 bg-transparent px-3 py-2 text-lg leading-7 outline-none placeholder:text-[#aaa69e]' />
          <div className='flex items-center justify-between gap-3 border-t border-[#ebe9e4] pt-3'>
            <button type='button' onClick={toggleVoice} disabled={transcribing} aria-label={recording ? '録音を止める' : '音声で話す'} className={`grid size-10 place-items-center rounded-xl border ${recording ? 'border-[#ff4801] bg-[#fff0e9] text-[#c43c00]' : 'border-[#dedbd4] bg-[#faf9f7] text-[#5f5b55]'}`}>{transcribing ? <LoaderCircle className='size-4 animate-spin' /> : recording ? <CircleStop className='size-4' /> : <Mic className='size-4' />}</button>
            {voiceMessage && <p className='min-w-0 flex-1 truncate text-xs text-[#817d76]'>{voiceMessage}</p>}
            <Button type='submit' disabled={!prompt.trim() || asking} className='h-11 rounded-xl bg-[#ff4801] px-5 text-white hover:bg-[#e54100]'>{asking ? <LoaderCircle className='size-4 animate-spin' /> : mode === 'delegate' ? <ArrowRight className='size-4' /> : <Send className='size-4' />}{asking ? '考えています' : mode === 'delegate' ? '任せる' : '聞く'}</Button>
          </div>
          {error && <p className='mt-2 px-2 text-xs text-red-700'>{error}</p>}
        </form>
      </div>
    </section>

    <aside className='flex min-h-0 flex-col gap-3'>
      <section className='rounded-[20px] border border-[#dedbd4] bg-white p-5'>
        <h2 className='text-sm font-semibold'>今日の経営</h2>
        <div className='mt-4 grid grid-cols-3 gap-2'>
          <MiniMetric icon={<Clock3 />} value={approvalCount} label='判断待ち' tone='orange' />
          <MiniMetric icon={<Sparkles />} value={activeCount} label='対応中' tone='violet' />
          <MiniMetric icon={<CheckCircle2 />} value={completedCount} label='完了' tone='green' />
        </div>
      </section>

      {(asking || answer) ? <section className='flex min-h-0 flex-1 flex-col rounded-[20px] bg-[#171513] p-5 text-white'>
        <p className='text-xs font-semibold text-[#ff9d75]'>GUILDLESSの回答</p>
        {asking ? <div className='grid flex-1 place-items-center'><LoaderCircle className='size-6 animate-spin text-[#ff7a45]' /></div> : <><p className='mt-4 min-h-0 flex-1 overflow-hidden text-sm leading-6 text-white/85'>{answer?.decision}</p>{answer?.next_action && <div className='mt-3 rounded-xl bg-white/[.07] p-3'><p className='text-[10px] text-white/45'>次の一手</p><p className='mt-1 text-sm'>{answer.next_action}</p></div>}<Button onClick={onOpenCouncil} variant='outline' className='mt-3 border-white/15 bg-white/5 text-white hover:bg-white/10 hover:text-white'>内訳を見る<ArrowRight className='size-4' /></Button></>}
      </section> : <section className='flex min-h-0 flex-1 flex-col justify-between rounded-[20px] border border-[#dedbd4] bg-white p-5'>
        <div><p className='text-[10px] font-semibold tracking-[.12em] text-[#817d76]'>いまの状況</p><h2 className='mt-2 text-lg font-semibold'>{current ? currentCopy[selectedJob?.status || current.status] || '処理中' : '待機中'}</h2><p className='mt-2 line-clamp-3 text-sm leading-6 text-[#77736d]'>{current?.objective || '相談か仕事を入力してください。'}</p></div>
      </section>}

      <section className='flex items-center gap-3 rounded-[18px] border border-[#cfe0d9] bg-[#edf5f1] px-4 py-3 text-[#276453]'><ShieldCheck className='size-5 shrink-0' /><div><p className='text-xs font-semibold'>外部作用 0</p><p className='text-[10px]'>送信・契約・支払いは承認まで停止</p></div></section>
    </aside>
  </div>
}

function MiniMetric({ icon, value, label, tone }: { icon: ReactNode; value: number; label: string; tone: 'orange' | 'violet' | 'green' }) {
  const colors = { orange: 'bg-[#f7eee8] text-[#a94712]', violet: 'bg-[#eeeeF7] text-[#4d4b87]', green: 'bg-[#eaf3ef] text-[#276453]' }
  return <div className='rounded-xl bg-[#faf9f7] p-3'><span className={`grid size-7 place-items-center rounded-lg [&>svg]:size-3.5 ${colors[tone]}`}>{icon}</span><p className='mt-2 text-2xl font-semibold tracking-[-.05em]'>{value}</p><p className='text-[10px] text-[#77736d]'>{label}</p></div>
}
