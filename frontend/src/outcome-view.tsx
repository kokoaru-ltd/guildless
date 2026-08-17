import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle, Check, ChevronRight, CircleStop, Flame, Languages,
  LoaderCircle, Mic, Terminal, X,
} from 'lucide-react'
import { LANGS, type Lang, dict, loadLang, saveLang } from '@/lib/i18n'

/**
 * The product, not a dashboard over it.
 *
 * Someone who hands over an idea wants one thing: how far has it got toward
 * money. So the run is a single path of eight business stages with exactly one
 * marked current, and opening a stage says what was decided, why, what was
 * actually done, what that revealed, and what comes next.
 *
 * The worker's own steps — observe, diagnose, classify — are absent. They repeat
 * every twenty seconds and tell a reader nothing about their idea. They remain
 * reachable behind a developer panel, where a pulse belongs.
 */

type Stage = {
  id: string; title: string; state: 'done' | 'current' | 'pending' | 'failed'
  summary: string; decided: string; why: string; did: string; learned: string; next: string
}
type HumanTask = { task: string; title: string; detail: string }

type Outcome = {
  verified_net_outcome_yen: number
  spark?: string
  status: string
  bottleneck: string
  current_action: string
  money: { starting_capital_yen: number; available_yen: number; spent_yen: number }
  strategy: { offer?: string; price_yen?: number; chosen_because: string; rejected: { name: string; reasons: string[] }[] }
  human_required: HumanTask[]
  journey?: { stages: Stage[]; position: number; total: number }
  engine?: { alive: boolean; activity: { at: string; step: string; detail: string; external: boolean }[] }
  excluded_from_totals: { test_payments: number }
}

const yen = (value: number) => `¥${Math.round(value || 0).toLocaleString('ja-JP')}`

export function OutcomeView() {
  const [data, setData] = useState<Outcome | null>(null)
  const [failed, setFailed] = useState(false)
  const [lang, setLang] = useState<Lang>(() => loadLang())
  const [openStage, setOpenStage] = useState<string | null>(null)
  const [devOpen, setDevOpen] = useState(false)
  const t = dict(lang)

  const load = useCallback(async () => {
    try {
      const response = await fetch('/v1/outcome')
      if (!response.ok) throw new Error()
      setData(await response.json())
      setFailed(false)
    } catch { setFailed(true) }
  }, [])

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => void load(), 5000)
    return () => window.clearInterval(timer)
  }, [load])

  const changeLang = (next: Lang) => { setLang(next); saveLang(next) }

  if (failed && !data) return <Centre><p className='text-sm text-red-700'>{t.unreachable}</p></Centre>
  if (!data) return <Centre><LoaderCircle className='size-5 animate-spin text-[#817d76]' /></Centre>
  if (!data.spark) return <Home t={t} lang={lang} onLang={changeLang} onStarted={load} />

  const journey = data.journey
  const needsHuman = data.human_required.length > 0
  const detail = journey?.stages.find(s => s.id === openStage)

  return <div className='flex h-svh w-full flex-col overflow-hidden bg-[#f7f7f5] text-[#20201e]'>
    <header className='flex h-12 shrink-0 items-center gap-3 border-b border-[#dedbd4] bg-white px-5'>
      <span className='text-sm font-semibold tracking-tight'>Guildless</span>
      <div className='ml-auto flex items-center gap-2'>
        <LangPicker lang={lang} onLang={changeLang} />
        <button
          onClick={() => setDevOpen(true)}
          className='rounded-lg border border-[#dedbd4] p-1.5 text-[#99958d] hover:bg-[#f3f1ed]'
          title={t.devDetails}
        ><Terminal className='size-3.5' /></button>
      </div>
    </header>

    <main className='min-h-0 flex-1 overflow-y-auto'>
      <div className='mx-auto max-w-[1000px] px-8 py-8'>

        {/* 1. What I asked for, and what it has produced. */}
        <p className='text-xs font-medium text-[#817d76]'>{t.iAskedFor}</p>
        <h1 className='mt-1 text-2xl font-semibold leading-9'>{data.spark}</h1>

        <div className='mt-6 flex flex-wrap items-end gap-x-10 gap-y-4'>
          <div>
            <p className='text-xs font-medium text-[#817d76]'>{t.netOutcome}</p>
            <p className={`mt-0.5 text-5xl font-semibold leading-none tabular-nums ${
              data.verified_net_outcome_yen > 0 ? 'text-[#1a7f37]' : ''
            }`}>{yen(data.verified_net_outcome_yen)}</p>
          </div>
          <Metric label={t.startingCapital} value={yen(data.money.starting_capital_yen)} />
          <Metric label={t.spent} value={yen(data.money.spent_yen)} />
          {journey && <Metric label={t.stageOf} value={`${journey.position} / ${journey.total}`} />}
          <Metric
            label={t.yourAction}
            value={needsHuman ? t.actionRequired : t.actionNone}
            alert={needsHuman}
          />
        </div>

        {needsHuman && <Approval tasks={data.human_required} t={t} />}

        {/* 2. The single path, with one position marked. */}
        {journey && (
          <ol className='mt-8'>
            {journey.stages.map((stage, index) => (
              <StageRow
                key={stage.id} stage={stage} t={t}
                last={index === journey.stages.length - 1}
                onOpen={() => setOpenStage(stage.id)}
              />
            ))}
          </ol>
        )}

        {/* 3. The strategy, so the reasoning is visible without a thought log. */}
        {data.strategy.offer && (
          <section className='mt-8 rounded-xl border border-[#dedbd4] bg-white p-6'>
            <p className='text-xs font-medium text-[#817d76]'>{t.plan}</p>
            <p className='mt-2 text-sm font-semibold'>{data.strategy.offer}
              {data.strategy.price_yen ? <span className='ml-2 font-normal text-[#817d76]'>
                {yen(data.strategy.price_yen)}</span> : null}
            </p>
            <p className='mt-1.5 text-xs leading-5 text-[#6f6b64]'>{data.strategy.chosen_because}</p>
            {data.strategy.rejected.map(item => (
              <p key={item.name} className='mt-1 text-[11px] leading-4 text-[#aaa69e]'>
                {t.rejected}：{item.name} — {item.reasons[0]}
              </p>
            ))}
          </section>
        )}

        {/* 4. Events only. A pulse is not an event. */}
        {data.engine?.activity?.length ? (
          <section className='mt-6'>
            <p className='text-xs font-medium text-[#817d76]'>{t.changes}</p>
            <ol className='mt-2 space-y-1'>
              {data.engine.activity.map((item, index) => (
                <li key={index} className='flex gap-3 text-xs leading-6'>
                  <span className='shrink-0 tabular-nums text-[#c4c0b8]'>{item.at.slice(11, 16)}</span>
                  <span className={item.external ? 'text-[#a94712]' : 'text-[#4d4a45]'}>{item.detail}</span>
                </li>
              ))}
            </ol>
          </section>
        ) : null}
      </div>
    </main>

    {detail && <StageDetail stage={detail} t={t} onClose={() => setOpenStage(null)} />}
    {devOpen && <DevPanel t={t} onClose={() => setDevOpen(false)} />}
  </div>
}

