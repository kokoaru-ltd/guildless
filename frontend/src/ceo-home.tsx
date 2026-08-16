import { FormEvent, ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CircleStop, FlaskConical, LoaderCircle, Mic, Radio } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { executiveJapaneseText } from '@/lib/executive-copy'
import {
  daysLeft, funnel, isRehearsal, money, nextMoveByGuildless,
  ownerActions, stagePlain, verdictPlain, yen,
  type OwnerAction, type V0Loop,
} from '@/lib/owner-view'

type Job = { job_id: string; status: string; objective: string; approval_required: boolean }
type JobPayload = { job_id: string; status: string }
type CouncilReply = {
  run_id: string
  status: string
  final_result?: { final_decision?: { decision?: string; next_action?: string } } | null
  error?: { error?: string; provider_unavailable?: Array<{ provider?: string; message?: string }> } | null
}
type TranscriptionReply = { text: string; device: string }

const terminalCouncilStates = new Set(['completed', 'degraded', 'failed'])

/**
 * Real multi-model council: two different hosted models argue, a third judges.
 * Every name here must be reachable without a local runtime, otherwise the
 * council silently degrades to a single voice.
 */
const COUNCIL_MODE = 'real'
const COUNCIL_PROVIDERS = ['sakana', 'deepseek_api', 'glm', 'codex']

/** What the council is doing right now, said plainly. It takes minutes. */
const COUNCIL_PROGRESS: Record<string, string> = {
  queued: '順番待ちです',
  researching: '材料を集めています',
  proposing: '2つのAIがそれぞれ案を作っています',
  criticizing: 'お互いの案に反論させています',
  judging: '3つ目のAIがどちらが正しいか判定しています',
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail ? String(payload.detail) : `HTTP ${response.status}`)
  return payload as T
}

