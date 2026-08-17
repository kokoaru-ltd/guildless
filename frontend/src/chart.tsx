/**
 * Charts, drawn by hand.
 *
 * Following Midday's treatment, which is unusually severe and worth copying
 * exactly: no colour in the data, a dashed grid at #e6e6e6, axes with neither
 * line nor tick marks, and 10px labels in grey. The series itself is black.
 * Colour in a financial chart makes every series look like a category, and the
 * reader then spends attention working out what the palette means instead of
 * reading the shape.
 *
 * Hand-drawn rather than pulled from a library, because the whole requirement
 * is four elements — a dashed grid, an area, a line, and two axis labels — and
 * a charting dependency to draw those is several hundred kilobytes shipped to
 * an offline desktop app to save fifty lines.
 */

const GRID = '#e6e6e6'
const AXIS = '#707070'
const LINE = '#121212'

type Series = { label: string; points: number[] }

/**
 * Cumulative counts over the run. Several series share one scale, because
 * the funnel's whole meaning is how far each stage falls behind the one above
 * it — separate scales would draw four identical lines.
 */
export function TrendChart({ series, height = 132 }: { series: Series[]; height?: number }) {
  const width = 640
  const pad = { top: 8, right: 4, bottom: 16, left: 30 }
  const inner = { w: width - pad.left - pad.right, h: height - pad.top - pad.bottom }

  const longest = Math.max(...series.map(s => s.points.length), 2)
  const peak = Math.max(...series.flatMap(s => s.points), 1)

  const x = (index: number) => pad.left + (index / Math.max(longest - 1, 1)) * inner.w
  const y = (value: number) => pad.top + inner.h - (value / peak) * inner.h

  if (longest < 2) {
    return <div className='flex items-center' style={{ height }}>
      <p className='text-xs text-[#878787]'>まだ描けるだけの記録がありません。</p>
    </div>
  }

  return <svg viewBox={`0 0 ${width} ${height}`} className='w-full' style={{ height }}
    preserveAspectRatio='none' role='img'>
    {/* Grid: dashed, four rows, no vertical lines. Vertical rules add ink
        without adding a reading anyone takes off this chart. */}
    {[0, 0.25, 0.5, 0.75, 1].map(fraction => (
      <line
        key={fraction}
        x1={pad.left} x2={width - pad.right}
        y1={pad.top + inner.h * fraction} y2={pad.top + inner.h * fraction}
        stroke={GRID} strokeDasharray='3 3' strokeWidth={1}
      />
    ))}

    <text x={2} y={pad.top + 4} fill={AXIS} fontSize={10}>{peak}</text>
    <text x={2} y={pad.top + inner.h} fill={AXIS} fontSize={10}>0</text>

    {series.map((one, index) => {
      const path = one.points.map((value, i) => `${i ? 'L' : 'M'}${x(i)},${y(value)}`).join(' ')
      const leading = index === 0
      return <g key={one.label}>
        {leading && (
          // The first series gets a fill, which is what makes the chart read
          // as one quantity with others measured against it rather than four
          // unrelated lines.
          <path
            d={`${path} L${x(one.points.length - 1)},${pad.top + inner.h} L${x(0)},${pad.top + inner.h} Z`}
            fill={LINE} fillOpacity={0.05}
          />
        )}
        <path
          d={path} fill='none' stroke={LINE} strokeWidth={leading ? 1.5 : 1}
          strokeOpacity={leading ? 1 : 0.32 + 0.12 * (series.length - index)}
        />
      </g>
    })}
  </svg>
}

/** The funnel, as horizontal bars on a shared scale. */
export function FunnelChart({ rows }: { rows: [string, number][] }) {
  const top = Math.max(...rows.map(([, n]) => n), 1)
  return <ul className='space-y-2'>
    {rows.map(([name, count], index) => {
      const last = index === rows.length - 1
      return <li key={name} className='flex items-center gap-3'>
        <span className='w-[76px] shrink-0 text-xs text-[#878787]'>{name}</span>
        <div className='h-2 min-w-0 flex-1 bg-[#f2f2f2]'>
          <div
            className='h-full'
            style={{
              width: `${(count / top) * 100}%`,
              // Only money is green, and only when it exists. Every other
              // stage is a count, and a count is not an achievement.
              background: last && count > 0 ? '#16794a' : LINE,
              opacity: last && count > 0 ? 1 : 0.72 - index * 0.1,
            }}
          />
        </div>
        <span className='w-9 shrink-0 text-right text-xs font-medium tabular-nums'>{count}</span>
      </li>
    })}
  </ul>
}