function StageRow({ stage, t, last, onOpen }: {
  stage: Stage; t: ReturnType<typeof dict>; last: boolean; onOpen: () => void
}) {
  const done = stage.state === 'done'
  const current = stage.state === 'current'
  return <li className='relative flex gap-4'>
    <div className='flex flex-col items-center'>
      <span className={`grid size-6 shrink-0 place-items-center rounded-full border-2 ${
        done ? 'border-[#276453] bg-[#276453] text-white'
          : current ? 'border-[#ff4801] bg-white' : 'border-[#dedbd4] bg-white'
      }`}>
        {done ? <Check className='size-3.5' />
          : current ? <span className='size-2 animate-pulse rounded-full bg-[#ff4801]' /> : null}
      </span>
      {!last && <span className={`w-0.5 flex-1 ${done ? 'bg-[#276453]' : 'bg-[#e6e4df]'}`} />}
    </div>

    <button
      onClick={onOpen}
      className={`group mb-4 min-w-0 flex-1 rounded-lg px-3 py-2 text-left transition-colors hover:bg-white ${
        current ? 'bg-white ring-1 ring-[#ffd4c0]' : ''
      }`}
    >
      <div className='flex items-center gap-2'>
        <p className={`text-sm ${current ? 'font-semibold' : done ? 'font-medium' : 'text-[#99958d]'}`}>
          {stage.title}
        </p>
        {current && <span className='rounded-full bg-[#fff1e9] px-2 py-0.5 text-[10px] font-semibold text-[#a94712]'>
          {t.hereNow}
        </span>}
        <ChevronRight className='ml-auto size-3.5 shrink-0 text-[#c4c0b8] opacity-0 transition-opacity group-hover:opacity-100' />
      </div>
      {stage.summary && (
        <p className={`mt-0.5 text-xs leading-5 ${current ? 'text-[#4d4a45]' : 'text-[#99958d]'}`}>
          {stage.summary}
        </p>
      )}
    </button>
  </li>
}

