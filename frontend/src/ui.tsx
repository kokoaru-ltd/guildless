/**
 * The visual vocabulary, in one place.
 *
 * The palette follows Midday's discipline, which is stricter than it first
 * looks: the page is pure white, surfaces are a warm off-white, borders are a
 * warm grey, and *there is no accent colour in the data*. Their charts are
 * literally black. Colour is spent on one thing only — the fact that money
 * arrived — and spending it anywhere else would make that fact ordinary.
 *
 * The warmth sits in the surfaces, not the page. That inversion is what keeps
 * a near-monochrome screen from reading as grey and dead: white behind, paper
 * on top.
 *
 * Hierarchy comes from type scale and whitespace, not from boxes. Wrapping
 * every group in a border makes a dense screen unreadable — everything looks
 * equally important, so the reader must read all of it to find the one number
 * that matters. There are two containers and no more: `Panel` draws a hairline
 * because it holds a distinct object, `Region` draws nothing. Most are Regions.
 *
 * Numbers are large; prose is not. A control tower exists to show quantities,
 * and a headline that competes with the cash figure is in the wrong place.
 */
import type { ReactNode } from 'react'

export const tone = {
  page: '#ffffff',
  surface: '#f7f5f1',   // warm paper, Midday's card tone
  border: '#dcdad5',    // warm grey hairline
  line: '#eeece7',      // lighter divider, for rows inside a surface
  ink: '#121212',
  muted: '#616161',
  faint: '#9d9a94',
  ghost: '#c4c1ba',
  cash: '#16794a',      // the only chromatic value, and only for money in hand
  accent: '#ff4801',    // Guildless's mark. Two uses: progress, active nav.
} as const

/** Uppercase micro-label. Latin at every locale on purpose: it marks "this is
 *  a field name", and at 10px a mixed-script row loses the even rhythm that
 *  makes a label row scannable. */
export function Label({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <p className={`text-[10px] font-medium uppercase tracking-[0.09em] text-[#9d9a94] ${className}`}>
    {children}
  </p>
}

/** A quantity and what it is. The number carries the weight; the label whispers. */
export function Figure({ label, value, note, tone: shade = 'plain', size = 'lg' }: {
  label: string
  value: string
  note?: string
  tone?: 'plain' | 'cash' | 'muted'
  size?: 'lg' | 'md' | 'sm'
}) {
  const colour = shade === 'cash' ? 'text-[#16794a]' : shade === 'muted' ? 'text-[#9d9a94]' : 'text-[#121212]'
  const type = size === 'lg' ? 'text-[30px] leading-9' : size === 'md' ? 'text-xl leading-7' : 'text-base leading-6'
  return <div className='min-w-0'>
    <Label>{label}</Label>
    <p className={`mt-1.5 font-semibold tabular-nums tracking-[-0.02em] ${type} ${colour}`}>{value}</p>
    {note ? <p className='mt-1 truncate text-[11px] text-[#9d9a94]'>{note}</p> : null}
  </div>
}

/** A bordered surface, for a thing that is genuinely a separate object. */
export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-[#dcdad5] bg-[#f7f5f1] ${className}`}>
    {children}
  </section>
}

/** An unbordered group, separated by space alone — which is enough, and which
 *  keeps the page from becoming a grid of boxes. */
export function Region({ label, children, right, className = '' }: {
  label?: string
  children: ReactNode
  right?: ReactNode
  className?: string
}) {
  return <section className={`min-w-0 ${className}`}>
    {label ? (
      <div className='flex items-baseline gap-3'>
        <Label>{label}</Label>
        {right ? <div className='ml-auto'>{right}</div> : null}
      </div>
    ) : null}
    <div className={label ? 'mt-3' : ''}>{children}</div>
  </section>
}

const STATUS_STYLE: Record<string, string> = {
  // Money in hand is the one status that gets colour.
  PAYING: 'border-[#16794a]/30 bg-[#16794a]/[0.06] text-[#16794a]',
  SCALE: 'border-[#121212]/20 bg-[#121212]/[0.04] text-[#121212]',
  TEST: 'border-[#dcdad5] bg-white text-[#616161]',
  WATCH: 'border-[#e6e3dd] bg-transparent text-[#9d9a94]',
  // Drained and struck through rather than red: a dead bet should recede.
  KILLED: 'border-transparent bg-transparent text-[#c4c1ba] line-through',
}

export function Status({ value }: { value: string }) {
  return <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${
    STATUS_STYLE[value] ?? STATUS_STYLE.WATCH
  }`}>{value}</span>
}

/** Progress toward the one number that settles the run. */
export function Bar({ percent }: { percent: number }) {
  const clamped = Math.max(0, Math.min(100, percent))
  return <div className='h-1 w-full overflow-hidden rounded-full bg-[#eeece7]'>
    <div className='h-full rounded-full transition-[width] duration-500'
      style={{ width: `${clamped}%`, background: tone.accent }} />
  </div>
}

export const yen = (value: number) => {
  const rounded = Math.round(value || 0)
  const sign = rounded < 0 ? '-' : ''
  return `${sign}¥${Math.abs(rounded).toLocaleString('ja-JP')}`
}

/** Compact yen for tight columns: ¥1.2m, ¥740k. */
export const yenShort = (value: number) => {
  const n = Math.round(value || 0)
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1_000_000) return `${sign}¥${(abs / 1_000_000).toFixed(abs % 1_000_000 === 0 ? 0 : 1)}m`
  if (abs >= 10_000) return `${sign}¥${Math.round(abs / 1_000)}k`
  return `${sign}¥${abs.toLocaleString('ja-JP')}`
}
