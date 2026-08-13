import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight,
  CheckCircle2,
  CircleStop,
  Clock3,
  LoaderCircle,
  Mic,
  Send,
  ShieldCheck,
  Sparkles,
  Volume2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { HomeTaskSuggestions, type GuildlessPromptMode } from '@/cloudflare-os/home-task-suggestions'

type Job = {
  job_id: string
  status: string
  objective: string
  updated_at: string
  approval_required: boolean
  external_actions_performed: boolean
}

type JobPayload = {
  job_id: string
  status: string
  result?: Record<string, unknown>
}

type CouncilReply = {
  run_id: string
  status: string
  final_result?: {
    final_decision?: {
      decision?: string
      next_action?: string
      confidence?: number
      risks?: string[]
    }
  } | null
  error?: unknown
}

type TranscriptionReply = {
  text: string
  language: string
  model: string
  device: string
  latency_seconds: number
  local_only: boolean
}

const terminalCouncilStates = new Set(['completed', 'degraded', 'failed'])

const modeLabels: Record<GuildlessPromptMode, string> = {
  consult: '壁打ち',
  organize: '整理',
  council: '経営会議',
  delegate: '任せる',
}

const operationCopy: Record<string, { title: string; step: number; detail: string }> = {
  queued: { title: '仕事を受け付けました', step: 0, detail: '始める準備をしています。' },
  researching: { title: '必要な情報と使えるOSSを調べています', step: 0, detail: '候補の更新状況やライセンスまで確認しています。' },
  analysis_researching: { title: '判断に必要な情報を集めています', step: 0, detail: '与えられた条件の中から根拠を整理しています。' },
  analysis_proposing: { title: '複数の選択肢を作っています', step: 1, detail: 'ひとつの案に早く寄りすぎないよう、別々に考えています。' },
  analysis_criticizing: { title: '見落としと反対意見を確認しています', step: 1, detail: '実行前に弱点と失敗条件を洗い出しています。' },
  analysis_judging: { title: '経営判断として比較しています', step: 1, detail: '効果・費用・速さ・リスクを同じ基準で比べています。' },
  analysis_completed: { title: '進め方が決まりました', step: 2, detail: '次の作業へ移れる状態です。' },
  analysis_degraded: { title: '使えるモデルだけで判断を続けています', step: 1, detail: '利用できないモデルを外し、残りの視点で継続しています。' },
  cloning: { title: '選んだ方法で試作品の準備をしています', step: 2, detail: '固定した版を安全な作業場所へ取り込んでいます。' },
  implementing: { title: '成果物を作っています', step: 2, detail: '外部へ送信せず、隔離された場所だけで作業しています。' },
  verifying: { title: '結果が本物か確認しています', step: 2, detail: 'ファイルの存在、テスト、安全条件を確かめています。' },
  completed: { title: '提案と成果物の準備ができました', step: 3, detail: '結果を確認できます。自動で外部へは出していません。' },
  degraded: { title: '一部の機能を使わずに完了しました', step: 3, detail: '不足した部分を明示して結果を残しています。' },
  partial: { title: '確認が必要な状態で止めています', step: 3, detail: 'できた部分と不足を分けて報告しています。' },
  awaiting_approval: { title: 'あなたの承認を待っています', step: 3, detail: '承認前のため外部作用は発生していません。' },
  failed: { title: '処理を安全に停止しました', step: 3, detail: '原因と次に試せる方法を記録しています。' },
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail ? JSON.stringify(payload.detail) : `HTTP ${response.status}`)
  return payload as T
}

