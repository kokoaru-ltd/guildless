import { cn } from '@/lib/utils'

export function GuildlessMark({ className, framed = true }: { className?: string; framed?: boolean }) {
  return (
    <span className={cn('relative inline-grid shrink-0 place-items-center', framed && 'rounded-xl bg-[#171513] shadow-[0_5px_14px_rgba(23,21,19,.18)]', className)} aria-hidden='true'>
      <svg viewBox='0 0 32 32' fill='none' className='size-[70%]'>
        <path d='M8 9.25 16 15m8-5.75L16 15m0 0v8' stroke='white' strokeWidth='2.2' strokeLinecap='round' strokeLinejoin='round' opacity='.82' />
        <circle cx='8' cy='8' r='3.25' fill='#FF8A5C' />
        <circle cx='24' cy='8' r='3.25' fill='#FFB08F' />
        <circle cx='16' cy='24' r='3.25' fill='white' />
        <path d='m16 11 4 4-4 4-4-4 4-4Z' fill='#FF4801' stroke='#171513' strokeWidth='1.2' />
      </svg>
    </span>
  )
}
