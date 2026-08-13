import { FormEvent, ReactNode, useCallback, useEffect, useState } from 'react'
import { Activity, Archive, CheckCircle2, Clock3, LoaderCircle, Menu, Megaphone, PanelLeftClose, PanelLeftOpen, Plus, ShieldCheck, Target, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CeoHome } from '@/ceo-home'
import { GuildlessMark } from '@/components/guildless-mark'
import { SalesMarketingView } from '@/sales-marketing-view'

type View = 'home' | 'growth' | 'work'
type Job = {
  job_id: string; status: string; objective: string; updated_at: string; repository?: string; summary?: string
  passed_test_count: number; output_file_count: number; external_actions_performed: boolean; approval_required: boolean
}
type JobPayload = { job_id: string; status: string; result?: Record<string, any>; external_actions_performed: boolean }
type Event = { sequence: number; status: string; occurred_at: string; details?: Record<string, any> }
type Artifact = { path: string; exists: boolean; size: number; sha256?: string }

const navItems = [
  { id: 'home' as const, label: '会社', description: '目標・要判断・リスク', icon: Target },
  { id: 'growth' as const, label: '売上', description: '営業・マーケ', icon: Megaphone },
  { id: 'work' as const, label: '実行', description: 'いま何をしているか', icon: Activity },
]

const terminalStates = new Set(['completed', 'degraded', 'partial', 'awaiting_approval', 'failed'])
const statusLabels: Record<string, string> = {
  queued: '開始待ち', researching: 'OSS調査中', analysis_researching: '材料収集中', analysis_proposing: '案を作成中',
  analysis_criticizing: '見落とし確認中', analysis_judging: '判断中', cloning: 'OSS準備中', implementing: '成果物を作成中',
  verifying: '結果を検証中', completed: '完了', degraded: '一部完了', partial: '要確認', awaiting_approval: '承認待ち', failed: '安全停止',
}
const workStages = [
  ['researching', '調べる'], ['analysis_proposing', '考える'], ['analysis_judging', '決める'],
  ['cloning', '準備'], ['implementing', '作る'], ['verifying', '確認'],
] as const

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail ? JSON.stringify(data.detail) : `HTTP ${response.status}`)
  return data as T
}