function StageDetail({ stage, t, onClose }: {
  stage: Stage; t: ReturnType<typeof dict>; onClose: () => void
}) {
  const rows = [
    [t.decided, stage.decided], [t.why, stage.why],
    [t.did, stage.did], [t.learned, stage.learned], [t.next, stage.next],
  ].filter(([, value]) => value)

  return <>
    <button className='fixed inset-0 z-30 bg-black/25' onClick={onClose} aria-label={t.close} />
    <aside className='fixed inset-y-0 right-0 z-40 flex w-[460px] flex-col overflow-y-auto border-l border-[#dedbd4] bg-white'>
      <div className='flex items-center justify-between border-b border-[#ece9e3] px-6 py-4'>
        <p className='text-sm font-semibold'>{stage.title}</p>
        <button onClick={onClose} aria-label={t.close} className='rounded p-1 hover:bg-[#f3f1ed]'>
          <X className='size-4' />
        </button>
      </div>
      <div className='px-6 py-5'>
        <p className='text-sm leading-6'>{stage.summary}</p>
        {rows.map(([label, value]) => (
          <div key={label} className='mt-5'>
            <p className='text-xs font-medium text-[#817d76]'>{label}</p>
            <p className='mt-1 text-sm leading-6 text-[#4d4a45]'>{value}</p>
          </div>
        ))}
      </div>
    </aside>
  </>
}

function Approval({ tasks, t }: { tasks: HumanTask[]; t: ReturnType<typeof dict> }) {
  return <section className='mt-6 rounded-xl border-2 border-[#ff4801] bg-[#fff1e9] p-6'>
    <p className='flex items-center gap-2 text-xs font-bold text-[#a94712]'>
      <AlertTriangle className='size-4' />{t.humanNeeded}
    </p>
    {tasks.map(task => (
      <div key={task.task} className='mt-3'>
        <p className='text-lg font-semibold'>{task.title}</p>
        <p className='mt-1 text-sm leading-6 text-[#6f6b64]'>{task.detail}</p>
      </div>
    ))}
  </section>
}

/** One field, dictated or typed, and the constraints beside it. */
function Home({ t, lang, onLang, onStarted }: {
  t: ReturnType<typeof dict>; lang: Lang; onLang: (l: Lang) => void; onStarted: () => void
}) {
  const [text, setText] = useState('')
  const [capital, setCapital] = useState(0)
  const [days, setDays] = useState(7)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [listening, setListening] = useState(false)
  const recognition = useRef<any>(null)

  const speechSupported = typeof window !== 'undefined'
    && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  const toggleVoice = () => {
    if (listening) { recognition.current?.stop(); return }
    const Engine = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!Engine) { setNote(t.voiceUnsupported); return }
    const engine = new Engine()
    engine.lang = lang === 'en' ? 'en-US' : lang === 'zh' ? 'zh-CN' : 'ja-JP'
    engine.interimResults = false
    engine.onresult = (event: any) => {
      const said = Array.from(event.results).map((r: any) => r[0].transcript).join('')
      setText(value => (value ? `${value} ${said}` : said))
    }
    engine.onerror = () => { setListening(false); setNote(t.voiceFailed) }
    engine.onend = () => setListening(false)
    recognition.current = engine
    engine.start()
    setListening(true)
    setNote('')
  }

  const ignite = async () => {
    if (!text.trim()) return
    setBusy(true); setNote('')
    try {
      const response = await fetch('/v1/spark', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          statement: text.trim(), capital_yen: capital, deadline_days: days,
        }),
      })
      if (!response.ok) throw new Error()
      onStarted()
    } catch { setNote(t.startFailed); setBusy(false) }
  }

  return <div className='flex h-svh w-full flex-col bg-[#f7f7f5] text-[#20201e]'>
    <header className='flex h-12 shrink-0 items-center gap-3 border-b border-[#dedbd4] bg-white px-5'>
      <span className='text-sm font-semibold tracking-tight'>Guildless</span>
      <div className='ml-auto'><LangPicker lang={lang} onLang={onLang} /></div>
    </header>

    <div className='grid flex-1 place-items-center p-8'>
      <div className='w-full max-w-xl'>
        <h1 className='text-2xl font-semibold'>{t.whatDoYouWant}</h1>

        <div className='relative mt-5'>
          <textarea
            autoFocus value={text} onChange={event => setText(event.target.value)}
            placeholder={t.sparkPlaceholder}
            className='h-32 w-full resize-none rounded-xl border border-[#dedbd4] bg-white p-5 pr-14 text-lg leading-8 outline-none focus:border-[#ff6b32] placeholder:text-[#c4c0b8]'
          />
          {speechSupported && (
            <button
              onClick={toggleVoice} aria-label={t.voice}
              className={`absolute right-3 top-3 grid size-9 place-items-center rounded-lg border transition-colors ${
                listening ? 'border-[#c66a3b] bg-[#fff1e9] text-[#a94712]' : 'border-[#dedbd4] text-[#6f6b64] hover:bg-[#f3f1ed]'
              }`}
            >{listening ? <CircleStop className='size-4' /> : <Mic className='size-4' />}</button>
          )}
        </div>
        <p className='mt-2 text-xs text-[#99958d]'>
          {listening ? t.listening : t.sparkHelp}
        </p>

        <div className='mt-5 flex gap-4'>
          <Field label={t.startingCapital}>
            <input
              type='number' min={0} step={1000} value={capital}
              onChange={event => setCapital(Number(event.target.value) || 0)}
              className='w-28 rounded-lg border border-[#dedbd4] bg-white px-3 py-2 text-sm tabular-nums outline-none focus:border-[#ff6b32]'
            />
          </Field>
          <Field label={t.deadline}>
            <input
              type='number' min={1} max={365} value={days}
              onChange={event => setDays(Number(event.target.value) || 7)}
              className='w-20 rounded-lg border border-[#dedbd4] bg-white px-3 py-2 text-sm tabular-nums outline-none focus:border-[#ff6b32]'
            />
          </Field>
          <Field label={t.constraints}>
            <p className='py-2 text-xs leading-5 text-[#817d76]'>{t.constraintsFixed}</p>
          </Field>
        </div>

        {note && <p className='mt-3 text-xs text-red-700'>{note}</p>}

        <button
          onClick={ignite} disabled={!text.trim() || busy}
          className='mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#ff4801] text-base font-semibold text-white hover:bg-[#e04400] disabled:bg-[#dedbd4]'
        >
          {busy ? <LoaderCircle className='size-4 animate-spin' /> : <Flame className='size-4' />}
          {t.run}
        </button>
      </div>
    </div>
  </div>
}

