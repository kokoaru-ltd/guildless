import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  ArrowLeft, ArrowRight, Building2, CheckCircle2, CircleDollarSign, ExternalLink,
  FlaskConical, GitBranch, GitFork, HandCoins, ListChecks, LoaderCircle, PackagePlus,
  Plug, Puzzle, Rocket, RotateCcw, Scale, Search, ShieldCheck, Table2, Target,
  Trash2, TriangleAlert, Wrench,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

type StageName =
  | 'goal'
  | 'plan'
  | 'constraint'
  | 'experiment'
  | 'envelope'
  | 'capability'
  | 'execute'
  | 'observe'
  | 'decide'
  | 'killed'

type BusinessCandidate = {
  id: string
  name: string
  price_yen: number
  delivery_hours: number
  summary: string
  channels: string[]
}

type ConstraintCheck = {
  id: string
  name: string
  detail: string
  pass: boolean
  note: string
}

type Experiment = {
  id: string
  label: string
  channel: string
  tactic: string
  tactic_detail: string
  rationale: string
  target_count: number
  budget_yen: number
  status: string
}

type Envelope = {
  channel: string[]
  target_count_cap: number
  budget_cap_yen: number
  period_hours: number
  follow_up_max: number
  prohibited: string[]
  status: string
  summary: string
  approved_at?: string | null
  approved_by?: string | null
}

type Capability = {
  id: string
  name: string
  note: string
  status: string
}

type Order = {
  order_id: string
  company: string
  amount_yen: number
  recorded_at: string
  recorded_by: string
  source: string
  delivered: boolean
  delivered_at?: string | null
  deliverable?: string | null
}

type LedgerEntry = {
  kind: string
  amount_yen: number
  label: string
  at: string
}

type Decision = {
  verdict: 'SCALE' | 'MODIFY' | 'KILL'
  summary: string
  spend_yen: number
  revenue_yen: number
  purchase_count: number
  decided_at: string
}

type V0Loop = {
  loop_id: string
  intent: string
  budget_yen: number
  deadline_days: number
  created_at: string
  stage: StageName
  furthest_stage: StageName
  status: string
  mode: string
  cycles: number
  goal: {
    final_goal: string
    intermediate_goal: string
    budget_yen: number
    deadline_days: number
    intent: string
    human_involvement: string
  } | null
  candidates: BusinessCandidate[]
  selected_business: BusinessCandidate | null
  constraint_checks: ConstraintCheck[]
  experiments: Experiment[]
  envelope: Envelope | null
  capabilities: Capability[]
  execution: {
    mode: string
    simulated: boolean
    simulated_note: string
    contacted_at: string | null
    experiments: Array<{
      experiment_id: string
      label: string
      channel: string
      tactic: string
      tactic_detail: string
      contacts: number
      replied: number
      interested: number
      responses: number
      purchases: number
      cost_yen: number
      cost_breakdown: Array<{ item: string; amount_yen: number }>
      revenue_yen: number
    }>
    totals: {
      contacts: number
      replied: number
      interested: number
      responses: number
      purchases: number
      cost_yen: number
      revenue_yen: number
      cost_breakdown: Array<{ item: string; amount_yen: number }>
    }
  } | null
  ledger: {
    cost_yen: number
    revenue_yen: number
    orders: Order[]
    entries: LedgerEntry[]
  }
  decision: Decision | null
  cycle_history: unknown[]
  checkins: Array<{
    id: string
    confirmed_at: string
    stage: string
    note: string
    by: string
  }>
}

// --- Revenue Engine v0.1（商材1つ -> 売上までの工程 -> 部品探索 -> 実行計画） -----
type RevenueCandidate = {
  name: string
  type: string
  detail: string
  source: string
}

type RevenueGap = {
  skill_id: string
  name: string
  required_capabilities: string[]
  suggested_query: string
  discovered_candidates: Array<{
    full_name: string
    html_url: string
    description: string
    stars: number
    score: number
    capabilities: string[]
  }>
}

type RevenuePlan = {
  plan_id: string
  created_at: string
  product: string
  price_yen: number
  target_revenue_yen: number
  budget_yen: number
  deadline_days: number
  region: string
  industry: string
  backward_calc: {
    target_revenue_yen: number
    price_yen: number
    required_orders: number
    meeting_rate: number
    required_meetings: number
    response_rate: number
    required_contacts: number
    interested: number
    note: string
  }
  funnel: Array<{
    stage_id: string
    label: string
    kpi: string
    unit: string
    note: string
    count: number | null
    basis: string
  }>
  capabilities: Array<{
    skill_id: string
    name: string
    goal: string
    owner: string
    kpi: string
    cost_limit_yen: number
    required_capabilities: string[]
    status: string
    primary: RevenueCandidate | null
    candidates: RevenueCandidate[]
  }>
  workflow: Array<{
    step: number
    stage_id: string
    stage_label: string
    skill_id: string
    name: string
    goal: string
    owner: string
    status: string
    primary: RevenueCandidate | null
    cost_limit_yen: number
  }>
  gaps: RevenueGap[]
  sources: {
    installed_packs: string[]
    oss_adapters: Record<string, string[]>
  }
  scout: {
    status: string
    queried_at: string | null
    results: Array<{ skill_id: string; query: string; found: number }>
    error?: string
  }
}

const STAGE_ORDER: StageName[] = [
  'goal', 'plan', 'constraint', 'experiment', 'envelope',
  'capability', 'execute', 'observe', 'decide',
]

const STAGE_META: Record<StageName, { label: string; hint: string }> = {
  goal: { label: '目標を決める', hint: 'いくら稼ぐか、いつまでにか、を数字にします' },
  plan: { label: '売るものを選ぶ', hint: '何を・誰に・いくらで売るかの候補を並べます' },
  constraint: { label: 'やれる範囲を確認', hint: '法律・資金・免許で引っかかることを先につぶします' },
  experiment: { label: '試し方を決める', hint: '売り方をいくつか作り、少額ずつ試します' },
  envelope: { label: '許可をもらう', hint: '「何社まで・いくらまで」を決めて、あなたが一度だけ許可します' },
  capability: { label: '道具をそろえる', hint: '営業に必要な仕組みを、既存のものから用意します' },
  execute: { label: '営業する', hint: '許可された範囲の中だけで、相手に連絡します' },
  observe: { label: '結果を数える', hint: '何社に声をかけ、何件返事が来て、いくら使ったかを記録します' },
  decide: { label: '続けるか決める', hint: '伸ばす・やり方を変える・やめる、のどれかを確定します' },
  killed: { label: 'やめた', hint: '見込みが立たないため、この商品での挑戦は止めました' },
}

const CHANNEL_LABELS: Record<string, string> = {
  email: 'メール',
  phone: '電話',
  dm: 'DM',
}

const VERDICT_META: Record<Decision['verdict'], { label: string; color: string; note: string }> = {
  SCALE: { label: '伸ばす', color: '#276453', note: '入金があり黒字です。次の営業に予算を寄せます' },
  MODIFY: { label: 'やり方を変える', color: '#b7791f', note: '売れなかったので、相手か売り方を変えて試し直します' },
  KILL: { label: 'やめる', color: '#b3261e', note: '見込みが立たないため、この商品での挑戦を止めます' },
}

function fmtYen(value: number) {
  return `¥${(value ?? 0).toLocaleString('ja-JP')}`
}

