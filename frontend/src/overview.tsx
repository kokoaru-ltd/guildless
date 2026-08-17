/**
 * The screen an owner opens in the morning.
 *
 * Laid out as Midday lays out a financial overview: a row of square bordered
 * cells across the top, then the working detail beneath. Every cell in that row
 * is the same size because none of them outranks the others at a glance — Cash
 * matters most, and it earns that by being first, not by being bigger.
 *
 * The charts exist because a total cannot answer the question an owner
 * actually has. ¥0 with 190 prospects and a rising reply line is a company
 * three weeks from revenue; ¥0 with a flat line is a company that is not
 * working. Same number, opposite meanings, and only the trajectory separates
 * them.
 *
 * There is no message box. Guildless is already running the company; a large
 * "what shall we do today?" field would make typing look like the job.
 */
import { AlertTriangle } from 'lucide-react'
import { FunnelChart, TrendChart } from '@/chart'
import { Bar, Cell, Label, Panel, Region, Status, yen, yenShort } from '@/ui'
import type { Company } from '@/types'

export function Overview({ data, onOpenBet }: {
  data: Company
  onOpenBet: (id: string) => void
}) {
  const { money, outcome, bets } = data
  const waiting = data.needs_you
  const history = data.history ?? []

  return <div className='flex h-full min-h-0 flex-col overflow-y-auto'>
    {money.world !== 'real' && (
      <div className='flex shrink-0 items-center gap-2.5 border-b border-[#b45309]/25 bg-[#b45309]/[0.04] px-7 py-2'>
        <span className='inline-flex h-[22px] shrink-0 items-center rounded-md border border-[#b45309]/35 px-2 text-[10px] font-medium text-[#b45309]'>
          SIMULATED
        </span>
        <p className='truncate text-xs text-[#8a5a1a]'>
          模擬環境で動作中。{yen(money.simulated_yen)}（{money.simulated_sales}件）は模擬売上で、Cashには入りません。
        </p>
      </div>
    )}

    <div className='p-7'>
      {/* Collapsed borders between neighbours, so the row reads as one ruled
          band rather than four floating boxes. */}
      <div className='grid grid-cols-4 gap-px bg-[#e6e6e6]'>
        <Cell
          label='Cash'
          value={yen(money.cash_yen)}
          tone={money.cash_yen > 0 ? 'cash' : 'plain'}
          detail={money.cash_yen === 0 ? '入金待ち' : '受取 − 支出'}
        />
        <Cell label='Received' value={yen(money.received_yen)}
          detail={`${money.payments} payments`} />
        <Cell label='30D Expected' value={yen(money.expected_yen)} tone='muted'
          detail={`${money.opportunities} opportunities`} />
        <Cell label='Capital' value={yen(money.capital_yen)} detail='使える残り' />
      </div>

      <div className='mt-7 grid grid-cols-[1fr_340px] gap-7'>
        {/* Two charts, not one with three series. Replies are an order of
            magnitude below contacts, so a shared axis flattens them onto the
            baseline and the reader learns nothing about the half of the funnel
            that actually decides whether this works. */}
        <Region label='Reach' right={
          history.length ? <Label>{history.length} passes</Label> : undefined
        }>
          <TrendChart series={[
            { label: 'Contacted', points: history.map(h => h.contacted) },
          ]} height={104} />
          <div className='mt-5'>
            <Label>Replies &amp; proposals</Label>
            <div className='mt-2'>
              <TrendChart series={[
                { label: 'Replied', points: history.map(h => h.replied) },
                { label: 'Quoted', points: history.map(h => h.quoted) },
              ]} height={104} />
            </div>
          </div>
        </Region>

        <Region label='Revenue Pipeline'>
          <FunnelChart rows={[
            ['Prospects', bets.funnel.contacted],
            ['Replies', bets.funnel.replied],
            ['Meetings', bets.funnel.meetings],
            ['Proposals', bets.funnel.quoted],
            ['Paid', bets.funnel.paid],
          ]} />
        </Region>
      </div>

      <div className='mt-7 grid grid-cols-[1fr_340px] gap-7'>
        <Region label='Primary Outcome'>
          <p className='truncate text-sm font-medium'>{outcome.statement || '未設定'}</p>
          {outcome.target_yen > 0 ? (
            <>
              <div className='mt-3'><Bar percent={outcome.progress} /></div>
              <p className='mt-2 text-xs tabular-nums text-[#878787]'>
                {yenShort(money.cash_yen)} / {yenShort(outcome.target_yen)}
                <span className='ml-2 font-medium text-[#121212]'>{outcome.progress}%</span>
              </p>
            </>
          ) : (
            <p className='mt-2 text-xs text-[#a8a8a8]'>金額目標が設定されていません</p>
          )}
        </Region>

        <Region label='Guildless Decision'>
          <p className='text-sm leading-6'>{data.decision}</p>
        </Region>
      </div>

      <Region label='Active Bets' className='mt-7'>
        {bets.bets.length ? (
          <div className='border border-[#e6e6e6] bg-white'>
            {bets.bets.slice(0, 5).map((bet, index) => (
              <button
                key={bet.id}
                onClick={() => onOpenBet(bet.id)}
                className={`flex h-[45px] w-full items-center gap-3 px-4 text-left hover:bg-[#f7f7f7] ${
                  index ? 'border-t border-[#e6e6e6]' : ''
                }`}
              >
                <span className={`shrink-0 text-sm ${bet.status === 'KILLED' ? 'text-[#c4c4c4]' : ''}`}>
                  {bet.name}
                </span>
                <span className='ml-auto truncate text-xs text-[#878787]'>{bet.why}</span>
                <Status value={bet.status} />
              </button>
            ))}
          </div>
        ) : (
          <p className='text-xs text-[#a8a8a8]'>まだ賭けがありません</p>
        )}
      </Region>

      {/* Only rendered when something is genuinely waiting. An always-present
          "nothing needs you" strip trains the eye to skip the place where the
          one thing that does need them will appear. */}
      {waiting.length > 0 && (
        <Panel className='mt-7 flex items-center gap-3 border-[#b45309]/35 bg-[#b45309]/[0.04] px-4 py-3'>
          <AlertTriangle className='size-4 shrink-0 text-[#b45309]' />
          <div className='min-w-0'>
            <Label className='!text-[#b45309]'>Needs you</Label>
            <p className='mt-0.5 truncate text-sm'>{waiting[0].title}</p>
          </div>
          {waiting.length > 1 && (
            <span className='ml-auto shrink-0 text-xs text-[#878787]'>他{waiting.length - 1}件</span>
          )}
        </Panel>
      )}
    </div>
  </div>
}