function safeText(value: unknown, fallback = '—') {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function stageIndex(status?: string) {
  if (!status) return -1
  if (status.startsWith('analysis_')) return status === 'analysis_judging' ? 2 : 1
  if (terminalStates.has(status)) return 5
  const found = workStages.findIndex(([id]) => id === status)
  return found < 0 ? 0 : found
}

function statusPercent(status?: string) {
  const progress: Record<string, number> = {
    queued: 5, researching: 15, analysis_researching: 25, analysis_proposing: 35, analysis_criticizing: 45,
    analysis_judging: 55, cloning: 65, implementing: 80, verifying: 92, awaiting_approval: 95,
    partial: 90, completed: 100, degraded: 100, failed: 0,
  }
  return status ? progress[status] ?? 10 : 0
}

export function GuildlessApp() {
  const [view, setView] = useState<View>('home')
  const [jobs, setJobs] = useState<Job[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(() => localStorage.getItem('guildless.currentJob'))
  const [job, setJob] = useState<JobPayload | null>(null)
  const [events, setEvents] = useState<Event[]>([])
  const [council, setCouncil] = useState<Record<string, any> | null>(null)
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [audit, setAudit] = useState<Record<string, any> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [delegateObjective, setDelegateObjective] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('guildless.sidebarCollapsed') !== 'false')

  const loadJobs = useCallback(async () => {
    const payload = await api<{ jobs: Job[] }>('/v1/guildless/jobs?limit=50')
    setJobs(payload.jobs)
    setSelectedId(current => current && payload.jobs.some(item => item.job_id === current) ? current : payload.jobs[0]?.job_id || null)
  }, [])

  const loadSelected = useCallback(async (jobId: string) => {
    const [jobData, eventData, councilData, artifactData, auditData] = await Promise.all([
      api<JobPayload>(`/v1/guildless/jobs/${encodeURIComponent(jobId)}`),
      api<{ events: Event[] }>(`/v1/guildless/jobs/${encodeURIComponent(jobId)}/events`),
      api<Record<string, any>>(`/v1/guildless/jobs/${encodeURIComponent(jobId)}/council`).catch(() => null),
      api<{ artifacts: Artifact[] }>(`/v1/guildless/jobs/${encodeURIComponent(jobId)}/artifacts`).catch(() => ({ artifacts: [] })),
      api<Record<string, any>>(`/v1/guildless/jobs/${encodeURIComponent(jobId)}/audit`).catch(() => null),
    ])
    setJob(jobData); setEvents(eventData.events || []); setCouncil(councilData); setArtifacts(artifactData.artifacts || []); setAudit(auditData)
    localStorage.setItem('guildless.currentJob', jobId)
  }, [])

  const refresh = useCallback(async () => {
    setError(''); setLoading(true)
    try { await loadJobs(); if (selectedId) await loadSelected(selectedId) }
    catch (reason) { setError(reason instanceof Error ? reason.message : '読み込みに失敗しました') }
    finally { setLoading(false) }
  }, [loadJobs, loadSelected, selectedId])

  useEffect(() => { loadJobs().catch(reason => setError(String(reason))).finally(() => setLoading(false)) }, [loadJobs])
  useEffect(() => { localStorage.setItem('guildless.sidebarCollapsed', String(sidebarCollapsed)) }, [sidebarCollapsed])
  useEffect(() => { if (selectedId) loadSelected(selectedId).catch(reason => setError(String(reason))) }, [selectedId, loadSelected])
  useEffect(() => {
    if (!job || terminalStates.has(job.status) || !selectedId) return
    const timer = window.setInterval(() => { loadSelected(selectedId).catch(() => undefined); loadJobs().catch(() => undefined) }, 1500)
    return () => window.clearInterval(timer)
  }, [job, selectedId, loadSelected, loadJobs])

  const page = navItems.find(item => item.id === view) || navItems[0]

  return <div className='h-svh overflow-hidden bg-[#f7f7f5] text-[#20201e]'>
    {sidebarOpen && <button className='fixed inset-0 z-30 bg-black/25 lg:hidden' onClick={() => setSidebarOpen(false)} aria-label='メニューを閉じる' />}
    <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-[#e6e5e1] bg-white transition-[width,transform] duration-200 lg:translate-x-0 ${sidebarCollapsed ? 'lg:w-[76px]' : 'lg:w-56'} ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
      <button className={`flex h-16 items-center border-b ${sidebarCollapsed ? 'justify-center' : 'gap-2.5 px-5'}`} onClick={() => setView('home')} aria-label='会社画面を開く'><GuildlessMark className='size-9 shrink-0' /><span className={`text-sm font-semibold ${sidebarCollapsed ? 'lg:hidden' : ''}`}>Guildless</span></button>
      <nav className='space-y-2 p-3' aria-label='メインナビゲーション'>
        {navItems.map(item => <button key={item.id} aria-label={item.label} aria-current={view === item.id ? 'page' : undefined} title={sidebarCollapsed ? item.label : undefined} onClick={() => { setView(item.id); setSidebarOpen(false) }} className={`flex w-full items-center rounded-xl py-3 text-left ${sidebarCollapsed ? 'justify-center px-2' : 'gap-3 px-3'} ${view === item.id ? 'bg-[#171513] text-white' : 'text-[#6f6b64] hover:bg-[#f3f1ed]'}`}><item.icon className='size-[18px] shrink-0' /><span className={sidebarCollapsed ? 'lg:hidden' : ''}><span className='block text-sm font-semibold'>{item.label}</span><span className={`block text-[10px] ${view === item.id ? 'text-white/55' : 'text-[#99958d]'}`}>{item.description}</span></span></button>)}
      </nav>
      <div className='mt-auto border-t p-3'>
        <div className={`flex items-center text-[#276453] ${sidebarCollapsed ? 'justify-center' : 'gap-2 px-2'}`} title='承認なしの外部作用 0'><ShieldCheck className='size-4 shrink-0' /><span className={`text-[10px] font-semibold ${sidebarCollapsed ? 'lg:hidden' : ''}`}>外部作用 0</span></div>
        <button className={`mt-3 hidden h-9 w-full items-center rounded-lg text-xs text-[#77736d] hover:bg-[#f3f1ed] lg:flex ${sidebarCollapsed ? 'justify-center' : 'gap-2 px-2'}`} onClick={() => setSidebarCollapsed(value => !value)} aria-label={sidebarCollapsed ? 'サイドバーを開く' : 'サイドバーを閉じる'}>{sidebarCollapsed ? <PanelLeftOpen className='size-4' /> : <><PanelLeftClose className='size-4' />閉じる</>}</button>
      </div>
    </aside>

    <div className={`h-svh transition-[padding] duration-200 ${sidebarCollapsed ? 'lg:pl-[76px]' : 'lg:pl-56'}`}>
      <header className='flex h-16 items-center gap-3 border-b border-[#e6e5e1] bg-white px-4 lg:px-7'>
        <button className='rounded-md p-2 hover:bg-[#f3f1ed] lg:hidden' onClick={() => setSidebarOpen(true)} aria-label='メニューを開く'><Menu className='size-5' /></button>
        <div className='min-w-0 flex-1'><p className='text-sm font-semibold'>{page.label}</p><p className='truncate text-xs text-[#817d76]'>{page.description}</p></div>
        {loading && <LoaderCircle className='size-4 animate-spin text-[#817d76]' />}
      </header>

      <main className='mx-auto h-[calc(100svh-4rem)] max-w-[1480px] overflow-hidden p-4 lg:p-7'>
        {error && <div className='absolute right-5 top-20 z-20 flex max-w-lg items-center gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700 shadow-lg'><span className='line-clamp-2'>{error}</span><button onClick={() => setError('')} aria-label='エラーを閉じる'><X className='size-4' /></button></div>}
        {view === 'home' && <CeoHome jobs={jobs} selectedJob={job} />}
        {view === 'growth' && <SalesMarketingView />}
        {view === 'work' && <ExecutionView jobs={jobs} selectedId={selectedId} onSelect={setSelectedId} job={job} events={events} council={council} artifacts={artifacts} audit={audit} onNew={() => { setDelegateObjective(''); setCreateOpen(true) }} onRefresh={refresh} />}
      </main>
    </div>
    {createOpen && <CreateDialog initialObjective={delegateObjective} onClose={() => setCreateOpen(false)} onCreated={id => { setCreateOpen(false); setSelectedId(id); setView('work') }} />}
  </div>
}

function ExecutionView({ jobs, selectedId, onSelect, job, events, council, artifacts, audit, onNew, onRefresh }: {
  jobs: Job[]; selectedId: string | null; onSelect: (id: string) => void; job: JobPayload | null; events: Event[]
  council: Record<string, any> | null; artifacts: Artifact[]; audit: Record<string, any> | null; onNew: () => void; onRefresh: () => void
}) {
  const selected = jobs.find(item => item.job_id === selectedId)
  const currentStatus = job?.status || selected?.status
  const currentStage = stageIndex(currentStatus)
  const completion = statusPercent(currentStatus)
  const decision = council?.decision || {}
  const verifiedArtifacts = artifacts.filter(item => item.exists).length
  const sourceUnchanged = audit?.verification?.source_unchanged
  const recent = events.slice(-3).reverse()

  return <div className='grid h-[calc(100svh-7.5rem)] min-h-[620px] grid-rows-[auto_1fr] gap-3 overflow-hidden'>
    <section className='flex items-center gap-3 rounded-[18px] border border-[#dedbd4] bg-white px-4 py-3'>
      <div className='min-w-0 flex-1'><p className='text-[10px] font-semibold tracking-[.12em] text-[#817d76]'>OPERATIONS</p><h1 className='truncate text-lg font-semibold'>Guildlessはいま何をしているか</h1></div>
      <select value={selectedId || ''} onChange={event => onSelect(event.target.value)} aria-label='仕事を選択' className='max-w-[360px] rounded-xl border border-[#dedbd4] bg-white px-3 py-2 text-xs outline-none'>{jobs.length ? jobs.map(item => <option key={item.job_id} value={item.job_id}>{item.objective}</option>) : <option value=''>仕事はありません</option>}</select>
      <button onClick={onRefresh} className='rounded-xl border border-[#dedbd4] px-3 py-2 text-xs font-medium'>更新</button>
      <Button onClick={onNew} className='h-9 rounded-xl bg-[#171513] px-4 text-white hover:bg-black'><Plus className='size-4' />仕事を追加</Button>
    </section>

    <section className='grid min-h-0 gap-3 lg:grid-cols-[1.2fr_.8fr]'>
      <div className='grid min-h-0 grid-rows-[auto_1fr] gap-3'>
        <div className='rounded-[20px] border border-[#dedbd4] bg-white p-5'>
          <div className='flex items-start justify-between gap-4'><div className='min-w-0'><p className='text-xs text-[#817d76]'>現在の仕事</p><h2 className='mt-1 line-clamp-2 text-xl font-semibold leading-7'>{selected?.objective || 'まだ仕事がありません'}</h2></div><span className='shrink-0 rounded-full bg-[#fff1e9] px-3 py-1.5 text-xs font-semibold text-[#b94b1b]'>完成まで {completion}% · {statusLabels[currentStatus || ''] || '待機中'}</span></div>
          <div className='mt-4 h-2 overflow-hidden rounded-full bg-[#ece9e3]'><div className='h-full rounded-full bg-[#ff6b32]' style={{ width: `${completion}%` }} /></div>
          <div className='mt-4 grid grid-cols-6 gap-2'>{workStages.map(([id, label], index) => <div key={id} className='min-w-0'><p className={`truncate text-center text-[10px] ${index === currentStage ? 'font-semibold text-[#171513]' : 'text-[#99958d]'}`}>{label}</p></div>)}</div>
        </div>

        <div className='grid min-h-0 gap-3 md:grid-cols-2'>
          <div className='min-h-0 rounded-[20px] border border-[#dedbd4] bg-white p-5'><p className='text-xs font-semibold'>直近の動き</p><div className='mt-3 space-y-3'>{recent.length ? recent.map(event => <div key={event.sequence} className='flex gap-3'><span className='mt-1.5 size-2 shrink-0 rounded-full bg-[#ff6b32]' /><div className='min-w-0'><p className='text-xs font-semibold'>{statusLabels[event.status] || event.status}</p><p className='mt-1 line-clamp-2 text-[11px] leading-4 text-[#817d76]'>{safeText(event.details?.message, safeText(event.details?.summary, '処理を記録しました'))}</p></div></div>) : <p className='text-xs text-[#817d76]'>動きはまだありません。</p>}</div></div>
          <div className='min-h-0 rounded-[20px] bg-[#171513] p-5 text-white'><p className='text-[10px] font-semibold tracking-[.12em] text-white/45'>DECISION</p><h3 className='mt-2 text-base font-semibold'>経営判断</h3><p className='mt-3 line-clamp-6 text-xs leading-5 text-white/65'>{safeText(decision.decision, council?.available === false ? council.message : 'Councilの判断はまだありません。')}</p><p className='mt-4 text-[10px] text-[#ff9d75]'>反論・監査は内部で保持し、経営者には結論と要判断だけを表示</p></div>
        </div>
      </div>

      <div className='grid min-h-0 grid-rows-4 gap-3'>
        <ExecMetric icon={<Clock3 />} label='人間の判断' value={selected?.approval_required || job?.status === 'awaiting_approval' ? '承認が必要' : 'いまは不要'} detail={selected?.approval_required ? '外部作用の前で停止中' : 'Guildlessが継続できます'} alert={Boolean(selected?.approval_required)} />
        <ExecMetric icon={<Archive />} label='成果物' value={`${verifiedArtifacts}件`} detail={artifacts.length ? `${artifacts.length}件中 ${verifiedArtifacts}件を実在確認` : 'まだ成果物はありません'} />
        <ExecMetric icon={<CheckCircle2 />} label='検証' value={`${selected?.passed_test_count || 0} tests`} detail={sourceUnchanged === true ? '固定OSS原本は変更なし' : sourceUnchanged === false ? '原本変更を検出' : '検証結果待ち'} alert={sourceUnchanged === false} />
        <ExecMetric icon={<ShieldCheck />} label='外部作用' value={selected?.external_actions_performed || job?.external_actions_performed ? '検出' : '0件'} detail='送信・契約・支払いは承認まで停止' alert={Boolean(selected?.external_actions_performed || job?.external_actions_performed)} />
      </div>
    </section>
  </div>
}

function ExecMetric({ icon, label, value, detail, alert = false }: { icon: ReactNode; label: string; value: string; detail: string; alert?: boolean }) {
  return <div className={`flex min-h-0 items-center gap-4 rounded-[18px] border p-4 ${alert ? 'border-[#efc8b7] bg-[#fff6f1]' : 'border-[#dedbd4] bg-white'}`}><span className={`grid size-10 shrink-0 place-items-center rounded-xl ${alert ? 'bg-[#ffe7da] text-[#b94b1b]' : 'bg-[#f3f1ed] text-[#6f6b64]'} [&>svg]:size-4`}>{icon}</span><div className='min-w-0'><p className='text-[10px] font-semibold text-[#817d76]'>{label}</p><p className='mt-0.5 text-lg font-semibold'>{value}</p><p className='truncate text-[10px] text-[#817d76]'>{detail}</p></div></div>
}

function CreateDialog({ initialObjective, onClose, onCreated }: { initialObjective?: string; onClose: () => void; onCreated: (id: string) => void }) {
  const [objective, setObjective] = useState(initialObjective || '')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const submit = async (event: FormEvent) => {
    event.preventDefault(); if (!objective.trim()) return; setSubmitting(true); setError('')
    try {
      const data = await api<{ run_id: string }>('/v1/guildless/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        objective: objective.trim(), github_queries: ['sales marketing automation OSS', 'agent workflow approval audit'], context: {},
        allowed_providers: ['deepseek', 'codex'], workspace_label: 'ui', max_rounds: 1, max_execution_minutes: 20,
        constraints: { license_allowlist: ['MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause'], min_stars: 0, max_candidates: 10, active_within_days: 730 },
      }) })
      onCreated(data.run_id)
    } catch (reason) { setError(reason instanceof Error ? reason.message : '開始できませんでした') }
    finally { setSubmitting(false) }
  }
  return <div className='fixed inset-0 z-50 grid place-items-center bg-black/30 p-4' role='dialog' aria-modal='true' aria-label='仕事を追加'><form onSubmit={submit} className='w-full max-w-xl rounded-[22px] border bg-white p-6 shadow-2xl'><div className='flex items-start justify-between'><div><p className='text-[10px] font-semibold tracking-[.12em] text-[#817d76]'>NEW WORK</p><h2 className='mt-1 text-xl font-semibold'>何を任せますか？</h2></div><button type='button' onClick={onClose} aria-label='閉じる' className='rounded-lg p-2 hover:bg-[#f3f1ed]'><X className='size-4' /></button></div><textarea autoFocus required value={objective} onChange={event => setObjective(event.target.value)} placeholder='例：今月の新規営業で優先すべき企業を選び、接触案を作る' className='mt-5 h-32 w-full resize-none rounded-2xl border border-[#dedbd4] p-4 text-base leading-7 outline-none focus:border-[#ff6b32]' />{error && <p className='mt-2 text-xs text-red-700'>{error}</p>}<div className='mt-5 flex items-center justify-between'><p className='text-[10px] text-[#817d76]'>外部送信・契約・支払いは行いません</p><Button type='submit' disabled={!objective.trim() || submitting} className='h-11 rounded-xl bg-[#ff4801] px-5 text-white hover:bg-[#e54100]'>{submitting ? <LoaderCircle className='size-4 animate-spin' /> : <Plus className='size-4' />}{submitting ? '開始中' : '任せる'}</Button></div></form></div>
}