function fmtDate(iso: string | null | undefined) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ja-JP', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error((body as { detail?: string }).detail || `HTTP ${response.status}`)
  }
  return body as T
}
export function SalesMarketingView() {
  const [viewMode, setViewMode] = useState<'v0' | 'revenue'>('v0')
  const [loop, setLoop] = useState<V0Loop | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [intent, setIntent] = useState('')
  const [budget, setBudget] = useState(30_000)
  const [deadline, setDeadline] = useState(14)
  const [orderCompany, setOrderCompany] = useState('')
  const [orderAmount, setOrderAmount] = useState('')
  const [prefilledFor, setPrefilledFor] = useState<string | null>(null)
  const [killReason, setKillReason] = useState('')

  useEffect(() => {
    requestJson<{ exists: boolean; loop: V0Loop | null }>('/v1/v0/overview')
      .then(data => setLoop(data.loop))
      .catch(reason => setError(reason instanceof Error ? reason.message : '売上ループを読み込めませんでした'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (loop && loop.loop_id !== prefilledFor) {
      setPrefilledFor(loop.loop_id)
      if (loop.selected_business?.price_yen) {
        setOrderAmount(String(loop.selected_business.price_yen))
      }
    }
  }, [loop, prefilledFor])

  const runAction = async (path: string, payload?: Record<string, unknown>) => {
    if (!loop) return
    setBusy(true)
    setError('')
    try {
      const next = await requestJson<V0Loop>(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload ?? { loop_id: loop.loop_id }),
      })
      setLoop(next)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '処理に失敗しました')
    } finally {
      setBusy(false)
    }
  }

  const startLoop = async () => {
    if (!intent.trim()) {
      setError('事業の目的を入力してください')
      return
    }
    setBusy(true)
    setError('')
    try {
      const next = await requestJson<V0Loop>('/v1/v0/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intent: intent.trim(), budget_yen: budget, deadline_days: deadline }),
      })
      setLoop(next)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '開始できませんでした')
    } finally {
      setBusy(false)
    }
  }

  const recordOrder = async () => {
    if (!orderCompany.trim()) {
      setError('注文企業名を入力してください')
      return
    }
    const amount = Number(orderAmount)
    if (!Number.isFinite(amount) || amount < 100) {
      setError('金額は100円以上で入力してください')
      return
    }
    await runAction('/v1/v0/order', {
      loop_id: loop?.loop_id,
      company: orderCompany.trim(),
      amount_yen: amount,
    })
  }

  const stageIndex = loop
    ? loop.stage === 'killed'
      ? STAGE_ORDER.length
      : STAGE_ORDER.indexOf(loop.stage)
    : -1

  const kpi = useMemo(() => (loop ? buildKpi(loop) : []), [loop])

  if (loading) {
    return (
      <div className='grid h-svh place-items-center bg-[#f6f8fa]'>
        <LoaderCircle className='size-5 animate-spin text-[#ff4801]' />
      </div>
    )
  }

  if (viewMode === 'revenue') {
    return <RevenueView onBack={() => setViewMode('v0')} />
  }

  if (!loop) {
    return (
      <StartView
        intent={intent}
        setIntent={setIntent}
        budget={budget}
        setBudget={setBudget}
        deadline={deadline}
        setDeadline={setDeadline}
        busy={busy}
        error={error}
        onStart={startLoop}
        viewMode={viewMode}
        onModeChange={setViewMode}
      />
    )
  }

  return (
    <div className='flex h-svh flex-col overflow-hidden bg-[#f6f8fa] text-[#24292f]'>
      <TopBar
        loop={loop}
        onRestart={() => setLoop(null)}
        viewMode={viewMode}
        onModeChange={setViewMode}
      />
      <RehearsalStrip loop={loop} />
      <KpiStrip kpi={kpi} />

      <div className='grid min-h-0 flex-1 grid-cols-[212px_minmax(0,1fr)_minmax(344px,392px)]'>
        <StageRail
          loop={loop}
          stageIndex={stageIndex}
          onNavigate={stage => runAction('/v1/v0/goto', { loop_id: loop.loop_id, stage })}
        />

        <main className='min-h-0 overflow-y-auto'>
          {error && (
            <div className='mx-3 mt-3 rounded-md border border-[#ff818266] bg-[#ffebe9] px-3 py-2 text-xs text-[#cf222e]'>{error}</div>
          )}
          <div className='p-2.5'>
            <StageCard
              loop={loop}
              busy={busy}
              onAdvance={() => runAction('/v1/v0/advance')}
              onApprove={() => runAction('/v1/v0/approve')}
              onDecide={() => runAction('/v1/v0/decide')}
              onSelect={candidateId => runAction('/v1/v0/select', { loop_id: loop.loop_id, candidate_id: candidateId })}
              onResolve={(name, source) => runAction('/v1/v0/resolve-capability', { loop_id: loop.loop_id, name, source })}
            />
          </div>
        </main>

        <aside className='flex min-h-0 flex-col gap-2.5 overflow-y-auto border-l border-[#d0d7de] bg-[#f6f8fa] p-2.5'>
          <DailyCheckinPanel
            loop={loop}
            busy={busy}
            onDailyConfirm={note => runAction('/v1/v0/daily-confirm', { loop_id: loop.loop_id, note })}
          />
          <VerdictCard loop={loop} />
          <LedgerPanel
            loop={loop}
            busy={busy}
            orderCompany={orderCompany}
            setOrderCompany={setOrderCompany}
            orderAmount={orderAmount}
            setOrderAmount={setOrderAmount}
            killReason={killReason}
            setKillReason={setKillReason}
            onRecordOrder={recordOrder}
            onDeliver={orderId => runAction('/v1/v0/deliver', { loop_id: loop.loop_id, order_id: orderId })}
            onKill={() => runAction('/v1/v0/kill', { loop_id: loop.loop_id, reason: killReason.trim() })}
          />
        </aside>
      </div>
    </div>
  )
}
function StartView({
  intent, setIntent, budget, setBudget, deadline, setDeadline, busy, error, onStart, viewMode, onModeChange,
}: {
  intent: string
  setIntent: (value: string) => void
  budget: number
  setBudget: (value: number) => void
  deadline: number
  setDeadline: (value: number) => void
  busy: boolean
  error: string
  viewMode: 'v0' | 'revenue'
  onModeChange: (value: 'v0' | 'revenue') => void
  onStart: () => void
}) {
  return (
    <div className='flex h-svh flex-col overflow-hidden bg-[#f6f8fa] text-[#24292f]'>
      <header className='flex h-11 shrink-0 items-center gap-2.5 border-b border-[#d0d7de] bg-white px-3'>
        <img src='/ui-assets/guildless-mark.svg' alt='Guildless' className='size-6 rounded' />
        <h1 className='text-[13px] font-bold tracking-[-.01em]'>Guildless</h1>
        <span className='text-[11px] text-[#57606a]'>ゼロから売上を作る</span>
        <span className='inline-flex items-center gap-1 rounded-full border border-[#d4a72c]/50 bg-[#fff8c5] px-2 py-0.5 text-[10px] font-semibold text-[#7d5d00]'>
          <ShieldCheck className='size-3' />
          確認運転
        </span>
        <ModeTabs value={viewMode} onChange={onModeChange} />
      </header>

      <div className='grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_minmax(360px,420px)]'>
        <section className='min-h-0 overflow-y-auto border-r border-[#d0d7de] bg-white p-3'>
          <p className='text-[10px] font-bold text-[#ff4801]'>Guildless v0 · Zero-to-Revenue</p>
          <h2 className='mt-0.5 text-lg font-bold tracking-[-.02em]'>「何か売れ」だけを渡す</h2>
          <p className='mt-1 max-w-2xl text-xs leading-5 text-[#57606a]'>
            事業名・予算・期限だけを渡すと、計画・承認・実行・判定までGuildless自身が回します。
            人間は承認と決済・納品のみ。GitHub等の既存OSSは「部品の確保」として必要なときだけ使います。
          </p>

          <ol className='mt-3 max-w-2xl space-y-1'>
            {[
              '事業候補を最大6つ生成し、1つを選択（選ぶと制約・実験・許可まで自動再構築）',
              '仮説を複数設計し、実行許可（範囲・上限）を1回だけ人間が承認',
              '営業の結果を数え、伸ばす・やり方を変える・やめる を判定',
              '実入金は人間が台帳に登録。決済・契約・納品は人間操作',
            ].map((item, index) => (
              <li key={index} className='flex items-start gap-2 rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-2.5 py-1.5'>
                <span className='mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-[#24292f] text-[9px] font-bold text-white'>{index + 1}</span>
                <span className='text-xs leading-5 text-[#24292f]'>{item}</span>
              </li>
            ))}
          </ol>

          <div className='mt-3 max-w-2xl'>
            <p className='text-[10px] font-bold text-[#57606a]'>v0の探索空間（システム側で固定）</p>
            <div className='mt-1.5 grid grid-cols-2 gap-1.5'>
              {[
                'デジタル納品・在庫なし',
                '初期費用3万円以下',
                '免許不要・BtoB',
                '3,000〜10,000円・即決済',
                '24〜48時間以内に納品',
                '人間は承認と決済・納品のみ',
              ].map(item => (
                <div key={item} className='flex items-center gap-1.5 rounded-md border border-[#d0d7de] bg-white px-2 py-1.5 text-[11px] text-[#57606a]'>
                  <CheckCircle2 className='size-3.5 shrink-0 text-[#1a7f37]' />
                  {item}
                </div>
              ))}
            </div>
          </div>
        </section>

        <aside className='flex min-h-0 flex-col overflow-y-auto border-l border-[#d0d7de] bg-white p-3'>
          <label className='text-xs font-bold text-[#24292f]'>事業の目的</label>
          <textarea
            value={intent}
            onChange={event => setIntent(event.target.value)}
            placeholder='例：新規事業を立ち上げて、第三者から最初の売上を作れ'
            rows={4}
            className='mt-2 w-full resize-none rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-3 py-2.5 text-sm outline-none focus:border-[#ff7038] focus:bg-white'
          />
          <div className='mt-4 grid grid-cols-2 gap-3'>
            <label className='block'>
              <span className='text-xs font-bold text-[#24292f]'>予算上限（円）</span>
              <input
                type='number'
                value={budget}
                min={1000}
                max={100000}
                step={1000}
                onChange={event => setBudget(Number(event.target.value))}
                className='mt-2 w-full rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-3 py-2.5 text-sm outline-none focus:border-[#ff7038] focus:bg-white'
              />
            </label>
            <label className='block'>
              <span className='text-xs font-bold text-[#24292f]'>期間（日）</span>
              <input
                type='number'
                value={deadline}
                min={1}
                max={90}
                onChange={event => setDeadline(Number(event.target.value))}
                className='mt-2 w-full rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-3 py-2.5 text-sm outline-none focus:border-[#ff7038] focus:bg-white'
              />
            </label>
          </div>
          <p className='mt-3 text-[11px] leading-5 text-[#57606a]'>
            相手への連絡は、あなたが許可した範囲の中だけ。決済・契約・納品はすべて人間が行います。
          </p>
          {error && <p className='mt-3 rounded-md border border-[#ff818266] bg-[#ffebe9] px-3 py-2 text-xs text-[#cf222e]'>{error}</p>}
          <Button onClick={onStart} disabled={busy} className='mt-4 h-11 w-full rounded-md bg-[#ff4801] text-white hover:bg-[#e04400]'>
            {busy ? <LoaderCircle className='size-4 animate-spin' /> : <ArrowRight className='size-4' />}
            {busy ? '計画中' : '事業を開始'}
          </Button>
        </aside>
      </div>
    </div>
  )
}
type KpiItem = { label: string; value: string; tone?: 'pos' | 'neg' | 'warn' }

function buildKpi(loop: V0Loop): KpiItem[] {
  // 台帳（実入金）を優先表示：入金登録直後にKPIが動くようにする
  const revenue = loop.ledger.revenue_yen ?? 0
  const cost = loop.ledger.cost_yen ?? 0
  const profit = revenue - cost
  const purchases = loop.ledger.orders.length
  const totals = loop.execution?.totals
  const contacts = totals?.contacts ?? 0
  const responses = totals?.responses ?? 0
  const remaining = loop.budget_yen - cost
  return [
    { label: '売上', value: fmtYen(revenue), tone: revenue > 0 ? 'pos' : undefined },
    { label: '支出', value: fmtYen(cost), tone: cost > 0 ? 'warn' : undefined },
    { label: '収支', value: fmtYen(profit), tone: profit >= 0 ? 'pos' : 'neg' },
    { label: '入金', value: `${purchases}件`, tone: purchases > 0 ? 'pos' : undefined },
    { label: '接触', value: `${contacts}社` },
    { label: '反応', value: `${responses}件` },
    { label: '予算残', value: fmtYen(Math.max(remaining, 0)), tone: remaining < 0 ? 'neg' : undefined },
  ]
}

function TopBar({ loop, onRestart, viewMode, onModeChange }: { loop: V0Loop; onRestart: () => void; viewMode: 'v0' | 'revenue'; onModeChange: (value: 'v0' | 'revenue') => void }) {
  const stageLabel = loop.stage === 'killed' ? '停止' : STAGE_META[loop.stage].label
  return (
    <header className='flex h-11 shrink-0 items-center gap-2.5 border-b border-[#d0d7de] bg-white px-3'>
      <img src='/ui-assets/guildless-mark.svg' alt='Guildless' className='size-6 rounded' />
      <h1 className='text-[13px] font-bold tracking-[-.01em]'>Guildless</h1>
      <span className='text-[11px] text-[#57606a]'>売上ループ</span>
      <span className='rounded-md bg-[#f6f8fa] px-1.5 py-0.5 text-[11px] font-medium text-[#57606a]'>{stageLabel}</span>
      <ModeTabs value={viewMode} onChange={onModeChange} />
      <div className='ml-auto flex items-center gap-4 text-[11px] text-[#57606a]'>
        <span className='hidden max-w-[280px] truncate xl:block'>目的：<b className='font-semibold text-[#24292f]'>{loop.intent}</b></span>
        <span>予算 <b className='font-semibold tabular-nums text-[#24292f]'>{fmtYen(loop.budget_yen)}</b></span>
        <span>期間 <b className='font-semibold text-[#24292f]'>{loop.deadline_days}日</b></span>
        <span className='hidden rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-1.5 py-0.5 font-mono text-[10px] text-[#57606a] md:block'>{loop.loop_id}</span>
      </div>
      <button
        type='button'
        onClick={onRestart}
        title='開始画面へ戻る'
        className='ml-1 inline-flex h-7 shrink-0 items-center gap-1 rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-2 text-[11px] font-semibold text-[#24292f] hover:bg-[#eaeef2]'
      >
        <RotateCcw className='size-3' />
        最初から
      </button>
    </header>
  )
}

/**
 * States plainly whether the contact numbers below come from real outreach.
 * Without this an owner reads simulated contacts as real sales activity.
 */
function RehearsalStrip({ loop }: { loop: V0Loop }) {
  const rehearsal = loop.mode === 'shadow' || loop.execution?.simulated === true
  const contacts = loop.execution?.totals?.contacts || 0
  if (!rehearsal) {
    return (
      <div className='flex shrink-0 items-center gap-2 border-b border-[#c3ddcf] bg-[#edf5f1] px-3 py-1.5'>
        <ShieldCheck className='size-3.5 shrink-0 text-[#276453]' />
        <p className='text-[11px] font-semibold text-[#276453]'>本番稼働中：実際のお客さんに連絡しています。</p>
      </div>
    )
  }
  return (
    <div className='flex shrink-0 items-center gap-2 border-b border-[#d4a72c]/50 bg-[#fff8c5] px-3 py-1.5'>
      <FlaskConical className='size-3.5 shrink-0 text-[#7d5d00]' />
      <p className='text-[11px] font-semibold text-[#7d5d00]'>
        お試し運転中：まだ誰にも連絡していません。
        {contacts > 0 && `以下の「接触${contacts.toLocaleString('ja-JP')}社」などの数字はコンピューター上の予測です。`}
      </p>
    </div>
  )
}

function KpiStrip({ kpi }: { kpi: KpiItem[] }) {
  return (
    <div className='grid shrink-0 grid-cols-2 gap-px border-b border-[#d0d7de] bg-[#d0d7de] sm:grid-cols-4 lg:grid-cols-7'>
      {kpi.map(item => (
        <div key={item.label} className='bg-white px-3 py-1.5'>
          <p className='text-[10px] font-medium text-[#57606a]'>{item.label}</p>
          <p
            className={[
              'mt-0.5 truncate text-[15px] font-semibold tabular-nums tracking-[-.02em]',
              item.tone === 'pos' ? 'text-[#1a7f37]' : item.tone === 'neg' ? 'text-[#cf222e]' : item.tone === 'warn' ? 'text-[#9a6700]' : 'text-[#24292f]',
            ].join(' ')}
          >
            {item.value}
          </p>
        </div>
      ))}
    </div>
  )
}

