/**
 * The screen an owner opens in the morning.
 *
 * Six questions, in the order someone actually asks them: how much money is
 * there, what are we aiming at, what has Guildless decided, which bets are
 * alive, what is in the pipeline, and is anything waiting on me. Nothing else
 * belongs here — a control tower earns its place by being complete at a
 * glance, and every row that is merely interesting pushes the row that matters
 * below the fold.
 *
 * There is no message box. Guildless is already running the company; a large
 * "what shall we do today?" field would suggest it is waiting to be told, and
 * would make typing feel like the job. Instructions go through the command bar,
 * which is invisible until summoned.
 */
import { AlertTriangle } from 'lucide-react'
import { Bar, Figure, Label, Panel, Region, Status, yen, yenShort } from '@/ui'
import type { Company } from '@/types'

export function Overview({ data, onOpenBet }: {
  data: Company
  onOpenBet: (id: string) => void
}) {
  const { money, outcome, bets } = data
  const waiting = data.needs_you

  return <div className='flex h-full min-h-0 flex-col gap-6 overflow-hidden p-7'>
    {/* Money first, and net first within it. A company that received ¥300,000
        and spent ¥400,000 has not made ¥300,000, so the headline is the net. */}
    <Region className='shrink-0 border-b border-[#eeece7] pb-6'>
      <div className='grid grid-cols-4 gap-8'>
        <Figure
          label='Cash'
          value={yen(money.cash_yen)}
          tone={money.cash_yen > 0 ? 'cash' : 'plain'}
          note={money.cash_yen === 0 ? '第三者からの入金はまだありません' : '受取から支出を引いた純額'}
        />
        <Figure
          label='Received'
          value={yen(money.received_yen)}
          note={`${money.payments} payments`}
        />
        <Figure
          label='30D Expected'
          value={yen(money.expected_yen)}
          tone='muted'
          note={`${money.opportunities} opportunities`}
        />
        <Figure label='Capital' value={yen(money.capital_yen)} note='使える残り' />
      </div>
    </Region>

    <div className='grid min-h-0 flex-1 grid-cols-2 grid-rows-[auto_minmax(0,1fr)] gap-x-10 gap-y-7'>
      <Region label='Primary Outcome'>
        <p className='truncate text-[15px] font-medium'>{outcome.statement || '未設定'}</p>
        {outcome.target_yen > 0 ? (
          <>
            <div className='mt-3'><Bar percent={outcome.progress} /></div>
            <p className='mt-2 text-xs tabular-nums text-[#616161]'>
              {yenShort(money.cash_yen)} / {yenShort(outcome.target_yen)}
              <span className='ml-2 font-semibold text-[#121212]'>{outcome.progress}%</span>
            </p>
          </>
        ) : (
          <p className='mt-2 text-xs text-[#9d9a94]'>金額目標が設定されていません</p>
        )}
      </Region>

      <Region label='Guildless Decision'>
        <p className='text-[15px] font-medium leading-6'>{data.decision}</p>
      </Region>

      <Region label='Active Bets' className='min-h-0'>
        {bets.bets.length ? (
          <ul className='space-y-2'>
            {bets.bets.slice(0, 5).map(bet => (
              <li key={bet.id}>
                <button
                  onClick={() => onOpenBet(bet.id)}
                  className='flex w-full items-center gap-2.5 rounded px-1 py-0.5 text-left hover:bg-[#f7f5f1]'
                >
                  <span className={`truncate text-sm ${bet.status === 'KILLED' ? 'text-[#c4c1ba]' : ''}`}>
                    {bet.name}
                  </span>
                  <span className='ml-auto shrink-0 text-xs tabular-nums text-[#616161]'>
                    {bet.cash_yen ? yenShort(bet.cash_yen) : ''}
                  </span>
                  <Status value={bet.status} />
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className='text-xs text-[#9d9a94]'>まだ賭けがありません</p>
        )}
      </Region>

      <Region label='Revenue Pipeline'>
        <Funnel funnel={bets.funnel} />
      </Region>
    </div>

    {/* Only rendered when something is genuinely waiting. An always-present
        "nothing needs you" strip trains the eye to skip the place where the
        one thing that does need them will appear. */}
    {waiting.length > 0 && (
      <Panel className='flex shrink-0 items-center gap-3 border-[#ff4801]/30 bg-[#fff7f3] px-4 py-3'>
        <AlertTriangle className='size-4 shrink-0 text-[#c23a08]' />
        <div className='min-w-0'>
          <Label className='!text-[#c23a08]'>Needs You</Label>
          <p className='mt-0.5 truncate text-sm font-medium'>{waiting[0].title}</p>
        </div>
        {waiting.length > 1 && (
          <span className='shrink-0 text-xs text-[#616161]'>他{waiting.length - 1}件</span>
        )}
      </Panel>
    )}
  </div>
}

/** The pipeline as counted people. Money lives in the row above; mixing the
 *  two invites reading a quote as revenue. */
function Funnel({ funnel }: { funnel: Company['bets']['funnel'] }) {
  const rows: [string, number][] = [
    ['Prospects', funnel.contacted],
    ['Replies', funnel.replied],
    ['Meetings', funnel.meetings],
    ['Proposals', funnel.quoted],
    ['Paid', funnel.paid],
  ]
  const top = Math.max(...rows.map(([, n]) => n), 1)
  return <ul className='space-y-1.5'>
    {rows.map(([name, count], index) => (
      <li key={name} className='flex items-center gap-3'>
        <span className='w-20 shrink-0 text-xs text-[#616161]'>{name}</span>
        <div className='h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-[#f4f2ee]'>
          <div
            className='h-full rounded-full'
            style={{
              width: `${(count / top) * 100}%`,
              // The last stage is the only one that is money. Colouring the
              // others would imply the funnel is five kinds of success.
              background: index === rows.length - 1 && count > 0 ? '#16794a' : '#bfbcb5',
            }}
          />
        </div>
        <span className='w-8 shrink-0 text-right text-xs font-semibold tabular-nums'>{count}</span>
      </li>
    ))}
  </ul>
}
