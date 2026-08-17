/**
 * The visual vocabulary, taken from Midday's components rather than its tokens.
 *
 * Reading their CSS variables was not enough and produced the wrong thing. The
 * actual specification lives in the components, and it is more severe than the
 * palette suggests:
 *
 * * **Square.** Their data surfaces carry `border` with no radius at all.
 *   Rounding is reserved for things that are not data — avatars, icon tiles,
 *   10px chips. A grid of rounded cards reads as an app; a grid of square
 *   bordered cells reads as a statement, which is what this is.
 * * **White, not warm.** The warm card token is used for popovers. The widget
 *   cards are `bg-white` with a `#e6e6e6` hairline.
 * * **Small numbers.** `text-xl font-medium`, not a display-size figure.
 *   Everything on the screen is a quantity, so making them all large makes
 *   none of them prominent — the hierarchy has to come from position.
 * * **Quiet labels.** `text-xs` in muted grey, sentence case. Not uppercase,
 *   not letter-spaced. A label that has to be decoded is a label competing
 *   with its own value.
 * * **No colour in data.** Their charts are black on a dashed grey grid.
 *
 * Colour is spent here on exactly one fact — money that arrived — so that fact
 * stays remarkable. Nothing else on the screen is allowed to be green.
 */
import type { ReactNode } from 'react'

export const tone = {
  ink: '#121212',
  muted: '#878787',
  faint: '#a8a8a8',
  border: '#e6e6e6',
  borderStrong: '#d0d0d0',
  hover: '#f7f7f7',
  track: '#f2f2f2',
  cash: '#16794a',
  warn: '#b45309',
} as const

/** A quiet field name. Sentence case, muted, no tracking. */
export function Label({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`text-xs text-[#878787] ${className}`}>{children}</span>
}

/**
 * A bordered cell holding one quantity.
 *
 * Label at the top, value at the bottom, detail inline beside the value —
 * Midday's arrangement, and it works because the labels align across the row
 * regardless of how long each one is, so the eye can run along the values.
 */
export function Cell({ label, value, detail, tone: shade = 'plain', href }: {
  label: string
  value: string
  detail?: string
  tone?: 'plain' | 'cash' | 'muted'
  href?: () => void
}) {
  const colour = shade === 'cash' ? 'text-[#16794a]' : shade === 'muted' ? 'text-[#878787]' : ''
  const body = <>
    <Label>{label}</Label>
    <div className='mt-3 flex items-baseline gap-2'>
      <span className={`text-xl font-medium tabular-nums ${colour}`}>{value}</span>
      {detail ? <span className='truncate text-xs text-[#878787]'>{detail}</span> : null}
    </div>
  </>
  const shell = 'flex min-h-[110px] flex-col justify-between border border-[#e6e6e6] bg-white p-5 text-left'
  return href
    ? <button onClick={href} className={`${shell} transition-colors hover:border-[#d0d0d0] hover:bg-[#f7f7f7]`}>{body}</button>
    : <div className={shell}>{body}</div>
}

/** A square bordered surface for anything that is not a single quantity. */
export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`border border-[#e6e6e6] bg-white ${className}`}>{children}</section>
}

/** A titled group with no border of its own. */
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

// Midday's chip: 10px, 22px tall, bordered, and the one place a small radius
// is allowed.
const CHIP = 'inline-flex h-[22px] shrink-0 items-center rounded-md border px-2 text-[10px] font-medium'

const STATUS_STYLE: Record<string, string> = {
  PAYING: 'border-[#16794a]/30 bg-[#16794a]/[0.06] text-[#16794a]',
  SCALE: 'border-[#d0d0d0] bg-white text-[#121212]',
  TEST: 'border-[#e6e6e6] bg-white text-[#878787]',
  WATCH: 'border-[#e6e6e6] bg-white text-[#a8a8a8]',
  // Drained rather than red. A dead bet should recede, not shout.
  KILLED: 'border-transparent bg-transparent text-[#c4c4c4] line-through',
}

export function Status({ value }: { value: string }) {
  return <span className={`${CHIP} ${STATUS_STYLE[value] ?? STATUS_STYLE.WATCH}`}>{value}</span>
}

/** Progress toward the one number that settles the run. */
export function Bar({ percent }: { percent: number }) {
  const clamped = Math.max(0, Math.min(100, percent))
  return <div className='h-1.5 w-full bg-[#f2f2f2]'>
    <div className='h-full bg-[#121212] transition-[width] duration-500' style={{ width: `${clamped}%` }} />
  </div>
}

export const yen = (value: number) => {
  const rounded = Math.round(value || 0)
  return `${rounded < 0 ? '-' : ''}¥${Math.abs(rounded).toLocaleString('ja-JP')}`
}

export const yenShort = (value: number) => {
  const n = Math.round(value || 0)
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1_000_000) return `${sign}¥${(abs / 1_000_000).toFixed(abs % 1_000_000 === 0 ? 0 : 1)}m`
  if (abs >= 10_000) return `${sign}¥${Math.round(abs / 1_000)}k`
  return `${sign}¥${abs.toLocaleString('ja-JP')}`
}