function StageRail({ loop, stageIndex, onNavigate }: { loop: V0Loop; stageIndex: number; onNavigate: (stage: StageName) => void }) {
  const killed = loop.stage === 'killed'
  const furthestIndex = killed
    ? STAGE_ORDER.length
    : loop.furthest_stage ? Math.max(0, STAGE_ORDER.indexOf(loop.furthest_stage)) : stageIndex
  return (
    <aside className='min-h-0 overflow-y-auto border-r border-[#d0d7de] bg-white p-2'>
      <div className='px-2 pb-1 pt-0.5'>
        <div className='flex items-center gap-1.5'>
          <Target className='size-3.5 text-[#ff4801]' />
          <p className='text-[10px] font-bold tracking-wide text-[#57606a]'>売上ループの進行</p>
        </div>
        <p className='mt-0.5 text-[9px] leading-4 text-[#8c959f]'>到達したステージはクリックで行き来できます</p>
      </div>
      <ol className='space-y-0.5'>
        {STAGE_ORDER.map((name, index) => {
          const meta = STAGE_META[name]
          const done = killed || index <= furthestIndex
          const current = !killed && index === stageIndex
          const clickable = done && !current
          return (
            <li key={name}>
              <button
                type='button'
                onClick={clickable ? () => onNavigate(name) : undefined}
                title={clickable ? `${meta.label}に戻る` : undefined}
                className={[
                  'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left',
                  current ? 'bg-[#fff4ef] ring-1 ring-[#ff7038]/60' : done ? 'hover:bg-[#f6f8fa]' : 'opacity-55',
                  clickable ? 'cursor-pointer' : 'cursor-default',
                ].join(' ')}
              >
                <span
                  className={[
                    'grid size-5 shrink-0 place-items-center rounded-full text-[10px] font-bold',
                    current ? 'bg-[#ff4801] text-white' : done ? 'bg-[#ddf4ff] text-[#0969da]' : 'bg-[#f6f8fa] text-[#8c959f]',
                  ].join(' ')}
                >
                  {done && !current ? '✓' : index + 1}
                </span>
                <div className='min-w-0'>
                  <p className={['truncate text-xs font-semibold', current ? 'text-[#24292f]' : 'text-[#57606a]'].join(' ')}>{meta.label}</p>
                </div>
              </button>
            </li>
          )
        })}
        {killed && (
          <li>
            <div className='flex items-center gap-2 rounded-md bg-[#ffebe9] px-2 py-1.5 ring-1 ring-[#ff818266]'>
              <span className='grid size-5 shrink-0 place-items-center rounded-full bg-[#cf222e] text-[10px] font-bold text-white'>終</span>
              <div className='min-w-0'>
                <p className='truncate text-xs font-semibold text-[#cf222e]'>やめた</p>
              </div>
            </div>
          </li>
        )}
      </ol>

      <div className='mt-3 space-y-2 border-t border-[#d0d7de] pt-2'>
        <div>
          <p className='px-2 text-[10px] font-semibold text-[#57606a]'>事業の目的</p>
          <p className='mt-1 line-clamp-4 rounded-md bg-[#f6f8fa] px-2 py-1.5 text-[11px] leading-4 text-[#24292f]'>{loop.intent}</p>
        </div>
        {loop.goal && (
          <div>
            <p className='px-2 text-[10px] font-semibold text-[#57606a]'>最終目的</p>
            <p className='mt-1 line-clamp-3 rounded-md bg-[#f6f8fa] px-2 py-1.5 text-[11px] leading-4 text-[#24292f]'>{loop.goal.final_goal}</p>
          </div>
        )}
        {loop.envelope && loop.envelope.status === 'approved' && (
          <div>
            <p className='px-2 text-[10px] font-semibold text-[#57606a]'>実行許可</p>
            <p className='mt-1 rounded-md bg-[#dafbe1] px-2 py-1.5 text-[10px] font-medium text-[#1a7f37]'>承認済み（{fmtDate(loop.envelope.approved_at)}）</p>
          </div>
        )}
      </div>
    </aside>
  )
}

function VerdictCard({ loop }: { loop: V0Loop }) {
  const decision = loop.decision
  if (!decision) return null
  const meta = VERDICT_META[decision.verdict]
  const kill = decision.verdict === 'KILL'
  const scale = decision.verdict === 'SCALE'
  return (
    <div
      className={[
        'rounded-lg border p-3',
        kill ? 'border-[#ff818266] bg-[#ffebe9]' : scale ? 'border-[#4ac26b]/50 bg-[#dafbe1]' : 'border-[#d4a72c]/60 bg-[#fff8c5]',
      ].join(' ')}
    >
      <div className='flex items-center gap-2'>
        <Scale className={['size-4', kill ? 'text-[#cf222e]' : scale ? 'text-[#1a7f37]' : 'text-[#9a6700]'].join(' ')} />
        <p className='text-xs font-bold text-[#24292f]'>最終判定</p>
        <span
          className={[
            'ml-auto rounded-md px-2 py-0.5 text-[10px] font-bold text-white',
            kill ? 'bg-[#cf222e]' : scale ? 'bg-[#1a7f37]' : 'bg-[#9a6700]',
          ].join(' ')}
        >
          {meta.label}
        </span>
      </div>
      <p className='mt-1 text-[10px] font-semibold text-[#57606a]'>{meta.note}</p>
      <p className='mt-2 line-clamp-4 text-[11px] leading-5 text-[#24292f]/85'>{decision.summary}</p>
      <div className='mt-2 grid grid-cols-3 gap-1.5'>
        <VerdictMetric label='売上' value={fmtYen(decision.revenue_yen)} tone={scale ? 'pos' : 'neutral'} />
        <VerdictMetric label='支出' value={fmtYen(decision.spend_yen)} tone='warn' />
        <VerdictMetric label='入金' value={`${decision.purchase_count}件`} tone={decision.purchase_count > 0 ? 'pos' : 'neutral'} />
      </div>
    </div>
  )
}

function VerdictMetric({ label, value, tone }: { label: string; value: string; tone: 'pos' | 'warn' | 'neutral' }) {
  return (
    <div className='rounded-md bg-white/80 px-1.5 py-1'>
      <p className='text-[9px] text-[#57606a]'>{label}</p>
      <p className={['text-[11px] font-bold tabular-nums', tone === 'pos' ? 'text-[#1a7f37]' : tone === 'warn' ? 'text-[#9a6700]' : 'text-[#24292f]'].join(' ')}>{value}</p>
    </div>
  )
}
function StageCard({
  loop, busy, onAdvance, onApprove, onDecide, onSelect, onResolve,
}: {
  loop: V0Loop
  busy: boolean
  onAdvance: () => void
  onApprove: () => void
  onDecide: () => void
  onSelect: (candidateId: string) => void
  onResolve: (name: string, source: string) => void
}) {
  const stage = loop.stage
  if (stage === 'goal') return <GoalCard loop={loop} busy={busy} onAdvance={onAdvance} />
  if (stage === 'plan') return <PlanCard loop={loop} busy={busy} onAdvance={onAdvance} onSelect={onSelect} />
  if (stage === 'constraint') return <ConstraintCard loop={loop} busy={busy} onAdvance={onAdvance} />
  if (stage === 'experiment') return <ExperimentCard loop={loop} busy={busy} onAdvance={onAdvance} />
  if (stage === 'envelope') return <EnvelopeCard loop={loop} busy={busy} onApprove={onApprove} onAdvance={onAdvance} />
  if (stage === 'capability') return <CapabilityCard loop={loop} busy={busy} onAdvance={onAdvance} onResolve={onResolve} />
  if (stage === 'execute') return <ExecuteCard loop={loop} busy={busy} onAdvance={onAdvance} />
  if (stage === 'observe') return <ObserveCard loop={loop} busy={busy} onAdvance={onAdvance} />
  if (stage === 'decide') return <DecideCard loop={loop} busy={busy} onDecide={onDecide} />
  if (stage === 'killed') return <KilledCard loop={loop} />
  return null
}

function CardShell({
  stage, title, hint, action, children,
}: {
  stage: StageName
  title: string
  hint?: string
  action?: ReactNode
  children: ReactNode
}) {
  const meta = STAGE_META[stage]
  return (
    <div className='rounded-lg border border-[#d0d7de] bg-white p-3'>
      <div className='flex items-center gap-2'>
        <p className='text-[10px] font-bold text-[#ff4801]'>{meta.label}</p>
        {hint && <span className='ml-auto truncate text-[10px] text-[#8c959f]'>{hint}</span>}
      </div>
      <h3 className='mt-1 text-[15px] font-bold tracking-[-.015em]'>{title}</h3>
      <div className='mt-2.5'>{children}</div>
      {action && <div className='mt-3.5'>{action}</div>}
    </div>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className='min-w-0 rounded-md bg-[#f6f8fa] px-2.5 py-2'>
      <p className='text-[9px] font-semibold text-[#57606a]'>{label}</p>
      <p className='mt-0.5 truncate text-[13px] font-semibold text-[#24292f]'>{value}</p>
    </div>
  )
}

function DetailBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className='mt-2.5 rounded-md border border-[#d0d7de] px-3 py-2'>
      <p className='text-[9px] font-semibold text-[#57606a]'>{label}</p>
      <p className='mt-1 whitespace-pre-wrap text-[13px] leading-5 text-[#24292f]'>{value}</p>
    </div>
  )
}


function GoalCard({ loop, busy, onAdvance }: { loop: V0Loop; busy: boolean; onAdvance: () => void }) {
  const goal = loop.goal
  if (!goal) return null
  return (
    <CardShell
      stage='goal'
      title='目標を数値化する'
      hint='原文は実行詳細へ'
      action={
        <Button onClick={onAdvance} disabled={busy} className='rounded-md bg-[#24292f] text-white hover:bg-[#1f2328]'>
          {busy ? <LoaderCircle className='size-4 animate-spin' /> : <ArrowRight className='size-4' />}
          事業案を作る
        </Button>
      }
    >
      <div className='grid gap-2 sm:grid-cols-2'>
        <Fact label='最終目的' value={goal.final_goal} />
        <Fact label='中間目的' value={goal.intermediate_goal} />
        <Fact label='予算上限' value={fmtYen(goal.budget_yen)} />
        <Fact label='期間' value={`${goal.deadline_days}日`} />
      </div>
      <DetailBlock label='発言（原文）' value={goal.intent} />
      <DetailBlock label='人間介入' value={goal.human_involvement} />
    </CardShell>
  )
}

