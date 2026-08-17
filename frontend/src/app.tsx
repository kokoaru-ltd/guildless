/**
 * The control tower.
 *
 * Six destinations, and Council, agents, models, MCP and skills are in none of
 * them. Those are how Guildless is built, not what the company is doing, and
 * putting them in the sidebar makes the owner responsible for machinery they
 * were promised they would not have to run. An owner who never learns the word
 * "council" has lost nothing.
 *
 * Nothing here is a chat. Instructions go through a command bar that does not
 * exist until it is summoned, so the resting state of the product is a company
 * operating rather than a prompt waiting to be filled.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  Activity as ActivityIcon, Boxes, Command, LayoutDashboard,
  LoaderCircle, Settings as SettingsIcon, Target, Wallet,
} from 'lucide-react'
import { Activity, Assets, Business, Revenue, Settings } from '@/screens'
import { Overview } from '@/overview'
import { CommandBar } from '@/command-bar'
import type { Company } from '@/types'

const SECTIONS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'business', label: 'Business', icon: Target },
  { id: 'revenue', label: 'Revenue', icon: Wallet },
  { id: 'assets', label: 'Assets', icon: Boxes },
  { id: 'activity', label: 'Activity', icon: ActivityIcon },
] as const

type SectionId = (typeof SECTIONS)[number]['id'] | 'settings'

export function App() {
  const [data, setData] = useState<Company | null>(null)
  const [environment, setEnvironment] = useState<any>(null)
  const [section, setSection] = useState<SectionId>('overview')
  const [openBet, setOpenBet] = useState<string | null>(null)
  const [commandOpen, setCommandOpen] = useState(false)
  const [unreachable, setUnreachable] = useState(false)

  const load = useCallback(async () => {
    try {
      const response = await fetch('/v1/company')
      if (!response.ok) throw new Error()
      setData(await response.json())
      setUnreachable(false)
    } catch { setUnreachable(true) }
  }, [])

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => void load(), 5000)
    return () => window.clearInterval(timer)
  }, [load])

  useEffect(() => {
    void fetch('/v1/environment').then(r => r.json()).then(setEnvironment).catch(() => undefined)
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen(open => !open)
      }
      if (event.key === 'Escape') setCommandOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const show = (next: SectionId) => { setSection(next); setOpenBet(null) }

  if (!data) {
    return <div className='grid h-svh place-items-center bg-white text-[#121212]'>
      {unreachable
        ? <p className='text-sm text-[#c23a08]'>Guildlessに接続できません。</p>
        : <LoaderCircle className='size-5 animate-spin text-[#9d9a94]' />}
    </div>
  }

  return <div className='flex h-svh w-full overflow-hidden bg-white text-[#121212]'>
    <aside className='flex w-[188px] shrink-0 flex-col border-r border-[#dcdad5] bg-white'>
      <div className='flex h-12 shrink-0 items-center px-4'>
        <span className='text-[13px] font-semibold tracking-tight'>GUILDLESS</span>
      </div>
      <nav className='flex flex-col gap-0.5 px-2'>
        {SECTIONS.map(({ id, label, icon: Icon }) => (
          <button
            key={id} onClick={() => show(id)}
            className={`flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[13px] ${
              section === id
                ? 'bg-[#f7f5f1] font-medium text-[#121212]'
                : 'text-[#616161] hover:bg-[#f7f5f1]'
            }`}
          >
            <Icon className='size-[15px]' strokeWidth={1.75} />{label}
          </button>
        ))}
      </nav>
      <div className='mt-auto border-t border-[#eeece7] p-2'>
        <button
          onClick={() => show('settings')}
          className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[13px] ${
            section === 'settings'
              ? 'bg-[#f7f5f1] font-medium text-[#121212]'
              : 'text-[#616161] hover:bg-[#f7f5f1]'
          }`}
        >
          <SettingsIcon className='size-[15px]' strokeWidth={1.75} />Settings
        </button>
      </div>
    </aside>

    <div className='flex min-w-0 flex-1 flex-col'>
      <header className='flex h-12 shrink-0 items-center gap-3 border-b border-[#dcdad5] bg-white px-5'>
        {data.company ? (
          <span className='text-[13px] text-[#616161]'>
            Company <span className='ml-1 font-medium text-[#121212]'>{data.company}</span>
          </span>
        ) : null}

        {/* State, stated. It reads from the worker's heartbeat, so it cannot
            say Operating while nothing is executing. */}
        <span className='flex items-center gap-1.5 text-[12px]'>
          <span className={`size-[6px] rounded-full ${data.operating ? 'bg-[#16794a]' : 'bg-[#c0bcb4]'}`} />
          <span className={data.operating ? 'text-[#16794a]' : 'text-[#9d9a94]'}>
            {data.operating ? 'Operating' : 'Stopped'}
          </span>
        </span>

        <button
          onClick={() => setCommandOpen(true)}
          className='ml-auto flex items-center gap-1.5 rounded-md border border-[#dcdad5] px-2 py-1 text-[11px] text-[#9d9a94] hover:bg-[#f7f5f1]'
        >
          <Command className='size-3' />K
        </button>
      </header>

      <main className='min-h-0 flex-1 overflow-hidden'>
        {section === 'overview' && (
          <Overview data={data} onOpenBet={id => { setSection('business'); setOpenBet(id) }} />
        )}
        {section === 'business' && <Business data={data} openId={openBet} onOpen={setOpenBet} />}
        {section === 'revenue' && <Revenue data={data} />}
        {section === 'assets' && <Assets />}
        {section === 'activity' && <Activity items={data.activity} />}
        {section === 'settings' && <Settings environment={environment} />}
      </main>
    </div>

    {commandOpen && <CommandBar onClose={() => setCommandOpen(false)} onRan={load} />}
  </div>
}
