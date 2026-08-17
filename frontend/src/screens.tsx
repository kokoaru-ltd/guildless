/**
 * The sections behind Overview.
 *
 * Business is the only one that is a management screen, and it manages bets
 * rather than tasks — the unit is "a way of making money", so the columns are
 * cash, pipeline, spend and reply rate rather than assignee and due date. A
 * company run by an AI has no shortage of effort to schedule; what it needs
 * managed is which hypotheses deserve more of the money.
 *
 * Activity is a debugging surface and is written as one. It is deliberately
 * plain and dense: nobody opens it when things are going well, and someone
 * opening it at all wants timestamps and the failure, not a designed page.
 * Keeping it separate is what stops the executive screens filling up with
 * retries and provider timeouts.
 */
import { useState } from 'react'
import { ExternalLink } from 'lucide-react'
import { Cell, Label, Panel, Region, Status, yen, yenShort } from '@/ui'
import type { ActivityItem, Bet, Company } from '@/types'

// --- Business ---------------------------------------------------------------

export function Business({ data, openId, onOpen }: {
  data: Company
  openId: string | null
  onOpen: (id: string | null) => void
}) {
  const bets = data.bets.bets
  const open = bets.find(b => b.id === openId) ?? null

  if (open) return <BetDetail bet={open} onBack={() => onOpen(null)} />

  return <div className='flex h-full min-h-0 flex-col p-7'>
    <Region label='Businesses / Bets' className='flex min-h-0 flex-1 flex-col'>
      {bets.length === 0 ? (
        <Empty>売るものが決まると、ここに賭けとして現れます。</Empty>
      ) : (
        <div className='min-h-0 flex-1 overflow-y-auto'>
          <table className='w-full table-fixed text-sm'>
            <thead className='sticky top-0 bg-white'>
              <tr className='border-b border-[#e6e6e6] text-left'>
                {([
                  ['Bet', 'w-auto'], ['Status', 'w-[86px]'], ['Cash', 'w-[92px]'],
                  ['Pipeline', 'w-[92px]'], ['Spent', 'w-[92px]'],
                  ['Reply', 'w-[68px]'], ['Contacted', 'w-[84px]'],
                ] as const).map(([head, width], index) => (
                  <th key={head} className={`${width} pb-2 text-[10px] font-medium uppercase tracking-[0.08em] text-[#878787] ${
                    index > 1 ? 'text-right' : 'text-left'
                  }`}>{head}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bets.map(bet => (
                <tr
                  key={bet.id}
                  onClick={() => onOpen(bet.id)}
                  className='cursor-pointer border-b border-[#e6e6e6] hover:bg-[#f7f7f7]'
                >
                  <td className='truncate py-2.5 pr-6 font-medium'>{bet.name}</td>
                  <td className='py-2.5 pr-4'><Status value={bet.status} /></td>
                  <td className={`py-2.5 text-right tabular-nums ${bet.cash_yen ? 'font-semibold text-[#16794a]' : 'text-[#878787]'}`}>
                    {yenShort(bet.cash_yen)}
                  </td>
                  <td className='py-2.5 text-right tabular-nums text-[#878787]'>{yenShort(bet.pipeline_yen)}</td>
                  <td className='py-2.5 text-right tabular-nums text-[#878787]'>{yenShort(bet.spent_yen)}</td>
                  <td className='py-2.5 text-right tabular-nums text-[#878787]'>
                    {bet.contacted ? `${Math.round(bet.reply_rate * 100)}%` : '—'}
                  </td>
                  <td className='py-2.5 text-right tabular-nums text-[#878787]'>{bet.contacted}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Region>
  </div>
}

function BetDetail({ bet, onBack }: { bet: Bet; onBack: () => void }) {
  const tabs = ['Overview', 'Pipeline', 'Assets', 'Activity', 'Evidence'] as const
  const [tab, setTab] = useState<(typeof tabs)[number]>('Overview')

  return <div className='flex h-full min-h-0 flex-col p-7'>
    <button onClick={onBack} className='self-start text-xs text-[#878787] hover:text-[#121212]'>
      ← Businesses
    </button>

    <div className='mt-3 flex shrink-0 items-center gap-3'>
      <h1 className='truncate text-lg font-semibold'>{bet.name}</h1>
      <Status value={bet.status} />
      <p className='ml-auto shrink-0 text-sm tabular-nums text-[#878787]'>{yen(bet.price_yen)}</p>
    </div>
    <p className='mt-1 text-xs text-[#878787]'>{bet.why}</p>

    <div className='mt-5 grid shrink-0 grid-cols-5 gap-px bg-[#e6e6e6]'>
      <Cell label='Cash' value={yen(bet.cash_yen)} tone={bet.cash_yen ? 'cash' : 'muted'} />
      <Cell label='Pipeline' value={yen(bet.pipeline_yen)} tone='muted' />
      <Cell label='Spent' value={yen(bet.spent_yen)} />
      <Cell label='Net' value={yen(bet.net_yen)} tone={bet.net_yen > 0 ? 'cash' : 'plain'} />
      <Cell label='First Cash'
        value={bet.days_to_first_cash === null ? '—' : `${bet.days_to_first_cash}d`}
        tone={bet.days_to_first_cash === null ? 'muted' : 'plain'}
      />
    </div>

    <nav className='mt-6 flex shrink-0 gap-5 border-b border-[#e6e6e6]'>
      {tabs.map(name => (
        <button
          key={name} onClick={() => setTab(name)}
          className={`-mb-px border-b-2 pb-2 text-xs font-medium ${
            tab === name
              ? 'border-[#ff4801] text-[#121212]'
              : 'border-transparent text-[#878787] hover:text-[#878787]'
          }`}
        >{name}</button>
      ))}
    </nav>

    <div className='min-h-0 flex-1 overflow-y-auto pt-5'>
      {tab === 'Overview' && (
        <dl className='grid max-w-2xl grid-cols-[120px_1fr] gap-y-3 text-sm'>
          <Row name='Offer' value={bet.offer} />
          <Row name='Customer' value={bet.audience} />
          <Row name='Channel' value={bet.channel} />
          <Row name='Price' value={yen(bet.price_yen)} />
          {bet.killed_because ? <Row name='Killed' value={bet.killed_because} /> : null}
        </dl>
      )}
      {tab === 'Pipeline' && (
        <dl className='grid max-w-md grid-cols-[120px_1fr] gap-y-3 text-sm'>
          <Row name='Contacted' value={String(bet.contacted)} />
          <Row name='Replied' value={String(bet.replied)} />
          <Row name='Meetings' value={String(bet.meetings)} />
          <Row name='Quoted' value={String(bet.quoted)} />
        </dl>
      )}
      {tab === 'Assets' && <Empty>この賭けの成果物はまだありません。</Empty>}
      {tab === 'Activity' && <Empty>この賭けに紐づく実行記録はまだありません。</Empty>}
      {tab === 'Evidence' && (
        <Empty>
          入金の証拠はここに出ます。外部の決済事業者が確認したものだけを載せます。
        </Empty>
      )}
    </div>
  </div>
}

function Row({ name, value }: { name: string; value: string }) {
  return <>
    <dt className='text-[#878787]'>{name}</dt>
    <dd className={value ? '' : 'text-[#c4c4c4]'}>{value || '未設定'}</dd>
  </>
}

// --- Revenue ----------------------------------------------------------------

export function Revenue({ data }: { data: Company }) {
  const { money } = data
  return <div className='flex h-full min-h-0 flex-col gap-7 overflow-y-auto p-7'>
    <Region>
      <div className='grid grid-cols-4 gap-px bg-[#e6e6e6]'>
        <Cell label='Cash' value={yen(money.cash_yen)} tone={money.cash_yen > 0 ? 'cash' : 'plain'} />
        <Cell label='Received' value={yen(money.received_yen)} detail={`${money.payments} payments`} />
        <Cell label='Expected' value={yen(money.expected_yen)} tone='muted' />
        <Cell label='Capital' value={yen(money.capital_yen)} />
      </div>
    </Region>

    <Region label='Verified Income'>
      {money.payments === 0 ? (
        <Empty>
          外部の決済事業者が確認した入金だけをここに載せます。テストモードの決済は
          売上に数えません。まだ1件もありません。
        </Empty>
      ) : (
        <p className='text-sm'>{money.payments}件の入金が確認済みです。</p>
      )}
    </Region>

    <Region label='Bets By Return'>
      {data.bets.bets.length === 0 ? <Empty>賭けがありません。</Empty> : (
        <ul className='max-w-2xl space-y-2 text-sm'>
          {data.bets.bets.map(bet => (
            <li key={bet.id} className='flex items-center gap-3'>
              <span className='truncate'>{bet.name}</span>
              <span className='ml-auto shrink-0 tabular-nums text-[#878787]'>
                {yen(bet.spent_yen)} 使って {yen(bet.cash_yen)}
              </span>
              <Status value={bet.status} />
            </li>
          ))}
        </ul>
      )}
    </Region>
  </div>
}

// --- Assets -----------------------------------------------------------------

export function Assets() {
  return <div className='flex h-full min-h-0 flex-col p-7'>
    <Region label='Assets' className='flex min-h-0 flex-1 flex-col'>
      <Empty>
        作ったものは、ファイルではなく作品として並びます。LP、提案資料、動画。
        それぞれが何のために作られ、どこで公開され、いくら稼いだかを持ちます。
        まだ何も作っていません。
      </Empty>
    </Region>
  </div>
}

// --- Activity ---------------------------------------------------------------

export function Activity({ items }: { items: ActivityItem[] }) {
  return <div className='flex h-full min-h-0 flex-col p-7'>
    <Region
      label='Activity'
      right={<span className='text-[11px] text-[#878787]'>{items.length} events</span>}
      className='flex min-h-0 flex-1 flex-col'
    >
      {items.length === 0 ? (
        <Empty>まだ記録された動きがありません。</Empty>
      ) : (
        <ol className='min-h-0 flex-1 overflow-y-auto font-mono text-xs'>
          {items.map((item, index) => (
            <li key={index} className='flex gap-4 border-b border-[#e6e6e6] py-1.5'>
              <span className='shrink-0 tabular-nums text-[#c4c4c4]'>
                {item.at.slice(11, 19)}
              </span>
              <span className='w-24 shrink-0 truncate text-[#878787]'>{item.step}</span>
              <span className={`min-w-0 flex-1 ${item.external ? 'text-[#c23a08]' : 'text-[#3a3a3a]'}`}>
                {item.detail}
              </span>
              {item.external ? <ExternalLink className='size-3 shrink-0 text-[#c23a08]' /> : null}
            </li>
          ))}
        </ol>
      )}
    </Region>
  </div>
}

// --- Settings ---------------------------------------------------------------

export function Settings({ environment }: { environment: { understanding: number; roles: Record<string, string[]>; services: unknown[] } | null }) {
  return <div className='flex h-full min-h-0 flex-col gap-7 overflow-y-auto p-7'>
    <Region label='Company Understanding'>
      {environment ? (
        <>
          <p className='text-2xl font-semibold tabular-nums'>{environment.understanding}%</p>
          <p className='mt-1 text-xs text-[#878787]'>
            {environment.services.length}件のサービスを、このPCから自動で検出しました。
            接続作業は要りません。
          </p>
          <dl className='mt-4 grid max-w-2xl grid-cols-[120px_1fr] gap-y-2 text-sm'>
            {Object.entries(environment.roles).map(([role, hosts]) => (
              <Row key={role} name={role} value={hosts.join('、')} />
            ))}
          </dl>
        </>
      ) : (
        <Empty>読み取り中です。</Empty>
      )}
    </Region>
  </div>
}

// --- shared -----------------------------------------------------------------

function Empty({ children }: { children: React.ReactNode }) {
  return <Panel className='max-w-2xl p-5'>
    <p className='text-xs leading-6 text-[#878787]'>{children}</p>
  </Panel>
}

export { Label }