export function CeoHome({ jobs }: { jobs: Job[]; selectedJob?: JobPayload | null }) {
  const [loop, setLoop] = useState<V0Loop | null>(null)
  const [acting, setActing] = useState('')
  const [error, setError] = useState('')

  const loadLoop = useCallback(async () => {
    try {
      const payload = await requestJson<{ exists: boolean; loop: V0Loop | null }>('/v1/v0/overview')
      setLoop(payload.exists ? payload.loop : null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '状況を読み込めませんでした')
    }
  }, [])

  useEffect(() => {
    void loadLoop()
    const timer = window.setInterval(() => void loadLoop(), 4000)
    return () => window.clearInterval(timer)
  }, [loadLoop])

  const runAction = async (action: OwnerAction) => {
    if (!loop) return
    setActing(action.id); setError('')
    try {
      await requestJson(action.endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ loop_id: loop.loop_id }),
      })
      await loadLoop()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '実行できませんでした')
    } finally { setActing('') }
  }

  const cash = money(loop)
  const reach = funnel(loop)
  const remainingDays = daysLeft(loop)
  const actions = ownerActions(loop)
  const verdict = verdictPlain(loop)
  const rehearsal = isRehearsal(loop)
  const pendingJobs = jobs.filter(item => item.approval_required || item.status === 'awaiting_approval').length

  return <div className='h-full space-y-3 overflow-y-auto pb-2 pr-1'>
    <ModeBanner rehearsal={rehearsal} contacts={reach.contacts} />

    <section className='grid grid-cols-2 overflow-hidden rounded-xl border border-[#dedbd4] bg-white lg:grid-cols-4'>
      <MoneyTile label='使えるお金' value={yen(cash.remaining)} note={`予算${yen(cash.budget)}のうち`} />
      <MoneyTile label='使ったお金' value={yen(cash.spent)} note='広告・ツールの実費' divided />
      <MoneyTile label='入ったお金' value={yen(cash.earned)} note={cash.earned ? '入金済み' : 'まだ入金はありません'} divided muted={!cash.earned} />
      <MoneyTile
        label='残り日数'
        value={remainingDays === null ? '—' : `${remainingDays}日`}
        note={remainingDays === null ? '期限は未設定' : remainingDays === 0 ? '今日が期限です' : '自分で決めた期限まで'}
        alert={remainingDays !== null && remainingDays <= 2}
        divided
      />
    </section>

    <section className='grid items-start gap-3 lg:grid-cols-[1fr_.72fr]'>
      <div className='flex flex-col gap-3'>
        <div className='rounded-xl border border-[#dedbd4] bg-white p-5'>
          <div className='flex items-baseline justify-between gap-4'>
            <h2 className='text-sm font-semibold'>いま決めること</h2>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${actions.length ? 'bg-[#fff1e9] text-[#a94712]' : 'bg-[#edf5f1] text-[#276453]'}`}>
              {actions.length ? `${actions.length}件` : 'なし'}
            </span>
          </div>

          {actions.length ? <div className='mt-4 space-y-3'>
            {actions.map(action => <div key={action.id} className='rounded-lg border border-[#efc8b7] bg-[#fffaf7] p-4'>
              <p className='text-base font-semibold leading-6'>{action.title}</p>
              <p className='mt-2 text-xs leading-5 text-[#6f6b64]'>{action.detail}</p>
              <Button
                onClick={() => void runAction(action)}
                disabled={Boolean(acting)}
                className='mt-4 h-11 rounded-lg bg-[#ff4801] px-6 text-sm text-white hover:bg-[#e04400]'
              >
                {acting === action.id ? <LoaderCircle className='size-4 animate-spin' /> : null}
                {action.confirmLabel}
              </Button>
            </div>)}
          </div> : <div className='mt-4 rounded-lg bg-[#f7f7f5] p-4'>
            <p className='text-sm leading-6'>あなたが決めることはいまありません。</p>
            <p className='mt-1 text-xs leading-5 text-[#817d76]'>{nextMoveByGuildless(loop)}</p>
          </div>}

          {pendingJobs > 0 && <p className='mt-3 text-[11px] text-[#a94712]'>
            このほかに「実行」画面で承認待ちの仕事が{pendingJobs}件あります。
          </p>}
        </div>

        <div className='rounded-xl border border-[#dedbd4] bg-white p-5'>
          <h2 className='text-sm font-semibold'>何が起きたか</h2>
          <div className='mt-4 grid grid-cols-4 gap-2'>
            <FunnelStep label='声をかけた' value={reach.contacts} unit='社' />
            <FunnelStep label='返事が来た' value={reach.replied} unit='件' />
            <FunnelStep label='興味あり' value={reach.interested} unit='件' />
            <FunnelStep label='買った' value={reach.orders} unit='件' emphasis />
          </div>
          {loop?.selected_business?.name && <p className='mt-4 border-t border-[#ece9e3] pt-3 text-xs leading-5 text-[#6f6b64]'>
            売っているもの：<span className='font-semibold text-[#20201e]'>{loop.selected_business.name}</span>
            {loop.selected_business.price_yen ? `（${yen(loop.selected_business.price_yen)}）` : ''}
          </p>}
        </div>
      </div>

      <div className='flex flex-col gap-3'>
        <div className='rounded-xl border border-[#dedbd4] bg-white p-5'>
          <h2 className='text-sm font-semibold'>いまの狙い</h2>
          <p className='mt-3 text-sm font-medium leading-6'>
            {executiveJapaneseText(loop?.goal?.intermediate_goal, executiveJapaneseText(loop?.intent, '目標がまだ設定されていません'))}
          </p>
          <p className='mt-3 border-t border-[#ece9e3] pt-3 text-xs leading-5 text-[#817d76]'>
            最終的に目指すこと：{executiveJapaneseText(loop?.goal?.final_goal, '未設定')}
          </p>
          <p className='mt-2 text-xs leading-5 text-[#817d76]'>いまの作業：{stagePlain(loop)}</p>
        </div>

        {verdict && <div className='rounded-xl border border-[#dedbd4] bg-white p-5'>
          <h2 className='text-sm font-semibold'>前回の結論</h2>
          <p className='mt-3 text-lg font-semibold'>{verdict.label}</p>
          <p className='mt-2 text-xs leading-5 text-[#6f6b64]'>{verdict.detail}</p>
        </div>}

        <ConsultPanel />
      </div>
    </section>

    {error && <p className='rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-xs text-red-700'>{error}</p>}
  </div>
}

function ModeBanner({ rehearsal, contacts }: { rehearsal: boolean; contacts: number }) {
  if (!rehearsal) {
    return <div className='flex items-center gap-3 rounded-xl border border-[#c3ddcf] bg-[#edf5f1] px-4 py-3'>
      <Radio className='size-4 shrink-0 text-[#276453]' />
      <p className='text-xs font-semibold text-[#276453]'>本番稼働中：実際のお客さんに連絡しています。</p>
    </div>
  }
  return <div className='flex items-center gap-3 rounded-xl border border-[#e4cfa6] bg-[#fdf6e7] px-4 py-3'>
    <FlaskConical className='size-4 shrink-0 text-[#8a6410]' />
    <p className='text-xs font-semibold text-[#8a6410]'>
      お試し運転中：まだ誰にも連絡していません。
      {contacts > 0 && `下の「${contacts.toLocaleString('ja-JP')}社」はコンピューター上の予測です。`}
    </p>
  </div>
}

function MoneyTile({ label, value, note, divided = false, muted = false, alert = false }: {
  label: string; value: string; note: string; divided?: boolean; muted?: boolean; alert?: boolean
}) {
  return <div className={`px-5 py-4 ${divided ? 'border-l border-[#ece9e3]' : ''} ${alert ? 'bg-[#fffaf7]' : ''}`}>
    <p className='flex items-center gap-1 text-[11px] font-medium text-[#817d76]'>
      {alert && <AlertTriangle className='size-3 text-[#a94712]' />}{label}
    </p>
    <p className={`mt-1 text-2xl font-semibold tabular-nums ${muted ? 'text-[#aaa69e]' : alert ? 'text-[#a94712]' : ''}`}>{value}</p>
    <p className='mt-1 text-[10px] text-[#99958d]'>{note}</p>
  </div>
}

function FunnelStep({ label, value, unit, emphasis = false }: { label: string; value: number; unit: string; emphasis?: boolean }) {
  return <div className={`rounded-lg p-3 ${emphasis ? 'bg-[#fff1e9]' : 'bg-[#f7f7f5]'}`}>
    <p className='text-[10px] font-medium text-[#817d76]'>{label}</p>
    <p className={`mt-1 text-xl font-semibold tabular-nums ${emphasis && value > 0 ? 'text-[#a94712]' : emphasis ? 'text-[#aaa69e]' : ''}`}>
      {value.toLocaleString('ja-JP')}<span className='ml-0.5 text-[11px] font-medium text-[#817d76]'>{unit}</span>
    </p>
  </div>
}

function ConsultPanel(): ReactNode {
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
    }, 3000)
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
        task_type: 'general', mode: COUNCIL_MODE, question,
        context: { source: 'guildless_owner_home' }, allowed_providers: COUNCIL_PROVIDERS,
      }) }))
    } catch (reason) { setError(reason instanceof Error ? reason.message : '相談できませんでした'); setAsking(false) }
  }

  const failed = run?.status === 'failed'
  const blockedProviders = run?.error?.provider_unavailable?.map(item => item.provider).filter(Boolean) || []

  return <form onSubmit={submit} className='flex flex-col rounded-xl border border-[#dedbd4] bg-white p-5'>
    <div className='flex items-baseline justify-between gap-2'>
      <h2 className='text-sm font-semibold'>相談する</h2>
      <span className='text-[10px] text-[#99958d]'>3つのAIが議論して答えます（数分かかります）</span>
    </div>

    {(asking || answer || failed) && <div className={`mt-3 max-h-56 overflow-y-auto rounded-lg p-3 ${failed ? 'bg-[#fff1e9]' : 'bg-[#f7f7f5]'}`}>
      {failed ? <>
        <p className='text-xs font-semibold leading-5 text-[#a94712]'>相談できませんでした。答えは出ていません。</p>
        <p className='mt-1 text-[11px] leading-5 text-[#6f6b64]'>
          {blockedProviders.length
            ? `つながらなかったAI：${blockedProviders.join('、')}。鍵か通信を確認してください。`
            : 'もう一度お試しください。'}
        </p>
      </> : answer ? <>
        <p className='text-xs leading-5'>{executiveJapaneseText(answer.decision, '回答を整理しています。')}</p>
        {answer.next_action && <p className='mt-2 border-l-2 border-[#4e6b5c] pl-2 text-[11px] leading-5 text-[#6f6b64]'>
          {executiveJapaneseText(answer.next_action, '')}
        </p>}
      </> : <div className='flex items-center gap-2 py-2'>
        <LoaderCircle className='size-4 shrink-0 animate-spin text-[#817d76]' />
        <p className='text-[11px] text-[#6f6b64]'>{COUNCIL_PROGRESS[run?.status || 'queued'] || '考えています'}</p>
      </div>}
    </div>}

    <div className='mt-3 flex items-end gap-2'>
      <textarea
        ref={inputRef} value={prompt} onChange={event => setPrompt(event.target.value)}
        placeholder='迷っていることを書いてください' aria-label='経営相談'
        className='h-11 min-w-0 flex-1 resize-none rounded-lg border border-[#dedbd4] px-3 py-3 text-sm outline-none focus:border-[#ff6b32] placeholder:text-[#aaa69e]'
      />
      <button
        type='button' onClick={toggleVoice} disabled={transcribing}
        aria-label={recording ? '録音を止める' : '音声で話す'}
        className={`grid size-11 shrink-0 place-items-center rounded-lg border ${recording ? 'border-[#c66a3b] bg-[#fff1e9] text-[#a94712]' : 'border-[#dedbd4] text-[#6f6b64]'}`}
      >
        {transcribing ? <LoaderCircle className='size-4 animate-spin' /> : recording ? <CircleStop className='size-4' /> : <Mic className='size-4' />}
      </button>
      <Button type='submit' disabled={!prompt.trim() || asking} className='h-11 shrink-0 rounded-lg bg-[#ff4801] px-4 text-white hover:bg-[#e04400]'>
        {asking ? <LoaderCircle className='size-4 animate-spin' /> : null}送る
      </Button>
    </div>
    {(error || voiceMessage) && <p className={`mt-2 text-[10px] ${error ? 'text-red-700' : 'text-[#817d76]'}`}>{error || voiceMessage}</p>}
  </form>
}
