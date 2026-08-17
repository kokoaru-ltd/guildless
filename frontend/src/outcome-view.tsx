import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle, CheckCircle2, CircleSlash, Flame, Languages,
  LoaderCircle, MessageSquare, X,
} from 'lucide-react'
import { LANGS, type Lang, dict, loadLang, saveLang } from '@/lib/i18n'

/**
 * The control centre. Full width, because this is the window the company runs
 * in rather than a document being read — a centred column wastes the space a
 * desktop app was installed to use.
 *
 * Laid out like a workspace: a narrow rail for state that is always true, and
 * everything else in the main area. Five seconds must still answer four
 * questions — how much real money, where it is stuck, what it is doing, and
 * whether the reader has to act — so those four are the largest things on it.
 *
 * Chat is a drawer. A conversation in the middle makes this an assistant, and
 * an assistant is something you have to operate.
 */

type HumanTask = { task: string; title: string; detail: string }
type Evidence = {
  kind: string; source: string; detail: string; at?: string
  counts_as_revenue: boolean; note: string
}
type Failure = { what: string; detail: string; learning: string }

type Outcome = {
  verified_net_outcome_yen: number
  goal: string
  spark?: string
  status: 'RUNNING' | 'BLOCKED' | 'HUMAN_REQUIRED' | 'SUCCESS' | 'TERMINAL_FAILURE'
  bottleneck: string
  current_action: string
  money: {
    starting_capital_yen: number; available_yen: number; reserved_yen: number
    spent_yen: number; verified_revenue_yen: number
    breakdown_yen: Record<string, number>
  }
  strategy: {
    offer?: string; price_yen?: number; chosen_because: string
    rejected: { name: string; reasons: string[] }[]
  }
  evidence: Evidence[]
  failures: Failure[]
  human_required: HumanTask[]
  gate: { level: string; real_payments: number }
  external_action?: { granted: boolean; note: string }
  excluded_from_totals: { test_payments: number; note: string }
}

const TONE: Record<string, { chip: string; dot: string }> = {
  RUNNING: { chip: 'text-[#276453] bg-[#edf5f1] border-[#c3ddcf]', dot: 'bg-[#276453]' },
  BLOCKED: { chip: 'text-[#8a6410] bg-[#fdf6e7] border-[#e4cfa6]', dot: 'bg-[#8a6410]' },
  HUMAN_REQUIRED: { chip: 'text-[#a94712] bg-[#fff1e9] border-[#efc8b7]', dot: 'bg-[#ff4801]' },
  SUCCESS: { chip: 'text-[#276453] bg-[#edf5f1] border-[#c3ddcf]', dot: 'bg-[#276453]' },
  TERMINAL_FAILURE: { chip: 'text-[#b3261e] bg-[#ffebe9] border-[#f5b5b0]', dot: 'bg-[#b3261e]' },
}

const yen = (value: number) => `¥${Math.round(value || 0).toLocaleString('ja-JP')}`

