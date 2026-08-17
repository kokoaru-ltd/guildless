import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, ArrowRight, CheckCircle2, CircleSlash, LoaderCircle, PanelRightOpen, X } from 'lucide-react'

/**
 * The one screen. Built so that five seconds answers four questions: how much
 * real money came in, where it is stuck, what it is doing, and whether the
 * reader has to act.
 *
 * Everything competing for that attention is deliberately smaller. Agent
 * counts, task totals and token usage are absent — a company that leads with
 * activity is measuring how busy it is, not whether it earned anything.
 *
 * Chat is not here. It sits behind a drawer, because a conversation in the
 * middle of the screen makes this an assistant, and an assistant is a thing
 * you have to operate.
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
  status: 'RUNNING' | 'BLOCKED' | 'HUMAN_REQUIRED' | 'SUCCESS' | 'TERMINAL_FAILURE'
  bottleneck: string
  current_action: string
  money: {
    starting_capital_yen: number; available_yen: number; reserved_yen: number
    spent_yen: number; verified_revenue_yen: number
    breakdown_yen: Record<string, number>
  }
  strategy: { offer?: string; price_yen?: number; chosen_because: string; rejected: { name: string; reasons: string[] }[] }
  evidence: Evidence[]
  failures: Failure[]
  human_required: HumanTask[]
  gate: { level: string; real_payments: number }
  external_action?: { granted: boolean; note: string }
  excluded_from_totals: { test_payments: number; note: string }
}

const STATUS: Record<string, { label: string; tone: string; dot: string }> = {
  RUNNING: { label: '実行中', tone: 'text-[#276453] bg-[#edf5f1] border-[#c3ddcf]', dot: 'bg-[#276453]' },
  BLOCKED: { label: '停滞', tone: 'text-[#8a6410] bg-[#fdf6e7] border-[#e4cfa6]', dot: 'bg-[#8a6410]' },
  HUMAN_REQUIRED: { label: 'あなたの操作待ち', tone: 'text-[#a94712] bg-[#fff1e9] border-[#efc8b7]', dot: 'bg-[#ff4801]' },
  SUCCESS: { label: '達成', tone: 'text-[#276453] bg-[#edf5f1] border-[#c3ddcf]', dot: 'bg-[#276453]' },
  TERMINAL_FAILURE: { label: '終了', tone: 'text-[#b3261e] bg-[#ffebe9] border-[#f5b5b0]', dot: 'bg-[#b3261e]' },
}

const yen = (value: number) => `¥${Math.round(value || 0).toLocaleString('ja-JP')}`

export function OutcomeView() {
  const [data, setData] = useState<Outcome | null>(null)
  const [error, setError] = useState('')
  const [drawer, setDrawer] = useState(false)

  const load = useCallback(async () => {
    try {
      const response = await fetch('/v1/outcome')
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      setData(await response.json())
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '状態を取得できません')
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => void load(), 5000)
    return () => window.clearInterval(timer)
  }, [load])

  if (error && !data) {
    return <div className='grid h-svh place-items-center bg-[#f7f7f5]'>
      <div className='rounded-xl border border-red-200 bg-red-50 px-6 py-4 text-sm text-red-700'>
        状態を取得できません（{error}）。数字は表示しません。
      </div>
    </div>
  }
  if (!data) {
    return <div className='grid h-svh place-items-center bg-[#f7f7f5]'>
      <LoaderCircle className='size-5 animate-spin text-[#817d76]' />
    </div>
  }

  const status = STATUS[data.status] || STATUS.RUNNING
  const money = data.money
  const needsHuman = data.human_required.length > 0

  return <div className='min-h-svh bg-[#f7f7f5] text-[#20201e]'>
    <div className='mx-auto max-w-[1180px] px-6 py-7 lg:px-10'>

      <header className='flex items-center justify-between'>
        <div className='flex items-baseline gap-3'>
          <span className='text-sm font-semibold tracking-tight'>Guildless</span>
          <span className='text-xs text-[#99958d]'>{data.goal}</span>
        </div>
        <button
          onClick={() => setDrawer(true)}
          className='flex items-center gap-1.5 rounded-lg border border-[#dedbd4] bg-white px-3 py-1.5 text-xs text-[#6f6b64] hover:bg-[#f3f1ed]'
        >
          <PanelRightOpen className='size-3.5' />相談
        </button>
      </header>

      {/* The four answers, in the order they are asked. */}
      <section className='mt-6 grid gap-4 lg:grid-cols-[1.15fr_1fr]'>
        <div className='rounded-2xl border border-[#dedbd4] bg-white p-7'>
          <p className='text-xs font-medium text-[#817d76]'>実際に増えた金</p>
          <p className={`mt-1 text-[64px] font-semibold leading-none tracking-tight tabular-nums ${
            data.verified_net_outcome_yen > 0 ? 'text-[#1a7f37]' : 'text-[#20201e]'
          }`}>
            {yen(data.verified_net_outcome_yen)}
          </p>
          <p className='mt-3 text-xs leading-5 text-[#817d76]'>
            外部の決済事業者が確認した入金のみ。{data.excluded_from_totals.test_payments > 0
              && `テスト決済${data.excluded_from_totals.test_payments}件は除外しています。`}
          </p>
        </div>

        <div className='grid gap-4'>
          <div className={`rounded-2xl border p-5 ${status.tone}`}>
            <div className='flex items-center gap-2'>
              <span className={`size-2 rounded-full ${status.dot}`} />
              <p className='text-lg font-semibold'>{status.label}</p>
            </div>
            <p className='mt-2 text-sm leading-6 opacity-90'>{data.current_action}</p>
          </div>

          <div className='rounded-2xl border border-[#dedbd4] bg-white p-5'>
            <p className='flex items-center gap-1.5 text-xs font-medium text-[#817d76]'>
              <CircleSlash className='size-3.5' />いま止まっている理由
            </p>
            <p className='mt-2 text-sm font-medium leading-6'>{data.bottleneck}</p>
          </div>
        </div>
      </section>

      {needsHuman && (
        <section className='mt-4 rounded-2xl border-2 border-[#ff4801] bg-[#fff1e9] p-6'>
          <p className='flex items-center gap-2 text-xs font-bold text-[#a94712]'>
            <AlertTriangle className='size-4' />あなたにしかできない操作があります
          </p>
          {data.human_required.map(task => (
            <div key={task.task} className='mt-3'>
              <p className='text-lg font-semibold'>{task.title}</p>
              <p className='mt-1 text-sm leading-6 text-[#6f6b64]'>{task.detail}</p>
            </div>
          ))}
        </section>
      )}

      <section className='mt-4 grid gap-4 lg:grid-cols-3'>
        <Card title='お金'>
          <Row label='元手' value={yen(money.starting_capital_yen)} />
          <Row label='使える' value={yen(money.available_yen)} />
          <Row label='留保（使用不可）' value={yen(money.reserved_yen)} muted />
          <Row label='使った' value={yen(money.spent_yen)} />
          <Row label='確認済み売上' value={yen(money.verified_revenue_yen)} strong />
          <div className='mt-3 border-t border-[#ece9e3] pt-2'>
            {Object.entries(money.breakdown_yen).map(([name, amount]) => (
              <div key={name} className='flex justify-between py-0.5 text-[11px] text-[#99958d]'>
                <span>{name}</span><span className='tabular-nums'>{yen(amount)}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title='いま試していること'>
          {data.strategy.offer ? <>
            <p className='text-sm font-semibold leading-6'>{data.strategy.offer}</p>
            {data.strategy.price_yen ? (
              <p className='mt-1 text-xs text-[#817d76]'>{yen(data.strategy.price_yen)}</p>
            ) : null}
            <p className='mt-3 text-xs leading-5 text-[#6f6b64]'>
              選んだ理由：{data.strategy.chosen_because}
            </p>
            {data.strategy.rejected.length > 0 && (
              <div className='mt-3 border-t border-[#ece9e3] pt-2'>
                {data.strategy.rejected.map(item => (
                  <p key={item.name} className='py-0.5 text-[11px] leading-4 text-[#99958d]'>
                    捨てた：{item.name} — {item.reasons[0]}
                  </p>
                ))}
              </div>
            )}
          </> : <p className='text-sm text-[#817d76]'>まだ選んでいません。</p>}
        </Card>

        <Card title='外部の証拠'>
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
          )) : <p className='text-sm text-[#817d76]'>外部で起きたことはまだありません。</p>}
        </Card>
      </section>

      {data.failures.length > 0 && (
        <section className='mt-4 rounded-2xl border border-[#dedbd4] bg-white p-6'>
          <p className='text-xs font-medium text-[#817d76]'>失敗と、そこから決めたこと</p>
          {data.failures.map((failure, index) => (
            <div key={index} className='mt-3 border-t border-[#ece9e3] pt-3 first:border-0 first:pt-0'>
              <p className='text-sm font-medium'>{failure.what}</p>
              {failure.detail && <p className='mt-1 text-xs leading-5 text-[#817d76]'>{failure.detail}</p>}
              <p className='mt-2 flex items-start gap-1.5 text-xs leading-5 text-[#4d4a45]'>
                <ArrowRight className='mt-0.5 size-3 shrink-0 text-[#ff4801]' />{failure.learning}
              </p>
            </div>
          ))}
        </section>
      )}

      <footer className='mt-6 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-[#aaa69e]'>
        <span>段階 {data.gate.level}</span>
        <span>確認済み入金 {data.gate.real_payments}件</span>
        {data.external_action && (
          <span>
            外部作用 {data.external_action.granted ? '許可済み' : '未許可'}
            <span className='ml-1 text-[#c4c0b8]'>· {data.external_action.note}</span>
          </span>
        )}
      </footer>
    </div>

    {drawer && <ConsultDrawer onClose={() => setDrawer(false)} />}
  </div>
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className='rounded-2xl border border-[#dedbd4] bg-white p-6'>
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

/** Secondary by construction: reachable, never in the way. */
function ConsultDrawer({ onClose }: { onClose: () => void }) {
  return <>
    <button className='fixed inset-0 z-30 bg-black/20' onClick={onClose} aria-label='閉じる' />
    <aside className='fixed inset-y-0 right-0 z-40 flex w-[380px] flex-col border-l border-[#dedbd4] bg-white'>
      <div className='flex items-center justify-between border-b border-[#ece9e3] px-5 py-4'>
        <p className='text-sm font-semibold'>相談</p>
        <button onClick={onClose} aria-label='閉じる' className='rounded p-1 hover:bg-[#f3f1ed]'>
          <X className='size-4' />
        </button>
      </div>
      <p className='px-5 py-4 text-xs leading-5 text-[#817d76]'>
        通常は使いません。Guildlessは指示を待たずに進みます。
        判断の背景を確認したいときだけ開いてください。
      </p>
    </aside>
  </>
}