function DevPanel({ t, onClose }: { t: ReturnType<typeof dict>; onClose: () => void }) {
  const [rows, setRows] = useState<{ at: string; step: string; detail: string }[]>([])
  useEffect(() => {
    const load = () => fetch('/v1/engine').then(r => r.json())
      .then(d => setRows(d.activity || [])).catch(() => undefined)
    void load()
    const timer = window.setInterval(load, 5000)
    return () => window.clearInterval(timer)
  }, [])

  return <>
    <button className='fixed inset-0 z-30 bg-black/25' onClick={onClose} aria-label={t.close} />
    <aside className='fixed inset-y-0 right-0 z-40 flex w-[520px] flex-col border-l border-[#dedbd4] bg-white'>
      <div className='flex items-center justify-between border-b border-[#ece9e3] px-5 py-4'>
        <p className='text-sm font-semibold'>{t.devDetails}</p>
        <button onClick={onClose} aria-label={t.close} className='rounded p-1 hover:bg-[#f3f1ed]'>
          <X className='size-4' />
        </button>
      </div>
      <ol className='min-h-0 flex-1 overflow-y-auto px-5 py-3 font-mono text-[11px] leading-5'>
        {rows.map((row, index) => (
          <li key={index} className='flex gap-2 text-[#6f6b64]'>
            <span className='shrink-0 text-[#c4c0b8]'>{row.at.slice(11, 19)}</span>
            <span className='shrink-0 text-[#99958d]'>{row.step}</span>
            <span className='min-w-0'>{row.detail}</span>
          </li>
        ))}
      </ol>
    </aside>
  </>
}

function LangPicker({ lang, onLang }: { lang: Lang; onLang: (l: Lang) => void }) {
  return <div className='flex items-center rounded-lg border border-[#dedbd4] p-0.5'>
    <Languages className='mx-1.5 size-3.5 text-[#99958d]' />
    {LANGS.map(item => (
      <button key={item.id} onClick={() => onLang(item.id)}
        className={`rounded-md px-2 py-1 text-[11px] ${
          lang === item.id ? 'bg-[#171513] text-white' : 'text-[#6f6b64] hover:bg-[#f3f1ed]'
        }`}>{item.label}</button>
    ))}
  </div>
}

function Metric({ label, value, alert = false }: { label: string; value: string; alert?: boolean }) {
  return <div>
    <p className='text-xs font-medium text-[#817d76]'>{label}</p>
    <p className={`mt-0.5 text-lg font-semibold tabular-nums ${alert ? 'text-[#a94712]' : ''}`}>{value}</p>
  </div>
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div>
    <p className='mb-1 text-xs font-medium text-[#817d76]'>{label}</p>
    {children}
  </div>
}

function Centre({ children }: { children: React.ReactNode }) {
  return <div className='grid h-svh place-items-center bg-[#f7f7f5]'>{children}</div>
}