export function OutcomeView() {
  const [data, setData] = useState<Outcome | null>(null)
  const [error, setError] = useState('')
  const [drawer, setDrawer] = useState(false)
  const [lang, setLang] = useState<Lang>(() => loadLang())
  const t = dict(lang)

  const load = useCallback(async () => {
    try {
      const response = await fetch('/v1/outcome')
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      setData(await response.json())
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'unavailable')
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => void load(), 5000)
    return () => window.clearInterval(timer)
  }, [load])

  const changeLang = (next: Lang) => { setLang(next); saveLang(next) }

  if (error && !data) {
    return <Shell lang={lang} onLang={changeLang} t={t}>
      <div className='grid h-full place-items-center'>
        <div className='rounded-xl border border-red-200 bg-red-50 px-6 py-4 text-sm text-red-700'>
          {error}
        </div>
      </div>
    </Shell>
  }
  if (!data) {
    return <Shell lang={lang} onLang={changeLang} t={t}>
      <div className='grid h-full place-items-center'>
        <LoaderCircle className='size-5 animate-spin text-[#817d76]' />
      </div>
    </Shell>
  }

  // Nothing has been started, so the only thing on screen is how to start it.
  if (!data.spark) {
    return <Shell lang={lang} onLang={changeLang} t={t}>
      <SparkGate t={t} onStarted={load} />
    </Shell>
  }

  const tone = TONE[data.status] || TONE.RUNNING
  const money = data.money
  const needsHuman = data.human_required.length > 0

  return <Shell
    lang={lang} onLang={changeLang} t={t}
    rail={<Rail data={data} tone={tone} t={t} />}
    onAsk={() => setDrawer(true)}
  >
    <div className='grid gap-4 p-6 xl:grid-cols-2 2xl:grid-cols-3'>
      {needsHuman && (
        <section className='rounded-xl border-2 border-[#ff4801] bg-[#fff1e9] p-6 xl:col-span-2 2xl:col-span-3'>
          <p className='flex items-center gap-2 text-xs font-bold text-[#a94712]'>
            <AlertTriangle className='size-4' />{t.humanNeeded}
          </p>
          {data.human_required.map(task => (
            <div key={task.task} className='mt-3'>
              <p className='text-lg font-semibold'>{task.title}</p>
              <p className='mt-1 text-sm leading-6 text-[#6f6b64]'>{task.detail}</p>
            </div>
          ))}
        </section>
      )}

      <Card title={t.money}>
        <Row label={t.startingCapital} value={yen(money.starting_capital_yen)} />
        <Row label={t.available} value={yen(money.available_yen)} />
        <Row label={t.reserved} value={yen(money.reserved_yen)} muted />
        <Row label={t.spent} value={yen(money.spent_yen)} />
        <Row label={t.verifiedRevenue} value={yen(money.verified_revenue_yen)} strong />
        <div className='mt-3 border-t border-[#ece9e3] pt-2'>
          {Object.entries(money.breakdown_yen).map(([name, amount]) => (
            <div key={name} className='flex justify-between py-0.5 text-[11px] text-[#99958d]'>
              <span>{name}</span><span className='tabular-nums'>{yen(amount)}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card title={t.trying}>
        {data.strategy.offer ? <>
          <p className='text-sm font-semibold leading-6'>{data.strategy.offer}</p>
          {data.strategy.price_yen ? (
            <p className='mt-1 text-xs text-[#817d76]'>{yen(data.strategy.price_yen)}</p>
          ) : null}
          <p className='mt-3 text-xs leading-5 text-[#6f6b64]'>
            {t.chosenBecause}：{data.strategy.chosen_because}
          </p>
          {data.strategy.rejected.length > 0 && (
            <div className='mt-3 border-t border-[#ece9e3] pt-2'>
              <p className='text-[11px] font-medium text-[#99958d]'>{t.rejected}</p>
              {data.strategy.rejected.map(item => (
                <p key={item.name} className='py-0.5 text-[11px] leading-4 text-[#99958d]'>
                  {item.name} — {item.reasons[0]}
                </p>
              ))}
            </div>
          )}
        </> : <p className='text-sm text-[#817d76]'>{t.notSelected}</p>}
      </Card>

      <Card title={t.evidence}>
        {data.evidence.length ? data.evidence.map((item, index) => (
          <div key={index} className='border-b border-[#ece9e3] py-2 last:border-0'>
            <div className='flex items-center gap-2'>
              {item.counts_as_revenue
                ? <CheckCircle2 className='size-3.5 shrink-0 text-[#1a7f37]' />
                : <CircleSlash className='size-3.5 shrink-0 text-[#aaa69e]' />}
              <p className='text-xs font-medium'>{item.source} · {item.detail}</p>
            </div>
            {item.note && <p className='mt-1 pl-5 text-[11px] leading-4 text-[#a94712]'>{item.note}</p>}
          </div>
        )) : <p className='text-sm text-[#817d76]'>{t.noEvidence}</p>}
      </Card>

      {data.failures.length > 0 && (
        <section className='rounded-xl border border-[#dedbd4] bg-white p-6 xl:col-span-2 2xl:col-span-3'>
          <p className='text-xs font-medium text-[#817d76]'>{t.failures}</p>
          <div className='mt-3 grid gap-4 lg:grid-cols-2'>
            {data.failures.map((failure, index) => (
              <div key={index} className='rounded-lg bg-[#f7f7f5] p-4'>
                <p className='text-sm font-medium'>{failure.what}</p>
                {failure.detail && <p className='mt-1 text-xs leading-5 text-[#817d76]'>{failure.detail}</p>}
                <p className='mt-2 border-l-2 border-[#ff4801] pl-2 text-xs leading-5 text-[#4d4a45]'>
                  {failure.learning}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>

    {drawer && <Drawer t={t} onClose={() => setDrawer(false)} />}
  </Shell>
}

/** Full-bleed frame: rail, header, scrolling main area. */
function Shell({ children, rail, lang, onLang, t, onAsk }: {
  children: React.ReactNode; rail?: React.ReactNode
  lang: Lang; onLang: (l: Lang) => void; t: ReturnType<typeof dict>
  onAsk?: () => void
}) {
  return <div className='flex h-svh w-full overflow-hidden bg-[#f7f7f5] text-[#20201e]'>
    {rail && <aside className='hidden w-[300px] shrink-0 flex-col overflow-y-auto border-r border-[#dedbd4] bg-white lg:flex'>
      {rail}
    </aside>}

    <div className='flex min-w-0 flex-1 flex-col'>
      <header className='flex h-12 shrink-0 items-center gap-3 border-b border-[#dedbd4] bg-white px-5'>
        <span className='text-sm font-semibold tracking-tight'>Guildless</span>
        <span className='hidden truncate text-xs text-[#99958d] md:block'>{t.appTagline}</span>
        <div className='ml-auto flex items-center gap-2'>
          <div className='flex items-center rounded-lg border border-[#dedbd4] p-0.5'>
            <Languages className='mx-1.5 size-3.5 text-[#99958d]' />
            {LANGS.map(item => (
              <button
                key={item.id}
                onClick={() => onLang(item.id)}
                className={`rounded-md px-2 py-1 text-[11px] transition-colors ${
                  lang === item.id ? 'bg-[#171513] text-white' : 'text-[#6f6b64] hover:bg-[#f3f1ed]'
                }`}
              >{item.label}</button>
            ))}
          </div>
          {onAsk && (
            <button
              onClick={onAsk}
              className='flex items-center gap-1.5 rounded-lg border border-[#dedbd4] px-3 py-1.5 text-xs text-[#6f6b64] hover:bg-[#f3f1ed]'
            ><MessageSquare className='size-3.5' />{t.ask}</button>
          )}
        </div>
      </header>
      <main className='min-h-0 flex-1 overflow-y-auto'>{children}</main>
    </div>
  </div>
}

/** The four answers, always visible, never scrolled away. */
function Rail({ data, tone, t }: {
  data: Outcome; tone: { chip: string; dot: string }; t: ReturnType<typeof dict>
}) {
  return <div className='flex flex-col gap-5 p-6'>
    <div>
      <p className='text-xs font-medium text-[#817d76]'>{t.netOutcome}</p>
      <p className={`mt-1 text-5xl font-semibold leading-none tracking-tight tabular-nums ${
        data.verified_net_outcome_yen > 0 ? 'text-[#1a7f37]' : ''
      }`}>{yen(data.verified_net_outcome_yen)}</p>
      <p className='mt-2 text-[11px] leading-4 text-[#99958d]'>
        {t.netOutcomeNote}
        {data.excluded_from_totals.test_payments > 0
          && ` ${t.testExcluded(data.excluded_from_totals.test_payments)}`}
      </p>
    </div>

    <div className={`rounded-xl border px-4 py-3 ${tone.chip}`}>
      <div className='flex items-center gap-2'>
        <span className={`size-2 rounded-full ${tone.dot}`} />
        <p className='text-sm font-semibold'>{t.statusLabels[data.status] || data.status}</p>
      </div>
    </div>

    <div>
      <p className='text-xs font-medium text-[#817d76]'>{t.bottleneck}</p>
      <p className='mt-1.5 text-sm font-medium leading-6'>{data.bottleneck}</p>
    </div>

    <div>
      <p className='text-xs font-medium text-[#817d76]'>{t.doingNow}</p>
      <p className='mt-1.5 text-sm leading-6 text-[#4d4a45]'>{data.current_action}</p>
    </div>

    {data.spark && (
      <div className='border-t border-[#ece9e3] pt-4'>
        <p className='text-xs font-medium text-[#817d76]'>{t.spark}</p>
        <p className='mt-1.5 text-xs leading-5 text-[#6f6b64]'>{data.spark}</p>
      </div>
    )}

    <div className='mt-auto space-y-1 border-t border-[#ece9e3] pt-4 text-[11px] text-[#aaa69e]'>
      <p>{t.gate} {data.gate.level} · {t.confirmedPayments} {data.gate.real_payments}</p>
      {data.external_action && (
        <p>{t.externalAction} {data.external_action.granted ? t.granted : t.notGranted}</p>
      )}
    </div>
  </div>
}

/** First run: one field, because a plan is not required to begin. */
function SparkGate({ t, onStarted }: { t: ReturnType<typeof dict>; onStarted: () => void }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const ignite = async () => {
    if (!text.trim()) return
    setBusy(true); setError('')
    try {
      const response = await fetch('/v1/spark', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ statement: text.trim() }),
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      onStarted()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'failed')
      setBusy(false)
    }
  }

  return <div className='grid h-full place-items-center p-8'>
    <div className='w-full max-w-2xl'>
      <p className='flex items-center gap-2 text-xs font-medium text-[#817d76]'>
        <Flame className='size-4 text-[#ff4801]' />{t.spark}
      </p>
      <textarea
        autoFocus value={text} onChange={event => setText(event.target.value)}
        placeholder={t.sparkPlaceholder}
        className='mt-3 h-32 w-full resize-none rounded-xl border border-[#dedbd4] bg-white p-5 text-lg leading-8 outline-none focus:border-[#ff6b32] placeholder:text-[#c4c0b8]'
      />
      <p className='mt-2 text-xs text-[#99958d]'>{t.sparkHelp}</p>
      {error && <p className='mt-2 text-xs text-red-700'>{error}</p>}
      <button
        onClick={ignite} disabled={!text.trim() || busy}
        className='mt-5 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#ff4801] text-base font-semibold text-white transition-colors hover:bg-[#e04400] disabled:bg-[#dedbd4]'
      >
        {busy ? <LoaderCircle className='size-4 animate-spin' /> : <Flame className='size-4' />}
        {t.ignite}
      </button>
    </div>
  </div>
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className='rounded-xl border border-[#dedbd4] bg-white p-6'>
    <p className='text-xs font-medium text-[#817d76]'>{title}</p>
    <div className='mt-3'>{children}</div>
  </div>
}

function Row({ label, value, muted = false, strong = false }: {
  label: string; value: string; muted?: boolean; strong?: boolean
}) {
  return <div className='flex items-baseline justify-between py-1'>
    <span className='text-xs text-[#817d76]'>{label}</span>
    <span className={`text-sm tabular-nums ${strong ? 'font-semibold' : ''} ${muted ? 'text-[#aaa69e]' : ''}`}>
      {value}
    </span>
  </div>
}

function Drawer({ t, onClose }: { t: ReturnType<typeof dict>; onClose: () => void }) {
  return <>
    <button className='fixed inset-0 z-30 bg-black/20' onClick={onClose} aria-label={t.close} />
    <aside className='fixed inset-y-0 right-0 z-40 flex w-[380px] flex-col border-l border-[#dedbd4] bg-white'>
      <div className='flex items-center justify-between border-b border-[#ece9e3] px-5 py-4'>
        <p className='text-sm font-semibold'>{t.ask}</p>
        <button onClick={onClose} aria-label={t.close} className='rounded p-1 hover:bg-[#f3f1ed]'>
          <X className='size-4' />
        </button>
      </div>
      <p className='px-5 py-4 text-xs leading-5 text-[#817d76]'>{t.askNote}</p>
    </aside>
  </>
}