function formatDate(value?: string) {
  return value
    ? new Intl.DateTimeFormat('ja-JP', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
    : '—'
}

export function CeoHome({
  jobs,
  selectedJob,
  onOpenOperations,
  onOpenCouncil,
  onDelegate,
}: {
  jobs: Job[]
  selectedJob: JobPayload | null
  onOpenOperations: () => void
  onOpenCouncil: () => void
  onDelegate: (objective?: string) => void
}) {
  const [mode, setMode] = useState<GuildlessPromptMode>('consult')
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
  const voiceChunksRef = useRef<Blob[]>([])
  const voiceTimerRef = useRef<number | null>(null)

  const current = jobs[0]
  const currentCopy = operationCopy[selectedJob?.status || current?.status || 'queued'] || operationCopy.queued
  const activeCount = jobs.filter(item => !['completed', 'degraded', 'partial', 'awaiting_approval', 'failed'].includes(item.status)).length
  const approvalCount = jobs.filter(item => item.approval_required || item.status === 'awaiting_approval').length
  const completedCount = jobs.filter(item => item.status === 'completed').length

  const answer = run?.final_result?.final_decision

  const summaryCards = useMemo(() => [
    { label: 'あなたの判断待ち', value: approvalCount, note: approvalCount ? '確認が必要です' : 'いまはありません', icon: Clock3, tone: approvalCount ? 'text-[#a94712] bg-[#f6eee7]' : 'text-[#276453] bg-[#e8f1ee]' },
    { label: 'Guildlessが対応中', value: activeCount, note: activeCount ? '裏側で進行中' : '待機しています', icon: Sparkles, tone: 'text-[#4d4b87] bg-[#ececf5]' },
    { label: '完了した仕事', value: completedCount, note: '結果を確認できます', icon: CheckCircle2, tone: 'text-[#276453] bg-[#e8f1ee]' },
  ], [activeCount, approvalCount, completedCount])

  useEffect(() => {
    if (!run?.run_id || terminalCouncilStates.has(run.status)) return
    const timer = window.setInterval(async () => {
      try {
        const latest = await requestJson<CouncilReply>(`/v1/council/runs/${run.run_id}`)
        setRun(latest)
        if (terminalCouncilStates.has(latest.status)) setAsking(false)
      } catch (pollError) {
        setError(pollError instanceof Error ? pollError.message : '回答の取得に失敗しました')
        setAsking(false)
      }
    }, 1300)
    return () => window.clearInterval(timer)
  }, [run?.run_id, run?.status])

  useEffect(() => () => {
    if (voiceTimerRef.current !== null) window.clearTimeout(voiceTimerRef.current)
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
    streamRef.current?.getTracks().forEach(track => track.stop())
  }, [])

  const selectSuggestion = (suggestion: { id: GuildlessPromptMode; prompt: string }) => {
    setMode(suggestion.id)
    setPrompt(suggestion.prompt)
    window.setTimeout(() => inputRef.current?.focus(), 50)
  }

  const transcribeRecording = async (blob: Blob) => {
    setTranscribing(true)
    setVoiceMessage('ローカルWhisperで文字にしています…')
    try {
      const form = new FormData()
      form.append('file', blob, 'guildless-voice.webm')
      form.append('language', 'ja')
      const response = await fetch('/v1/audio/transcriptions', { method: 'POST', body: form })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`)
      const transcription = payload as TranscriptionReply
      setPrompt(current => current.trim() ? `${current.trim()}\n${transcription.text}` : transcription.text)
      setVoiceMessage(`端末内で文字起こし完了（${transcription.model} / ${transcription.device} / ${transcription.latency_seconds}秒）`)
      window.setTimeout(() => inputRef.current?.focus(), 50)
    } catch (voiceError) {
      setVoiceMessage(voiceError instanceof Error ? `文字起こし失敗：${voiceError.message}` : '文字起こしに失敗しました')
    } finally {
      setTranscribing(false)
    }
  }

  const stopRecording = () => {
    if (voiceTimerRef.current !== null) {
      window.clearTimeout(voiceTimerRef.current)
      voiceTimerRef.current = null
    }
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
  }

  const toggleVoice = async () => {
    if (recording) {
      stopRecording()
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setVoiceMessage('このブラウザではマイク録音を開始できません。ChromeまたはEdgeで開いてください。')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 64_000 })
      streamRef.current = stream
      recorderRef.current = recorder
      voiceChunksRef.current = []
      recorder.ondataavailable = event => {
        if (event.data.size > 0) voiceChunksRef.current.push(event.data)
      }
      recorder.onerror = () => {
        setRecording(false)
        setVoiceMessage('録音に失敗しました。マイクの許可を確認してください。')
        stream.getTracks().forEach(track => track.stop())
      }
      recorder.onstop = () => {
        setRecording(false)
        stream.getTracks().forEach(track => track.stop())
        streamRef.current = null
        const blob = new Blob(voiceChunksRef.current, { type: recorder.mimeType })
        voiceChunksRef.current = []
        if (blob.size > 0) void transcribeRecording(blob)
        else setVoiceMessage('音声が録音されませんでした。')
      }
      recorder.start(250)
      setRecording(true)
      setVoiceMessage('録音中です。もう一度押すと停止して、端末内で文字にします。')
      voiceTimerRef.current = window.setTimeout(stopRecording, 60_000)
    } catch (microphoneError) {
      setRecording(false)
      setVoiceMessage(microphoneError instanceof Error ? `マイクを開始できません：${microphoneError.message}` : 'マイクを開始できません')
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
      const providers = mode === 'council' ? ['deepseek', 'codex'] : ['deepseek']
      const accepted = await requestJson<CouncilReply>('/v1/council/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_type: 'general',
          mode: mode === 'council' ? 'fast' : 'local',
          question,
          context: { source: 'guildless_ceo_desk', interaction_mode: mode },
          allowed_providers: providers,
        }),
      })
      setRun(accepted)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Guildlessへ相談できませんでした')
      setAsking(false)
    }
  }

  return (
    <div className='space-y-8 pb-12'>
      <section aria-labelledby='today-management-title'>
        <div className='mb-3 flex items-end justify-between gap-4'>
          <div>
            <p className='text-[11px] font-semibold uppercase tracking-[.12em] text-[#817d76]'>TODAY</p>
            <h1 id='today-management-title' className='mt-1 text-xl font-semibold tracking-[-.025em] text-[#171513]'>今日の経営</h1>
          </div>
          <button type='button' onClick={onOpenOperations} className='text-xs font-medium text-[#67635d] underline-offset-4 hover:text-[#171513] hover:underline'>すべての仕事を見る</button>
        </div>
        <div className='grid gap-3 sm:grid-cols-3'>
          {summaryCards.map(card => <div key={card.label} className='flex min-h-28 items-center gap-4 rounded-[18px] border border-[#dedbd4] bg-white px-5 py-4 shadow-[0_1px_0_rgba(20,17,15,.02)]'>
            <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${card.tone}`}><card.icon className='size-[18px]' /></span>
            <div className='min-w-0'><p className='text-3xl font-semibold tracking-[-.055em] text-[#211f1c]'>{card.value}</p><p className='mt-0.5 text-sm font-medium text-[#3b3833]'>{card.label}</p><p className='mt-1 text-xs text-[#8b877f]'>{card.note}</p></div>
          </div>)}
        </div>
      </section>

      <section className='relative overflow-hidden rounded-[28px] border border-[#dedbd4] bg-[#f6f0e8] shadow-[0_1px_0_rgba(20,17,15,.03)]'>
        <img src='/ui-assets/guildless-company-map.png' alt='' className='absolute inset-0 h-full w-full object-cover object-center opacity-95' />
        <div className='absolute inset-0 bg-[linear-gradient(90deg,#f8f3ec_0%,#f8f3ec_35%,rgba(248,243,236,.82)_53%,rgba(248,243,236,.06)_78%)]' />
        <div className='relative max-w-2xl px-6 py-10 sm:px-10 sm:py-14 lg:py-16'>
          <p className='mb-4 inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/70 px-3 py-1.5 text-[11px] font-semibold tracking-[.08em] text-[#615e58] backdrop-blur'>
            <span className='size-1.5 rounded-full bg-[#ff4801]' />経営デスク
          </p>
          <h1 className='max-w-xl text-[clamp(2rem,4vw,3.75rem)] font-semibold leading-[1.02] tracking-[-.055em] text-[#171513]'>
            今日は、何を<br className='hidden sm:block' />決めますか？
          </h1>
          <p className='mt-5 max-w-md text-sm leading-6 text-[#6f6b64]'>話すだけでも、書くだけでも大丈夫です。Guildlessが状況を整理し、必要なら複数の知能を集めます。</p>
        </div>
      </section>

      <form onSubmit={submit} className='rounded-[24px] border border-[#d9d6cf] bg-white p-3 shadow-[0_18px_55px_rgba(44,35,29,.08)] sm:p-4'>
        <div className='flex flex-wrap gap-1.5 px-1 pb-3'>
          {(Object.keys(modeLabels) as GuildlessPromptMode[]).map(item => (
            <button key={item} type='button' onClick={() => setMode(item)} className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${mode === item ? 'bg-[#171513] text-white' : 'text-[#77736d] hover:bg-[#f2f0ec]'}`}>{modeLabels[item]}</button>
          ))}
        </div>
        <textarea
          ref={inputRef}
          value={prompt}
          onChange={event => setPrompt(event.target.value)}
          placeholder='例：営業DMから商談までの流れを、いまあるOSSでどう作る？'
          className='min-h-28 w-full resize-none border-0 bg-transparent px-3 py-2 text-base leading-7 text-[#211f1c] outline-none placeholder:text-[#aaa69e] sm:text-lg'
          aria-label='Guildlessへの相談内容'
        />
        <div className='flex flex-col gap-3 border-t border-[#ebe9e4] px-1 pt-3 sm:flex-row sm:items-center sm:justify-between'>
          <div className='flex min-w-0 items-center gap-2'>
            <button type='button' onClick={toggleVoice} disabled={transcribing} aria-pressed={recording} className={`inline-flex h-10 items-center gap-2 rounded-xl border px-3 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ff4801]/40 disabled:cursor-wait disabled:opacity-65 ${recording ? 'border-[#ff4801] bg-[#fff0e9] text-[#c43c00]' : 'border-[#dedbd4] bg-[#faf9f7] text-[#5f5b55] hover:bg-[#f2f0ec]'}`}>
              {transcribing ? <LoaderCircle className='size-4 animate-spin' /> : recording ? <CircleStop className='size-4' /> : <Mic className='size-4' />}
              {transcribing ? '端末内で文字起こし中' : recording ? '録音を止める' : '音声で話す'}
            </button>
            {voiceMessage && <span className='truncate text-xs text-[#817d76]'>{voiceMessage}</span>}
          </div>
          <Button type='submit' disabled={!prompt.trim() || asking} className='h-11 rounded-xl bg-[#ff4801] px-5 text-white shadow-[0_6px_16px_rgba(255,72,1,.22)] hover:bg-[#e54100]'>
            {asking ? <LoaderCircle className='size-4 animate-spin' /> : mode === 'delegate' ? <ArrowRight className='size-4' /> : <Send className='size-4' />}
            {asking ? '考えています' : mode === 'delegate' ? '仕事として任せる' : 'Guildlessに聞く'}
          </Button>
        </div>
        {error && <p className='mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700'>{error}</p>}
      </form>

      {(asking || answer || run?.status === 'failed') && (
        <section aria-live='polite' className='rounded-[24px] border border-[#dedbd4] bg-[#171513] p-5 text-white sm:p-7'>
          <div className='flex items-center gap-3'>
            <span className='grid size-9 place-items-center rounded-full bg-white/10'><Volume2 className='size-4' /></span>
            <div><p className='text-sm font-semibold'>Guildless</p><p className='text-xs text-white/55'>{asking ? '複数の視点を整理中' : '回答'}</p></div>
          </div>
          {asking && <div className='mt-5 flex items-center gap-3 text-sm text-white/70'><LoaderCircle className='size-4 animate-spin text-[#ff7a45]' />情報を集め、選択肢を比べています。ここで待つ必要はありません。</div>}
          {answer && <div className='mt-5 max-w-3xl'><p className='whitespace-pre-wrap text-base leading-7 text-white/90'>{answer.decision}</p>{answer.next_action && <div className='mt-5 rounded-xl bg-white/7 p-4'><p className='text-[11px] font-semibold uppercase tracking-[.12em] text-[#ff9d75]'>次の一手</p><p className='mt-2 text-sm leading-6 text-white/85'>{answer.next_action}</p></div>}<div className='mt-5 flex items-center gap-3'><Button type='button' onClick={onOpenCouncil} variant='outline' className='border-white/20 bg-white/5 text-white hover:bg-white/10 hover:text-white'>判断の内訳を見る<ArrowRight className='size-4' /></Button>{typeof answer.confidence === 'number' && <span className='text-xs text-white/50'>確信度 {Math.round(answer.confidence * 100)}%</span>}</div></div>}
          {run?.status === 'failed' && <p className='mt-5 text-sm text-red-200'>回答を作れませんでした。設定またはモデルの状態を確認してください。</p>}
        </section>
      )}

      <HomeTaskSuggestions onPick={selectSuggestion} />

      <section className='grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,.65fr)]'>
        <div className='rounded-[22px] border border-[#dedbd4] bg-white p-5 sm:p-6'>
          <div className='flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between'>
            <div>
              <p className='text-[11px] font-semibold uppercase tracking-[.12em] text-[#817d76]'>Guildlessはいま何をしている？</p>
              <h2 className='mt-2 text-xl font-semibold tracking-[-.025em] text-[#171513]'>{current ? currentCopy.title : 'いまは待機しています'}</h2>
              <p className='mt-2 max-w-xl text-sm leading-6 text-[#77736d]'>{current ? currentCopy.detail : '相談、調査、経営会議、仕事の依頼をここから始められます。'}</p>
              {current && <p className='mt-3 text-xs text-[#99958e]'>最終更新 {formatDate(current.updated_at)}</p>}
            </div>
            {current && <Button type='button' variant='outline' onClick={onOpenOperations} className='shrink-0 rounded-xl'>詳しく見る<ArrowRight className='size-4' /></Button>}
          </div>
          <div className='mt-6 grid grid-cols-3 gap-2'>
            {['情報を集める', '選択肢を比べる', '提案をまとめる'].map((label, index) => {
              const active = currentCopy.step === index
              const done = currentCopy.step > index
              return <div key={label} className={`rounded-xl border px-3 py-3 ${active ? 'border-[#ffb08f] bg-[#fff3ed]' : done ? 'border-[#c9ded5] bg-[#eef6f2]' : 'border-[#e5e2dc] bg-[#faf9f7]'}`}><div className='mb-2 flex items-center gap-2'>{done ? <CheckCircle2 className='size-3.5 text-[#33705b]' /> : <span className={`size-2 rounded-full ${active ? 'bg-[#ff4801]' : 'bg-[#c7c3bc]'}`} />}<span className='text-[10px] font-semibold text-[#8b877f]'>{index + 1}</span></div><p className='text-xs font-medium text-[#3b3833]'>{label}</p></div>
            })}
          </div>
        </div>

        <div className='rounded-[22px] border border-[#dedbd4] bg-[#f0eee9] p-5 sm:p-6'>
          <div className='flex items-center gap-2 text-[#276453]'><ShieldCheck className='size-5' /><p className='text-sm font-semibold'>安全に停止できています</p></div>
          <p className='mt-3 text-sm leading-6 text-[#6f6b64]'>承認なしの外部送信・契約・支払いは行いません。現在確認された外部作用は 0 件です。</p>
          <div className='mt-5 rounded-xl border border-[#dedbd4] bg-white/70 p-4'><p className='text-xs font-medium text-[#3b3833]'>現在の運転モード</p><div className='mt-2 flex items-center gap-2 text-sm text-[#276453]'><span className='size-2 rounded-full bg-emerald-500' />Shadow Mode・承認待ちで停止</div></div>
        </div>
      </section>
    </div>
  )
}