function PlanCard({ loop, busy, onAdvance, onSelect }: { loop: V0Loop; busy: boolean; onAdvance: () => void; onSelect: (candidateId: string) => void }) {
  const selected = loop.selected_business
  return (
    <CardShell
      stage='plan'
      title='事業候補から1つを選ぶ'
      hint='候補を選ぶと制約・実験・許可まで再構築'
      action={
        selected ? (
          <Button onClick={onAdvance} disabled={busy} className='rounded-md bg-[#24292f] text-white hover:bg-[#1f2328]'>
            {busy ? <LoaderCircle className='size-4 animate-spin' /> : <ArrowRight className='size-4' />}
            制約を確認
          </Button>
        ) : (
          <Button disabled className='w-full rounded-md bg-[#d0d7de] text-[#57606a]'>
            候補を選択してください
          </Button>
        )
      }
    >
      {selected && (
        <p className='mb-2.5 flex items-center gap-2 rounded-md bg-[#fff4ef] px-3 py-2 text-xs text-[#24292f]'>
          <CheckCircle2 className='size-3.5 shrink-0 text-[#ff4801]' />
          現在の選択：<b>{selected.name}</b>
          <span className='ml-auto text-[10px] text-[#8c959f]'>別の候補を選ぶと未承認の下流を再構築します</span>
        </p>
      )}
      <div className='grid gap-2 sm:grid-cols-2 xl:grid-cols-3'>
        {loop.candidates.map((candidate, index) => {
          const isSelected = selected?.id === candidate.id
          return (
            <button
              key={candidate.id}
              type='button'
              onClick={() => onSelect(candidate.id)}
              disabled={busy || isSelected}
              title={isSelected ? '選択済み' : 'この事業を選ぶ'}
              className={[
                'rounded-md border px-3 py-2.5 text-left',
                isSelected
                  ? 'cursor-default border-[#ff4801] bg-[#fff4ef] ring-1 ring-[#ff7038]/50'
                  : 'cursor-pointer border-[#d0d7de] hover:border-[#ff7038]/70 hover:bg-[#fffaf6]',
                busy ? 'cursor-wait opacity-70' : '',
              ].join(' ')}
            >
              <div className='flex items-center gap-1.5'>
                <span className={['grid size-4 place-items-center rounded-full text-[8px] font-semibold', isSelected ? 'bg-[#ff4801] text-white' : 'bg-[#24292f] text-white'].join(' ')}>{index + 1}</span>
                <span className={['ml-auto rounded-full px-2 py-0.5 text-[9px] font-semibold', isSelected ? 'bg-[#ff4801] text-white' : 'bg-[#f6f8fa] text-[#57606a]'].join(' ')}>
                  {isSelected ? '選択済み' : '選択する'}
                </span>
              </div>
              <p className='mt-1.5 text-sm font-semibold leading-5'>{candidate.name}</p>
              <p className='mt-1 text-[11px] leading-4 text-[#57606a]'>{candidate.summary}</p>
              <div className='mt-1.5 flex flex-wrap gap-1'>
                <span className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>{fmtYen(candidate.price_yen)}</span>
                <span className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>納品{candidate.delivery_hours}h</span>
                <span className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>
                  {candidate.channels.map(channel => CHANNEL_LABELS[channel] || channel).join('・')}
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </CardShell>
  )
}

function ConstraintCard({ loop, busy, onAdvance }: { loop: V0Loop; busy: boolean; onAdvance: () => void }) {
  return (
    <CardShell
      stage='constraint'
      title='実行できないことを先に確認する'
      hint='法律・資金・免許・ライセンス'
      action={
        <Button onClick={onAdvance} disabled={busy} className='rounded-md bg-[#24292f] text-white hover:bg-[#1f2328]'>
          {busy ? <LoaderCircle className='size-4 animate-spin' /> : <ArrowRight className='size-4' />}
          実験を設計
        </Button>
      }
    >
      <div className='grid gap-2 sm:grid-cols-2'>
        {loop.constraint_checks.map(check => (
          <div key={check.id} className='flex items-start gap-2.5 rounded-md border border-[#d0d7de] px-3 py-2'>
            <CheckCircle2 className='mt-0.5 size-4 shrink-0 text-[#1a7f37]' />
            <div className='min-w-0'>
              <p className='text-sm font-semibold'>{check.name}</p>
              <p className='mt-0.5 text-[11px] leading-4 text-[#57606a]'>{check.detail}</p>
              <p className='mt-1 text-[10px] text-[#6e7781]'>{check.note}</p>
            </div>
          </div>
        ))}
      </div>
    </CardShell>
  )
}

function ExperimentCard({ loop, busy, onAdvance }: { loop: V0Loop; busy: boolean; onAdvance: () => void }) {
  return (
    <CardShell
      stage='experiment'
      title='仮説を複数作り、少額ずつ試す'
      hint='1仮説に寄せ切らない'
      action={
        <Button onClick={onAdvance} disabled={busy} className='rounded-md bg-[#24292f] text-white hover:bg-[#1f2328]'>
          {busy ? <LoaderCircle className='size-4 animate-spin' /> : <ArrowRight className='size-4' />}
          実行許可を作成
        </Button>
      }
    >
      <div className='grid gap-2 lg:grid-cols-3'>
        {loop.experiments.map(exp => (
          <div key={exp.id} className='rounded-md border border-[#d0d7de] px-3 py-2.5'>
            <div className='flex items-center gap-1.5'>
              <FlaskConical className='size-3.5 shrink-0 text-[#ff4801]' />
              <p className='text-xs font-semibold leading-5'>{exp.label}</p>
            </div>
            <div className='mt-1.5 flex flex-wrap gap-1'>
              <span className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>{CHANNEL_LABELS[exp.channel] || exp.channel}</span>
              <span className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>{exp.target_count}社</span>
              <span className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>{fmtYen(exp.budget_yen)}</span>
            </div>
            <p className='mt-1.5 text-[10px] font-bold text-[#24292f]'>戦術：{exp.tactic}</p>
            <p className='mt-0.5 line-clamp-3 text-[10px] leading-4 text-[#57606a]'>{exp.tactic_detail}</p>
            <p className='mt-1 text-[9px] leading-4 text-[#8c959f]'>狙い：{exp.rationale}</p>
          </div>
        ))}
      </div>
    </CardShell>
  )
}

function EnvelopeCard({ loop, busy, onApprove, onAdvance }: { loop: V0Loop; busy: boolean; onApprove: () => void; onAdvance: () => void }) {
  const envelope = loop.envelope
  if (!envelope) return null
  const approved = Boolean(envelope.approved_at)
  return (
    <CardShell
      stage='envelope'
      title='範囲と上限を決め、一度だけ承認する'
      hint='この営業ひとまとまりへの許可'
      action={
        approved ? (
          <>
          <div className='flex items-center gap-2 rounded-md bg-[#dafbe1] px-3 py-2 text-sm font-semibold text-[#1a7f37]'>
            <CheckCircle2 className='size-4' />
            承認済み（{fmtDate(envelope.approved_at)}）
          </div>
          <Button onClick={onAdvance} disabled={busy} className='h-10 w-full rounded-md bg-[#24292f] text-white hover:bg-[#1f2328]'>
            {busy ? <LoaderCircle className='size-4 animate-spin' /> : <ArrowRight className='size-4' />}
            {busy ? '実行中' : '実行へ進む'}
          </Button>
          </>
        ) : (
          <Button onClick={onApprove} disabled={busy} className='h-11 w-full rounded-md bg-[#ff6b32] text-white hover:bg-[#ff4801]'>
            {busy ? <LoaderCircle className='size-4 animate-spin' /> : <ShieldCheck className='size-4' />}
            {busy ? '実行中' : 'この内容で営業を許可する'}
          </Button>
        )
      }
    >
      <p className='rounded-md bg-[#f6f8fa] px-3 py-2.5 text-[13px] leading-5 text-[#24292f]'>{envelope.summary}</p>
      <div className='mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4'>
        <Fact label='接触チャネル' value={envelope.channel.map(channel => CHANNEL_LABELS[channel] || channel).join('・')} />
        <Fact label='接触上限' value={`${envelope.target_count_cap}社`} />
        <Fact label='予算上限' value={fmtYen(envelope.budget_cap_yen)} />
        <Fact label='期間' value={`${Math.round(envelope.period_hours / 24)}日`} />
      </div>
      <div className='mt-3 rounded-md border border-[#d0d7de] px-3 py-2'>
        <p className='text-[10px] font-semibold text-[#57606a]'>禁止事項</p>
        <div className='mt-1.5 flex flex-wrap gap-1.5'>
          {envelope.prohibited.map(item => (
            <span key={item} className='rounded-md bg-[#ffebe9] px-2 py-0.5 text-[10px] font-medium text-[#cf222e]'>{item}</span>
          ))}
        </div>
      </div>
    </CardShell>
  )
}
type PartKind = 'git' | 'api' | 'mcp' | 'build'

const PART_LIBRARY: Array<{ name: string; source: string; note: string; kind: PartKind }> = [
  { name: '営業メール送信', source: 'GitHub OSS', note: 'nodemailer / Resend 等を組み込み、許可された範囲内で一括送信する', kind: 'git' },
  { name: '企業リスト取得', source: 'API', note: 'Google Maps / オープンデータから対象業種の企業情報を収集する', kind: 'api' },
  { name: 'マーケティングLP作成', source: '自作・OSS', note: '商品ページを静的HTMLで生成し、効果測定タグを埋め込む', kind: 'build' },
  { name: '決済リンク生成', source: 'API', note: 'Stripe Payment Link で請求ごとの支払いURLを作成する', kind: 'api' },
  { name: '請求書生成', source: '自作・OSS', note: 'PDF請求書を自動生成し、メールへ添付する', kind: 'build' },
  { name: '入金確認Webhook', source: 'API', note: 'Stripe Webhook で支払い完了を検知し台帳へ通知する', kind: 'api' },
  { name: 'Webスクレイピング', source: 'GitHub OSS', note: 'Playwright 等で公開ページから必要情報を抽出する', kind: 'git' },
  { name: 'フォーム営業', source: 'MCP', note: '問い合わせフォームの特定・入力・送信を自動化（送信前に人間承認）', kind: 'mcp' },
  { name: '架電営業', source: 'API', note: '通話発信APIと連携し、応答結果を台帳へ記録する', kind: 'api' },
]

const PART_SOURCE_COLOR: Record<PartKind, string> = {
  git: 'bg-[#ddf4ff] text-[#0969da]',
  api: 'bg-[#fbefff] text-[#8250df]',
  mcp: 'bg-[#fff8c5] text-[#9a6700]',
  build: 'bg-[#f6f8fa] text-[#57606a]',
}

function PartIcon({ kind }: { kind: PartKind }) {
  if (kind === 'git') return <GitBranch className='mt-0.5 size-4 shrink-0 text-[#0969da]' />
  if (kind === 'api') return <Plug className='mt-0.5 size-4 shrink-0 text-[#8250df]' />
  if (kind === 'mcp') return <Puzzle className='mt-0.5 size-4 shrink-0 text-[#9a6700]' />
  return <Wrench className='mt-0.5 size-4 shrink-0 text-[#57606a]' />
}

function CapabilityCard({ loop, busy, onAdvance, onResolve }: {
  loop: V0Loop
  busy: boolean
  onAdvance: () => void
  onResolve: (name: string, source: string) => void
}) {
  const [query, setQuery] = useState('')
  const [scanning, setScanning] = useState(false)
  const [candidates, setCandidates] = useState<Array<{ name: string; source: string; note: string; kind: PartKind }> | null>(null)

  const startScan = () => {
    setScanning(true)
    setCandidates(null)
    const q = query.trim().toLowerCase()
    const have = new Set(loop.capabilities.map(cap => cap.name))
    window.setTimeout(() => {
      setCandidates(
        PART_LIBRARY.filter(part =>
          q === '' ||
          part.name.toLowerCase().includes(q) ||
          part.note.toLowerCase().includes(q)
        ).filter(part => !have.has(part.name))
      )
      setScanning(false)
    }, 600)
  }

  const adopt = (part: { name: string; source: string }) => {
    setCandidates(prev => prev ? prev.filter(item => item.name !== part.name) : prev)
    onResolve(part.name, `${part.source} から確保`)
  }

  return (
    <CardShell
      stage='capability'
      title='必要な部品を確保する'
      hint='既存能力・API・OSS・自作の順'
      action={
        <Button onClick={onAdvance} disabled={busy} className='rounded-md bg-[#24292f] text-white hover:bg-[#1f2328]'>
          {busy ? <LoaderCircle className='size-4 animate-spin' /> : <ArrowRight className='size-4' />}
          実行する
        </Button>
      }
    >
      <div className='grid gap-2 sm:grid-cols-2'>
        {loop.capabilities.map(cap => (
          <div key={cap.id} className='flex items-start gap-2.5 rounded-md border border-[#d0d7de] px-3 py-2'>
            <Building2 className='mt-0.5 size-4 shrink-0 text-[#ff4801]' />
            <div className='min-w-0 flex-1'>
              <div className='flex items-center gap-2'>
                <p className='text-sm font-semibold'>{cap.name}</p>
                <span
                  className={[
                    'ml-auto shrink-0 rounded-full px-2 py-0.5 text-[9px] font-semibold',
                    cap.status === '人間操作'
                      ? 'bg-[#f6f8fa] text-[#57606a]'
                      : cap.status === '要承認'
                        ? 'bg-[#fff8c5] text-[#9a6700]'
                        : 'bg-[#dafbe1] text-[#1a7f37]',
                  ].join(' ')}
                >
                  {cap.status}
                </span>
              </div>
              <p className='mt-0.5 text-[11px] leading-4 text-[#57606a]'>{cap.note}</p>
            </div>
          </div>
        ))}
      </div>

      <div className='mt-3 rounded-md border border-[#d0d7de] bg-[#f6f8fa] p-2.5'>
        <div className='flex items-center gap-2'>
          <GitBranch className='size-4 text-[#0969da]' />
          <p className='text-xs font-bold text-[#24292f]'>不足している部品をGitHub等から拾う</p>
          <span className='ml-auto text-[10px] text-[#57606a]'>OSS・API・MCP・自作を比較して確保</span>
        </div>
        <div className='mt-2 flex gap-2'>
          <input
            value={query}
            onChange={event => setQuery(event.target.value)}
            onKeyDown={event => { if (event.key === 'Enter') startScan() }}
            placeholder='例：営業メール、決済、スクレイピング'
            className='h-9 min-w-0 flex-1 rounded-md border border-[#d0d7de] bg-white px-2.5 text-xs text-[#24292f] outline-none placeholder:text-[#8c959f] focus:border-[#ff7038]'
          />
          <Button onClick={startScan} disabled={busy || scanning} className='h-9 shrink-0 rounded-md bg-[#0969da] text-white hover:bg-[#0b5ec2]'>
            {scanning ? <LoaderCircle className='size-3.5 animate-spin' /> : <Search className='size-3.5' />}
            検索
          </Button>
        </div>
        {scanning && (
          <p className='mt-2 flex items-center gap-1.5 text-[11px] text-[#57606a]'>
            <LoaderCircle className='size-3 animate-spin' />
            GitHub / npm / API のライセンスと利用規約を確認しながら検索中…
          </p>
        )}
        {candidates && !scanning && (
          <div className='mt-2 space-y-1.5'>
            {candidates.length === 0 && (
              <p className='rounded-md border border-dashed border-[#d0d7de] px-3 py-2 text-center text-[11px] text-[#8c959f]'>
                該当する不足部品はありません（既に確保済みです）
              </p>
            )}
            {candidates.map(part => (
              <div key={part.name} className='flex items-center gap-2 rounded-md border border-[#d0d7de] bg-white px-2.5 py-2'>
                <PartIcon kind={part.kind} />
                <div className='min-w-0 flex-1'>
                  <div className='flex items-center gap-2'>
                    <p className='truncate text-xs font-semibold text-[#24292f]'>{part.name}</p>
                    <span className={['shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-semibold', PART_SOURCE_COLOR[part.kind]].join(' ')}>
                      {part.source}
                    </span>
                  </div>
                  <p className='mt-0.5 truncate text-[10px] text-[#57606a]'>{part.note}</p>
                </div>
                <Button onClick={() => adopt(part)} disabled={busy} size='sm' className='h-7 shrink-0 rounded-md bg-[#1a7f37] px-2 text-[10px] text-white hover:bg-[#116932]'>
                  <PackagePlus className='size-3' />
                  採用して部品化
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </CardShell>
  )
}

function ExecuteCard({ loop, busy, onAdvance }: { loop: V0Loop; busy: boolean; onAdvance: () => void }) {
  const execution = loop.execution
  if (!execution) return null
  return (
    <CardShell
      stage='execute'
      title='承認された範囲内で接触する'
      hint='外部接触は未実行・シミュレーション'
      action={
        <Button onClick={onAdvance} disabled={busy} className='rounded-md bg-[#24292f] text-white hover:bg-[#1f2328]'>
          {busy ? <LoaderCircle className='size-4 animate-spin' /> : <ArrowRight className='size-4' />}
          観測へ
        </Button>
      }
    >
      <p className='rounded-md bg-[#fff8c5] px-3 py-2 text-xs leading-5 text-[#9a6700]'>{execution.simulated_note}</p>
      <div className='mt-2.5 grid grid-cols-2 gap-2 sm:grid-cols-6'>
        <Fact label='接触' value={`${execution.totals.contacts}件`} />
        <Fact label='返信' value={`${execution.totals.replied}件`} />
        <Fact label='興味' value={`${execution.totals.interested}件`} />
        <Fact label='購入反応' value={`${execution.totals.purchases}件`} />
        <Fact label='費用' value={fmtYen(execution.totals.cost_yen)} />
        <Fact label='売上（シミュ）' value={fmtYen(execution.totals.revenue_yen)} />
      </div>
      <ExecutionDetailTable execution={execution} />
    </CardShell>
  )
}

function ExecutionDetailTable({ execution }: { execution: NonNullable<V0Loop['execution']> }) {
  return (
    <div className='mt-2.5 overflow-x-auto'>
      <table className='w-full min-w-[760px] text-left text-xs'>
        <thead>
          <tr className='border-b border-[#d0d7de] text-[10px] font-semibold text-[#57606a]'>
            <th className='py-1.5 pr-2'>仮説</th>
            <th className='py-1.5 pr-2'>戦術</th>
            <th className='py-1.5 pr-2'>接触</th>
            <th className='py-1.5 pr-2'>返信</th>
            <th className='py-1.5 pr-2'>興味</th>
            <th className='py-1.5 pr-2'>購入</th>
            <th className='py-1.5 pr-2'>費用（内訳）</th>
            <th className='py-1.5'>売上</th>
          </tr>
        </thead>
        <tbody>
          {execution.experiments.map(result => (
            <tr key={result.experiment_id} className='border-b border-[#d0d7de] align-top text-[#24292f]'>
              <td className='py-2 pr-2 font-medium'>{result.label || result.experiment_id}</td>
              <td className='py-2 pr-2 text-[10px] leading-4 text-[#57606a]'>{result.tactic || CHANNEL_LABELS[result.channel] || result.channel}</td>
              <td className='py-2 pr-2 tabular-nums'>{result.contacts}</td>
              <td className='py-2 pr-2 tabular-nums'>{result.replied ?? result.responses}</td>
              <td className='py-2 pr-2 tabular-nums'>{result.interested ?? 0}</td>
              <td className='py-2 pr-2 tabular-nums'>{result.purchases}</td>
              <td className='py-2 pr-2'>
                <span className='font-medium tabular-nums'>{fmtYen(result.cost_yen)}</span>
                <span className='block text-[9px] leading-4 text-[#8c959f]'>
                  {(result.cost_breakdown || []).map(item => `${item.item} ${fmtYen(item.amount_yen)}`).join(' / ')}
                </span>
              </td>
              <td className='py-2 font-medium tabular-nums'>{fmtYen(result.revenue_yen)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className='text-[10px] font-bold text-[#24292f]'>
            <td className='py-2 pr-2'>合計</td>
            <td className='py-2 pr-2' />
            <td className='py-2 pr-2 tabular-nums'>{execution.totals.contacts}</td>
            <td className='py-2 pr-2 tabular-nums'>{execution.totals.replied}</td>
            <td className='py-2 pr-2 tabular-nums'>{execution.totals.interested}</td>
            <td className='py-2 pr-2 tabular-nums'>{execution.totals.purchases}</td>
            <td className='py-2 pr-2 tabular-nums'>{fmtYen(execution.totals.cost_yen)}</td>
            <td className='py-2 tabular-nums'>{fmtYen(execution.totals.revenue_yen)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

function ObserveCard({ loop, busy, onAdvance }: { loop: V0Loop; busy: boolean; onAdvance: () => void }) {
  const totals = loop.execution?.totals
  return (
    <CardShell
      stage='observe'
      title='接触結果を台帳に記録する'
      hint='実入金は人間が登録'
      action={
        <Button onClick={onAdvance} disabled={busy} className='rounded-md bg-[#24292f] text-white hover:bg-[#1f2328]'>
          {busy ? <LoaderCircle className='size-4 animate-spin' /> : <ArrowRight className='size-4' />}
          判定へ
        </Button>
      }
    >
      <div className='grid grid-cols-2 gap-2 sm:grid-cols-6'>
        <Fact label='接触' value={`${totals?.contacts ?? 0}件`} />
        <Fact label='返信' value={`${totals?.replied ?? 0}件`} />
        <Fact label='興味' value={`${totals?.interested ?? 0}件`} />
        <Fact label='購入反応' value={`${totals?.purchases ?? 0}件`} />
        <Fact label='費用' value={fmtYen(totals?.cost_yen ?? 0)} />
        <Fact label='売上（シミュ）' value={fmtYen(totals?.revenue_yen ?? 0)} />
      </div>
      {(totals?.cost_breakdown ?? []).length > 0 && (
        <div className='mt-2.5 flex flex-wrap items-center gap-1.5'>
          <span className='text-[10px] font-semibold text-[#57606a]'>費用内訳：</span>
          {(totals?.cost_breakdown ?? []).map(item => (
            <span key={item.item} className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>
              {item.item} {fmtYen(item.amount_yen)}
            </span>
          ))}
        </div>
      )}
      {loop.execution && <ExecutionDetailTable execution={loop.execution} />}
      <p className='mt-2.5 rounded-md bg-[#f6f8fa] px-3 py-2 text-[11px] leading-5 text-[#57606a]'>
        シミュレーション上の売上は実入金に数えません。実入金は右の台帳から人間が登録し、収支判定に反映されます。
      </p>
    </CardShell>
  )
}

function ExecutionSummary({ loop }: { loop: V0Loop }) {
  const totals = loop.execution?.totals
  if (!totals) return null
  return (
    <div className='mt-3 rounded-md border border-[#d0d7de] px-3 py-2'>
      <p className='text-[10px] font-semibold text-[#57606a]'>実行結果（シミュレーション）</p>
      <div className='mt-1 flex flex-wrap gap-1.5'>
        <span className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>接触 {totals.contacts}件</span>
        <span className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>返信 {totals.replied ?? 0}件</span>
        <span className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>興味 {totals.interested ?? 0}件</span>
        <span className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>購入反応 {totals.purchases}件</span>
        <span className='rounded-md bg-[#f6f8fa] px-2 py-0.5 text-[10px] font-medium text-[#57606a]'>費用 {fmtYen(totals.cost_yen)}</span>
      </div>
    </div>
  )
}

function DecideCard({ loop, busy, onDecide }: { loop: V0Loop; busy: boolean; onDecide: () => void }) {
  const decision = loop.decision
  if (decision) {
    const meta = VERDICT_META[decision.verdict]
    return (
      <CardShell stage='decide' title='判定を確定した'>
        <div className='rounded-lg border border-[#d0d7de] p-3'>
          <div className='flex items-center gap-3'>
            <span className='grid size-11 shrink-0 place-items-center rounded-md text-[10px] font-bold leading-tight text-white' style={{ backgroundColor: meta.color }}>
              判定
            </span>
            <div>
              <p className='text-lg font-semibold'>{meta.label}</p>
              <p className='text-xs text-[#57606a]'>{meta.note}</p>
            </div>
          </div>
          <p className='mt-3 rounded-md bg-[#f6f8fa] px-3 py-2 text-[13px] leading-5 text-[#24292f]'>{decision.summary}</p>
          <div className='mt-3 grid grid-cols-3 gap-2'>
            <Fact label='支出' value={fmtYen(decision.spend_yen)} />
            <Fact label='売上' value={fmtYen(decision.revenue_yen)} />
            <Fact label='実入金' value={`${decision.purchase_count}件`} />
          </div>
        </div>
        <ExecutionSummary loop={loop} />
        {loop.stage !== 'killed' && (
          <div className='mt-3'>
            <Button onClick={onDecide} disabled={busy} variant='outline' className='w-full rounded-md border-[#d0d7de] text-[#24292f] hover:bg-[#f6f8fa]'>
              {busy ? <LoaderCircle className='size-4 animate-spin' /> : <Scale className='size-4' />}
              入金を反映して再判定
            </Button>
          </div>
        )}
        {decision.verdict !== 'KILL' && (
          <p className='mt-3 rounded-md bg-[#f6f8fa] px-3 py-2 text-[11px] leading-5 text-[#57606a]'>
            判定後も人間はいつでも事業を停止できます。右の台帳から「事業を停止」を押してください。
          </p>
        )}
      </CardShell>
    )
  }
  return (
    <CardShell
      stage='decide'
      title='収支を見て判定する'
      hint='伸ばす / やり方を変える / やめる'
      action={
        <Button onClick={onDecide} disabled={busy} className='h-11 w-full rounded-md bg-[#ff6b32] text-white hover:bg-[#ff4801]'>
          {busy ? <LoaderCircle className='size-4 animate-spin' /> : <Scale className='size-4' />}
          {busy ? '判定中' : '判定を確定'}
        </Button>
      }
    >
      <div className='grid grid-cols-2 gap-2 sm:grid-cols-4'>
        <Fact label='累計費用' value={fmtYen(loop.ledger.cost_yen)} />
        <Fact label='実入金' value={`${loop.ledger.orders.length}件`} />
        <Fact label='実売上' value={fmtYen(loop.ledger.revenue_yen)} />
        <Fact label='損益' value={fmtYen(loop.ledger.revenue_yen - loop.ledger.cost_yen)} />
      </div>
      <ExecutionSummary loop={loop} />
      <p className='mt-3 rounded-md bg-[#f6f8fa] px-3 py-2 text-[11px] leading-5 text-[#57606a]'>
        入金が2件以上あって黒字なら「伸ばす」、入金1件以下なら「やり方を変える」。予算を使い切った場合は「やめる」になります。
      </p>
    </CardShell>
  )
}

function KilledCard({ loop }: { loop: V0Loop }) {
  const decision = loop.decision
  return (
    <CardShell stage='killed' title='この事業は停止しました'>
      <div className='rounded-lg border border-red-100 bg-[#ffebe9] p-3'>
        <div className='flex items-center gap-3'>
          <span className='grid size-11 shrink-0 place-items-center rounded-md bg-[#b3261e] text-xs font-bold text-white'>停止</span>
          <div>
            <p className='text-lg font-semibold text-[#b3261e]'>事業停止</p>
            <p className='text-xs text-[#9a6700]'>条件を満たさないため、これ以上の実行は行いません</p>
          </div>
        </div>
        <p className='mt-3 rounded-md bg-white px-3 py-2 text-[13px] leading-5 text-[#24292f]'>{decision?.summary ?? ''}</p>
        <div className='mt-3 grid grid-cols-3 gap-2'>
          <Fact label='支出' value={fmtYen(loop.ledger.cost_yen)} />
          <Fact label='実売上' value={fmtYen(loop.ledger.revenue_yen)} />
          <Fact label='実入金' value={`${loop.ledger.orders.length}件`} />
        </div>
      </div>
      <ExecutionSummary loop={loop} />
      <p className='mt-3 text-[11px] leading-5 text-[#57606a]'>
        次の事業を始めるには、画面を再読み込みして新しい目的を入力してください。判定の証跡は保存されています。
      </p>
    </CardShell>
  )
}
function DailyCheckinPanel({ loop, busy, onDailyConfirm }: { loop: V0Loop; busy: boolean; onDailyConfirm: (note: string) => void }) {
  const [note, setNote] = useState('')
  const checkins = loop.checkins || []
  const last = checkins.length > 0 ? checkins[checkins.length - 1] : null
  const submit = () => {
    onDailyConfirm(note)
    setNote('')
  }
  return (
    <div className='rounded-lg border border-[#d0d7de] bg-white p-3'>
      <div className='flex items-center gap-2'>
        <CheckCircle2 className='size-4 text-[#ff4801]' />
        <p className='text-xs font-bold text-[#24292f]'>デイリー確認（捺印）</p>
      </div>
      <p className='mt-1 text-[10px] leading-4 text-[#57606a]'>
        今日の画面内容を確認した証跡を残します。実行・入金・判定の確認に使ってください。
      </p>
      {last && (
        <p className='mt-1.5 flex items-center gap-1 rounded-md bg-[#dafbe1] px-2 py-1 text-[10px] font-medium text-[#1a7f37]'>
          <CheckCircle2 className='size-3 shrink-0' />
          最終捺印：{fmtDate(last.confirmed_at)}（{STAGE_META[last.stage as StageName]?.label ?? last.stage}）
        </p>
      )}
      <input
        value={note}
        onChange={event => setNote(event.target.value)}
        onKeyDown={event => { if (event.key === 'Enter') submit() }}
        placeholder='確認メモ（任意）'
        className='mt-2 h-8 w-full rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-2 text-xs text-[#24292f] outline-none placeholder:text-[#8c959f] focus:border-[#ff7038] focus:bg-white'
      />
      <Button onClick={submit} disabled={busy} className='mt-2 h-8 w-full rounded-md bg-[#24292f] text-[11px] text-white hover:bg-[#1f2328]'>
        {busy ? <LoaderCircle className='size-3 animate-spin' /> : <CheckCircle2 className='size-3.5' />}
        確認済みにする
      </Button>
      {checkins.length > 0 && (
        <div className='mt-2 max-h-28 space-y-1 overflow-y-auto border-t border-[#d0d7de] pt-2'>
          {[...checkins].reverse().map(checkin => (
            <div key={checkin.id} className='flex items-start gap-1.5 text-[10px]'>
              <span className='mt-0.5 grid size-3.5 shrink-0 place-items-center rounded-full bg-[#dafbe1] text-[7px] font-bold text-[#1a7f37]'>✓</span>
              <div className='min-w-0'>
                <p className='text-[#24292f]'>
                  {fmtDate(checkin.confirmed_at)} · {STAGE_META[checkin.stage as StageName]?.label ?? checkin.stage}
                </p>
                {checkin.note && <p className='truncate text-[#57606a]'>{checkin.note}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function LedgerPanel({
  loop, busy,
  orderCompany, setOrderCompany, orderAmount, setOrderAmount,
  killReason, setKillReason,
  onRecordOrder, onDeliver, onKill,
}: {
  loop: V0Loop
  busy: boolean
  orderCompany: string
  setOrderCompany: (value: string) => void
  orderAmount: string
  setOrderAmount: (value: string) => void
  killReason: string
  setKillReason: (value: string) => void
  onRecordOrder: () => void
  onDeliver: (orderId: string) => void
  onKill: () => void
}) {
  const profit = loop.ledger.revenue_yen - loop.ledger.cost_yen
  const orders = loop.ledger.orders
  const killed = loop.stage === 'killed'
  return (
    <>
      <div className='flex items-center gap-3'>
        <img src='/ui-assets/decision-action-v1.png' alt='相談判断' className='size-10 rounded-md object-cover' />
        <div>
          <p className='text-sm font-semibold'>収支台帳</p>
          <p className='text-xs text-[#57606a]'>実入金は人間が登録します</p>
        </div>
      </div>

      <div className='mt-3 grid grid-cols-3 gap-2'>
        <LedgerMetric label='費用' value={fmtYen(loop.ledger.cost_yen)} tone='neutral' />
        <LedgerMetric label='売上' value={fmtYen(loop.ledger.revenue_yen)} tone='positive' />
        <LedgerMetric label='損益' value={fmtYen(profit)} tone={profit >= 0 ? 'positive' : 'negative'} />
      </div>

      <div className='mt-3 rounded-lg border border-[#d0d7de] bg-white p-3'>
        <p className='text-xs font-semibold text-[#24292f]'>注文（実入金）</p>
        <div className='mt-3 space-y-2'>
          {orders.length === 0 && (
            <p className='rounded-md border border-dashed border-[#d0d7de] px-3 py-2.5 text-center text-xs text-[#8c959f]'>まだ実入金はありません</p>
          )}
          {orders.map(order => (
            <div key={order.order_id} className='rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-3 py-2'>
              <div className='flex items-center gap-2'>
                <HandCoins className='size-3.5 shrink-0 text-[#1a7f37]' />
                <p className='min-w-0 flex-1 truncate text-xs font-semibold'>{order.company}</p>
                <p className='shrink-0 text-xs font-semibold text-[#1a7f37]'>{fmtYen(order.amount_yen)}</p>
              </div>
              <div className='mt-1.5 flex items-center gap-2'>
                <span className='text-[10px] text-[#8c959f]'>{fmtDate(order.recorded_at)}</span>
                {order.delivered ? (
                  <span className='ml-auto inline-flex items-center gap-1 rounded-full bg-[#dafbe1] px-2 py-0.5 text-[9px] font-semibold text-[#1a7f37]'>
                    <CheckCircle2 className='size-3' />
                    納品済み
                  </span>
                ) : (
                  <Button
                    onClick={() => onDeliver(order.order_id)}
                    disabled={busy}
                    variant='outline'
                    className='ml-auto h-6 rounded-lg border-[#d0d7de] bg-white px-2 text-[10px] text-[#24292f] hover:bg-[#f6f8fa] hover:text-[#24292f]'
                  >
                    納品する
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className='mt-3 border-t border-[#d0d7de] pt-3'>
          <p className='text-[10px] font-semibold text-[#57606a]'>実入金の登録（人間操作）</p>
          <div className='mt-2 grid grid-cols-[1fr_90px] gap-2'>
            <input
              value={orderCompany}
              onChange={event => setOrderCompany(event.target.value)}
              placeholder='注文企業名'
              className='h-9 min-w-0 rounded-lg border border-[#d0d7de] bg-[#f6f8fa] px-2.5 text-xs text-[#24292f] outline-none placeholder:text-[#8c959f] focus:border-[#ff7038] focus:bg-white'
            />
            <input
              value={orderAmount}
              onChange={event => setOrderAmount(event.target.value)}
              placeholder='金額'
              inputMode='numeric'
              className='h-9 min-w-0 rounded-lg border border-[#d0d7de] bg-[#f6f8fa] px-2.5 text-xs text-[#24292f] outline-none placeholder:text-[#8c959f] focus:border-[#ff7038] focus:bg-white'
            />
          </div>
          <Button onClick={onRecordOrder} disabled={busy} className='mt-2 h-9 w-full rounded-lg bg-[#ff6b32] text-xs text-white hover:bg-[#ff4801]'>
            {busy ? <LoaderCircle className='size-3.5 animate-spin' /> : <CircleDollarSign className='size-3.5' />}
            入金を登録
          </Button>
        </div>
      </div>

      <div className='mt-3 rounded-lg border border-[#d0d7de] bg-white p-3'>
        <p className='text-xs font-semibold text-[#24292f]'>台帳の動き</p>
        <div className='mt-3 max-h-44 space-y-2 overflow-y-auto pr-1'>
          {[...loop.ledger.entries].reverse().map((entry, index) => (
            <div key={index} className='flex items-start gap-2 text-xs'>
              <span
                className={[
                  'mt-1 size-1.5 shrink-0 rounded-full',
                  entry.kind === 'revenue' ? 'bg-[#1a7f37]' : entry.kind === 'delivery' ? 'bg-[#0969da]' : 'bg-[#8c959f]',
                ].join(' ')}
              />
              <div className='min-w-0'>
                <p className='text-[#24292f]'>{entry.label}</p>
                <p className='text-[10px] text-[#8c959f]'>{fmtDate(entry.at)}</p>
              </div>
              {entry.amount_yen !== 0 && (
                <p className={['ml-auto shrink-0 font-semibold', entry.kind === 'revenue' ? 'text-[#1a7f37]' : 'text-[#57606a]'].join(' ')}>
                  {entry.kind === 'revenue' ? '+' : ''}{fmtYen(entry.amount_yen)}
                </p>
              )}
            </div>
          ))}
          {loop.ledger.entries.length === 0 && (
            <p className='py-2.5 text-center text-xs text-[#8c959f]'>まだ動きはありません</p>
          )}
        </div>
      </div>

      {!killed && (
        <div className='mt-3 rounded-lg border border-[#ff818266] bg-[#ffebe9] p-3'>
          <p className='text-xs font-semibold text-[#cf222e]'>事業を停止する</p>
          <input
            value={killReason}
            onChange={event => setKillReason(event.target.value)}
            placeholder='理由（任意）'
            className='mt-2 h-9 w-full rounded-lg border border-[#ff818266] bg-white px-2.5 text-xs text-[#24292f] outline-none placeholder:text-[#8c959f] focus:border-[#cf222e]'
          />
          <Button onClick={onKill} disabled={busy} variant='destructive' className='mt-2 h-9 w-full rounded-lg text-xs'>
            <Trash2 className='size-3.5' />
            事業を停止
          </Button>
        </div>
      )}
    </>
  )
}

function LedgerMetric({ label, value, tone }: { label: string; value: string; tone: 'positive' | 'negative' | 'neutral' }) {
  return (
    <div className='rounded-md border border-[#d0d7de] bg-white px-3 py-2'>
      <p className='text-[10px] text-[#57606a]'>{label}</p>
      <p className={['mt-0.5 text-base font-semibold tracking-[-.02em]', tone === 'positive' ? 'text-[#1a7f37]' : tone === 'negative' ? 'text-[#cf222e]' : 'text-[#24292f]'].join(' ')}>
        {value}
      </p>
    </div>
  )
}






// ---------------------------------------------------------------------------
// Revenue Engine v0.1 UI
// ---------------------------------------------------------------------------
function ModeTabs({ value, onChange }: { value: 'v0' | 'revenue'; onChange: (value: 'v0' | 'revenue') => void }) {
  const base = 'inline-flex h-6 items-center gap-1 rounded px-2 text-[11px] font-semibold transition-colors'
  return (
    <div className='flex items-center gap-0.5 rounded-md border border-[#d0d7de] bg-[#f6f8fa] p-0.5'>
      <button
        type='button'
        onClick={() => onChange('v0')}
        className={base + (value === 'v0' ? ' bg-white text-[#24292f] shadow-sm' : ' text-[#57606a] hover:text-[#24292f]')}
      >
        <GitBranch className='size-3' />
        売上ループ
      </button>
      <button
        type='button'
        onClick={() => onChange('revenue')}
        className={base + (value === 'revenue' ? ' bg-white text-[#24292f] shadow-sm' : ' text-[#57606a] hover:text-[#24292f]')}
      >
        <Table2 className='size-3' />
        収益計画
      </button>
    </div>
  )
}

function RevenueView({ onBack }: { onBack: () => void }) {
  return (
    <div className='flex h-svh flex-col overflow-hidden bg-[#f6f8fa] text-[#24292f]'>
      <header className='flex h-11 shrink-0 items-center gap-2.5 border-b border-[#d0d7de] bg-white px-3'>
        <img src='/ui-assets/guildless-mark.svg' alt='Guildless' className='size-6 rounded' />
        <h1 className='text-[13px] font-bold tracking-[-.01em]'>Guildless</h1>
        <span className='text-[11px] text-[#57606a]'>収益計画</span>
        <ModeTabs value='revenue' onChange={value => { if (value === 'v0') onBack() }} />
        <div className='ml-auto flex items-center gap-2'>
          <span className='inline-flex items-center gap-1 rounded-full border border-[#d4a72c]/50 bg-[#fff8c5] px-2 py-0.5 text-[10px] font-semibold text-[#7d5d00]'>
            <ShieldCheck className='size-3' />
            確認運転
          </span>
          <button
            type='button'
            onClick={onBack}
            className='inline-flex h-7 items-center gap-1 rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-2 text-[11px] font-semibold text-[#24292f] hover:bg-[#eaeef2]'
          >
            <ArrowLeft className='size-3' />
            売上ループへ
          </button>
        </div>
      </header>
      <RevenueBody />
    </div>
  )
}

function RevenueBody() {
  const [plan, setPlan] = useState<RevenuePlan | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [scouting, setScouting] = useState(false)
  const [error, setError] = useState('')
  const [product, setProduct] = useState('')
  const [priceYen, setPriceYen] = useState(5000)
  const [targetYen, setTargetYen] = useState('')
  const [budgetYen, setBudgetYen] = useState(30000)
  const [deadlineDays, setDeadlineDays] = useState(14)
  const [region, setRegion] = useState('')
  const [industry, setIndustry] = useState('')

  useEffect(() => {
    requestJson<{ exists: boolean; plan: RevenuePlan | null }>('/v1/revenue/overview')
      .then(data => {
        setPlan(data.plan)
        if (data.plan) {
          setProduct(data.plan.product)
          setPriceYen(data.plan.price_yen)
          setTargetYen(data.plan.target_revenue_yen ? String(data.plan.target_revenue_yen) : '')
          setBudgetYen(data.plan.budget_yen)
          setDeadlineDays(data.plan.deadline_days)
          setRegion(data.plan.region)
          setIndustry(data.plan.industry)
        }
      })
      .catch(reason => setError(reason instanceof Error ? reason.message : '収益計画を読み込めませんでした'))
      .finally(() => setLoading(false))
  }, [])

  const analyze = async () => {
    if (!product.trim()) {
      setError('商品名を入力してください')
      return
    }
    if (!Number.isFinite(priceYen) || priceYen < 300) {
      setError('価格は300円以上で入力してください')
      return
    }
    setBusy(true)
    setError('')
    try {
      const next = await requestJson<RevenuePlan>('/v1/revenue/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product: product.trim(),
          price_yen: priceYen,
          target_revenue_yen: targetYen.trim() ? Number(targetYen) : null,
          budget_yen: budgetYen,
          deadline_days: deadlineDays,
          region: region.trim(),
          industry: industry.trim(),
        }),
      })
      setPlan(next)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '計画を組み立てられませんでした')
    } finally {
      setBusy(false)
    }
  }

  const scout = async () => {
    if (!plan) return
    setScouting(true)
    setError('')
    try {
      const next = await requestJson<RevenuePlan>('/v1/revenue/scout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_id: plan.plan_id }),
      })
      setPlan(next)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'GitHub探索に失敗しました')
    } finally {
      setScouting(false)
    }
  }

  if (loading) {
    return (
      <div className='grid flex-1 place-items-center bg-[#f6f8fa]'>
        <LoaderCircle className='size-5 animate-spin text-[#ff4801]' />
      </div>
    )
  }

  const gaps = plan ? plan.gaps : []
  const discoveredCount = gaps.reduce((sum, gap) => sum + gap.discovered_candidates.length, 0)

  return (
    <div className='grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_minmax(340px,400px)]'>
      <main className='min-h-0 overflow-y-auto border-r border-[#d0d7de] bg-[#f6f8fa] p-3'>
        {error && (
          <div className='mb-3 flex items-start gap-1.5 rounded-md border border-[#ff818266] bg-[#ffebe9] px-3 py-2 text-xs text-[#cf222e]'>
            <TriangleAlert className='mt-0.5 size-3.5 shrink-0' />
            {error}
          </div>
        )}
        {plan ? <RevenueResults plan={plan} /> : <RevenueIntro />}
      </main>

      <aside className='flex min-h-0 flex-col gap-2.5 overflow-y-auto p-2.5'>
        <RevenueForm
          product={product}
          setProduct={setProduct}
          priceYen={priceYen}
          setPriceYen={setPriceYen}
          targetYen={targetYen}
          setTargetYen={setTargetYen}
          budgetYen={budgetYen}
          setBudgetYen={setBudgetYen}
          deadlineDays={deadlineDays}
          setDeadlineDays={setDeadlineDays}
          region={region}
          setRegion={setRegion}
          industry={industry}
          setIndustry={setIndustry}
          busy={busy}
          hasPlan={plan !== null}
          onAnalyze={analyze}
        />
        {plan && <RevenueGaps plan={plan} scouting={scouting} discoveredCount={discoveredCount} onScout={scout} />}
      </aside>
    </div>
  )
}

function RevenueIntro() {
  return (
    <div className='max-w-2xl'>
      <p className='text-[10px] font-bold text-[#ff4801]'>Guildless Revenue Engine v0.1</p>
      <h2 className='mt-0.5 text-lg font-bold tracking-[-.02em]'>商材を入れると、売上までの工程を逆算する</h2>
      <p className='mt-1 text-xs leading-5 text-[#57606a]'>
        商品名・価格を入れるだけで、目標売上から受注数・商談数・接触数を逆算し、
        9段階の売上ファネルと再利用可能な部品（Skill）に分解します。
        不足している部品はGitHubやOSSから実装候補を探索して埋めます。
      </p>

      <h3 className='mt-4 text-[11px] font-bold text-[#57606a]'>逆算の流れ</h3>
      <ol className='mt-1.5 space-y-1'>
        {[
          ['目標売上 ÷ 平均単価', '必要受注数を出す'],
          ['受注率20%（商談→受注）', '必要商談数を出す'],
          ['商談化率5%（接触→商談）', '必要接触数を出す'],
          ['反応率2%（接触→興味）', '興味件数の見込みを出す'],
        ].map((item, index) => (
          <li key={index} className='flex items-center gap-2 rounded-md border border-[#d0d7de] bg-white px-2.5 py-1.5 text-xs'>
            <span className='grid size-4 shrink-0 place-items-center rounded-full bg-[#24292f] text-[9px] font-bold text-white'>{index + 1}</span>
            <span className='font-semibold'>{item[0]}</span>
            <ArrowRight className='size-3 shrink-0 text-[#57606a]' />
            <span className='text-[#57606a]'>{item[1]}</span>
          </li>
        ))}
      </ol>

      <h3 className='mt-4 text-[11px] font-bold text-[#57606a]'>部品の優先順位</h3>
      <p className='mt-1 text-xs leading-5 text-[#57606a]'>
        既存Capability → 既存API/MCP → 信頼できるOSS（Firecrawl・Browser Use・OpenHands・n8n 等）→ 小さく自作。
        GitHubは「コード置き場」ではなく「部品市場」として扱い、不足部品ごとに実装候補を探します。
      </p>
    </div>
  )
}

function RevenueResults({ plan }: { plan: RevenuePlan }) {
  const calc = plan.backward_calc
  const installedPacks = plan.sources.installed_packs
  return (
    <div className='space-y-3'>
      <div className='flex flex-wrap items-center gap-2'>
        <h2 className='text-sm font-bold tracking-[-.01em]'>売上計画：{plan.product}</h2>
        <span className='rounded-md bg-[#eaeef2] px-1.5 py-0.5 font-mono text-[10px] text-[#57606a]'>{plan.plan_id}</span>
        <span className='text-[11px] text-[#57606a]'>作成 {fmtDate(plan.created_at)}</span>
        <span className='text-[11px] text-[#57606a]'>
          予算 {fmtYen(plan.budget_yen)} · 期間 {plan.deadline_days}日
          {plan.region ? ' · 地域 ' + plan.region : ''}
          {plan.industry ? ' · 業界 ' + plan.industry : ''}
        </span>
      </div>

      {installedPacks.length > 0 && (
        <div className='flex flex-wrap items-center gap-1.5'>
          <span className='text-[10px] text-[#57606a]'>確保済みOSS：</span>
          {installedPacks.map(pack => (
            <span key={pack} className='rounded bg-[#dafbe1] px-1.5 py-0.5 text-[9px] font-semibold text-[#1a7f37]'>{pack}</span>
          ))}
        </div>
      )}

      <section>
        <h3 className='mb-1.5 flex items-center gap-1.5 text-[11px] font-bold text-[#57606a]'>
          <Target className='size-3.5 text-[#ff4801]' />
          売上から逆算
        </h3>
        <div className='grid grid-cols-3 gap-2 xl:grid-cols-6'>
          <CalcCard label='目標売上' value={fmtYen(calc.target_revenue_yen)} />
          <CalcCard label='平均単価' value={fmtYen(calc.price_yen)} />
          <CalcCard label='必要受注' value={calc.required_orders + '件'} />
          <CalcCard label='必要商談' value={calc.required_meetings + '商談'} />
          <CalcCard label='必要接触' value={calc.required_contacts + '社'} accent />
          <CalcCard label='興味見込み' value={calc.interested + '件'} />
        </div>
        <p className='mt-1.5 text-[10px] text-[#57606a]'>
          基準値：商談→受注 20% ・ 接触→商談 {Math.round(calc.meeting_rate * 100)}% ・ 接触→反応 {Math.round(calc.response_rate * 100)}%
          （実行後の実測値で差し替えます）
        </p>
      </section>

      <section>
        <h3 className='mb-1.5 flex items-center gap-1.5 text-[11px] font-bold text-[#57606a]'>
          <Table2 className='size-3.5 text-[#ff4801]' />
          売上までの9段階
        </h3>
        <div className='overflow-hidden rounded-md border border-[#d0d7de]'>
          <table className='w-full border-collapse bg-white text-xs'>
            <thead>
              <tr className='border-b border-[#d0d7de] bg-[#f6f8fa] text-left text-[10px] text-[#57606a]'>
                <th className='px-2.5 py-1.5 font-semibold'>段階</th>
                <th className='px-2.5 py-1.5 font-semibold'>KPI</th>
                <th className='px-2.5 py-1.5 text-right font-semibold'>数量</th>
                <th className='px-2.5 py-1.5 text-right font-semibold'>根拠</th>
                <th className='px-2.5 py-1.5 font-semibold'>内容</th>
              </tr>
            </thead>
            <tbody>
              {plan.funnel.map(row => (
                <tr key={row.stage_id} className='border-b border-[#eaeef2] last:border-0'>
                  <td className='px-2.5 py-1.5 font-semibold'>{row.label}</td>
                  <td className='px-2.5 py-1.5 text-[#57606a]'>{row.kpi}</td>
                  <td className='px-2.5 py-1.5 text-right font-bold tabular-nums'>
                    {row.count === null ? '—' : row.count.toLocaleString('ja-JP') + row.unit}
                  </td>
                  <td className='px-2.5 py-1.5 text-right text-[#57606a]'>{row.basis}</td>
                  <td className='px-2.5 py-1.5 text-[#57606a]'>{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3 className='mb-1.5 flex items-center gap-1.5 text-[11px] font-bold text-[#57606a]'>
          <ListChecks className='size-3.5 text-[#ff4801]' />
          実行ワークフロー（{plan.workflow.length}個の部品）
        </h3>
        <div className='overflow-hidden rounded-md border border-[#d0d7de]'>
          <table className='w-full border-collapse bg-white text-xs'>
            <thead>
              <tr className='border-b border-[#d0d7de] bg-[#f6f8fa] text-left text-[10px] text-[#57606a]'>
                <th className='px-2.5 py-1.5 font-semibold'>#</th>
                <th className='px-2.5 py-1.5 font-semibold'>工程</th>
                <th className='px-2.5 py-1.5 font-semibold'>部品（Skill）</th>
                <th className='px-2.5 py-1.5 font-semibold'>実装候補</th>
                <th className='px-2.5 py-1.5 font-semibold'>状態</th>
                <th className='px-2.5 py-1.5 text-right font-semibold'>費用上限</th>
              </tr>
            </thead>
            <tbody>
              {plan.workflow.map(step => (
                <tr key={step.step} className='border-b border-[#eaeef2] last:border-0'>
                  <td className='px-2.5 py-1.5 font-mono text-[#57606a]'>{step.step}</td>
                  <td className='px-2.5 py-1.5 whitespace-nowrap text-[#57606a]'>{step.stage_label}</td>
                  <td className='px-2.5 py-1.5'>
                    <div className='font-semibold'>{step.name}</div>
                    <div className='text-[10px] text-[#57606a]'>{step.goal}</div>
                  </td>
                  <td className='px-2.5 py-1.5 text-[#57606a]'>
                    {step.primary ? step.primary.name + '（' + step.primary.source + '）' : '—'}
                  </td>
                  <td className='px-2.5 py-1.5'><RevenueStatus status={step.status} /></td>
                  <td className='px-2.5 py-1.5 text-right tabular-nums'>{fmtYen(step.cost_limit_yen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function CalcCard({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className='rounded-md border border-[#d0d7de] bg-white px-2.5 py-2'>
      <div className='text-[10px] font-medium text-[#57606a]'>{label}</div>
      <div className={'text-sm font-bold tabular-nums ' + (accent ? 'text-[#ff4801]' : 'text-[#24292f]')}>{value}</div>
    </div>
  )
}

function RevenueStatus({ status }: { status: string }) {
  const tone = status === '確保済み' ? 'ok' : status === '要確保' ? 'gap' : 'warn'
  const style = tone === 'ok'
    ? 'bg-[#dafbe1] text-[#1a7f37]'
    : tone === 'gap'
      ? 'bg-[#fff1e5] text-[#bc4c00]'
      : 'bg-[#fff8c5] text-[#7d5d00]'
  return <span className={'inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-semibold ' + style}>{status}</span>
}

function RevenueForm(props: {
  product: string; setProduct: (v: string) => void
  priceYen: number; setPriceYen: (v: number) => void
  targetYen: string; setTargetYen: (v: string) => void
  budgetYen: number; setBudgetYen: (v: number) => void
  deadlineDays: number; setDeadlineDays: (v: number) => void
  region: string; setRegion: (v: string) => void
  industry: string; setIndustry: (v: string) => void
  busy: boolean; hasPlan: boolean; onAnalyze: () => void
}) {
  const inputCls = 'mt-1 w-full rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-2.5 py-1.5 text-xs outline-none focus:border-[#ff7038] focus:bg-white'
  return (
    <section className='shrink-0 rounded-md border border-[#d0d7de] bg-white'>
      <div className='flex items-center gap-1.5 border-b border-[#d0d7de] bg-[#f6f8fa] px-2.5 py-2'>
        <Rocket className='size-3.5 text-[#ff4801]' />
        <h3 className='text-[11px] font-bold text-[#24292f]'>商材を入れて売上計画を組む</h3>
      </div>
      <div className='grid grid-cols-2 gap-2 p-2.5'>
        <label className='col-span-2 block'>
          <span className='text-[10px] font-bold text-[#24292f]'>商品名</span>
          <input value={props.product} onChange={e => props.setProduct(e.target.value)} placeholder='例：ホームページ改善診断レポート' className={inputCls} />
        </label>
        <label className='block'>
          <span className='text-[10px] font-bold text-[#24292f]'>価格（円）</span>
          <input type='number' value={props.priceYen} min={300} max={10000000} onChange={e => props.setPriceYen(Number(e.target.value))} className={inputCls} />
        </label>
        <label className='block'>
          <span className='text-[10px] font-bold text-[#24292f]'>目標売上（円）</span>
          <input type='number' value={props.targetYen} min={300} onChange={e => props.setTargetYen(e.target.value)} placeholder='価格×6' className={inputCls} />
        </label>
        <label className='block'>
          <span className='text-[10px] font-bold text-[#24292f]'>予算上限（円）</span>
          <input type='number' value={props.budgetYen} min={1000} max={1000000} onChange={e => props.setBudgetYen(Number(e.target.value))} className={inputCls} />
        </label>
        <label className='block'>
          <span className='text-[10px] font-bold text-[#24292f]'>期間（日）</span>
          <input type='number' value={props.deadlineDays} min={1} max={90} onChange={e => props.setDeadlineDays(Number(e.target.value))} className={inputCls} />
        </label>
        <label className='block'>
          <span className='text-[10px] font-bold text-[#24292f]'>地域（任意）</span>
          <input value={props.region} onChange={e => props.setRegion(e.target.value)} placeholder='例：東京' className={inputCls} />
        </label>
        <label className='block'>
          <span className='text-[10px] font-bold text-[#24292f]'>業界（任意）</span>
          <input value={props.industry} onChange={e => props.setIndustry(e.target.value)} placeholder='例：飲食店' className={inputCls} />
        </label>
      </div>
      <div className='px-2.5 pb-2.5'>
        <Button onClick={props.onAnalyze} disabled={props.busy} className='h-9 w-full rounded-md bg-[#ff4801] text-white hover:bg-[#e04400]'>
          {props.busy ? <LoaderCircle className='size-4 animate-spin' /> : <ArrowRight className='size-4' />}
          {props.busy ? '計画中' : props.hasPlan ? '再分析' : '売上計画を組む'}
        </Button>
      </div>
    </section>
  )
}

function RevenueGaps({ plan, scouting, discoveredCount, onScout }: { plan: RevenuePlan; scouting: boolean; discoveredCount: number; onScout: () => void }) {
  const gaps = plan.gaps
  const scoutDone = plan.scout.status === 'done'
  return (
    <section className='shrink-0 rounded-md border border-[#d0d7de] bg-white'>
      <div className='flex items-center justify-between gap-2 border-b border-[#d0d7de] bg-[#f6f8fa] px-2.5 py-2'>
        <div className='flex items-center gap-1.5'>
          <PackagePlus className='size-3.5 text-[#ff4801]' />
          <h3 className='text-[11px] font-bold text-[#24292f]'>不足部品（{gaps.length}）</h3>
          {discoveredCount > 0 && (
            <span className='rounded-full bg-[#dafbe1] px-1.5 py-0.5 text-[9px] font-bold text-[#1a7f37]'>{discoveredCount}件発見</span>
          )}
        </div>
        <Button onClick={onScout} disabled={scouting || gaps.length === 0} variant='outline' size='sm' className='h-7 border-[#d0d7de] text-[11px]'>
          {scouting ? <LoaderCircle className='size-3 animate-spin' /> : <GitFork className='size-3' />}
          {scouting ? '探索中' : 'GitHubから探索'}
        </Button>
      </div>
      {gaps.length === 0 ? (
        <p className='flex items-center gap-1.5 px-2.5 py-3 text-[11px] text-[#57606a]'>
          <CheckCircle2 className='size-3.5 text-[#1a7f37]' />
          不足なし。全工程の部品が確保済みです。
        </p>
      ) : (
        <ul className='divide-y divide-[#eaeef2]'>
          {gaps.map(gap => (
            <li key={gap.skill_id} className='px-2.5 py-2'>
              <div className='flex items-center justify-between gap-2'>
                <span className='text-xs font-semibold'>{gap.name}</span>
                <span className='shrink-0 rounded bg-[#eaeef2] px-1.5 py-0.5 text-[9px] text-[#57606a]'>
                  {gap.required_capabilities.join(' / ')}
                </span>
              </div>
              {gap.discovered_candidates.length > 0 ? (
                <div className='mt-1.5 space-y-1.5'>
                  {gap.discovered_candidates.map(cand => (
                    <a key={cand.full_name} href={cand.html_url} target='_blank' rel='noreferrer'
                       className='block rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-2 py-1.5 hover:border-[#ff7038]'>
                      <span className='flex items-center gap-1 text-[11px] font-semibold text-[#24292f]'>
                        <GitFork className='size-3 shrink-0 text-[#57606a]' />
                        {cand.full_name}
                        <ExternalLink className='size-2.5 shrink-0 text-[#57606a]' />
                      </span>
                      <span className='mt-0.5 block truncate text-[10px] text-[#57606a]'>{cand.description}</span>
                      <span className='mt-1 flex flex-wrap items-center gap-1.5 text-[9px] text-[#57606a]'>
                        <span className='font-semibold'>★ {cand.stars}</span>
                        {cand.capabilities.slice(0, 3).map(cap => (
                          <span key={cap} className='rounded bg-[#eaeef2] px-1'>{cap}</span>
                        ))}
                      </span>
                    </a>
                  ))}
                </div>
              ) : scoutDone ? (
                <p className='mt-1 text-[10px] text-[#57606a]'>探索済みですが候補が見つかりませんでした</p>
              ) : (
                <p className='mt-1 text-[10px] text-[#57606a]'>未探索 · {gap.suggested_query ? 'クエリ「' + gap.suggested_query + '」' : 'クエリ未設定'}</p>
              )}
            </li>
          ))}
        </ul>
      )}
      {scoutDone && (
        <div className='border-t border-[#d0d7de] bg-[#f6f8fa] px-2.5 py-1.5 text-[10px] text-[#57606a]'>
          探索時刻：{fmtDate(plan.scout.queried_at)} · {plan.scout.results.length}件のクエリを実行
        </div>
      )}
    </section>
  )
}
