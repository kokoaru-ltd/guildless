import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  Archive,
  ArrowRight,
  Bot,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  Clock3,
  Code2,
  FileCode2,
  FileText,
  GitBranch,
  History,
  Home,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  UsersRound,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CeoHome } from '@/ceo-home'
import { GuildlessMark } from '@/components/guildless-mark'

type View = 'home' | 'operations' | 'council' | 'artifacts' | 'audit'
type Job = {
  job_id: string
  status: string
  objective: string
  updated_at: string
  repository?: string
  summary?: string
  passed_test_count: number
  output_file_count: number
  external_actions_performed: boolean
  approval_required: boolean
}
type JobPayload = {
  job_id: string
  status: string
  result?: Record<string, any>
  execution_audit?: Record<string, any>
  external_actions_performed: boolean
}
type Event = { sequence: number; status: string; occurred_at: string; details?: Record<string, any> }
type Artifact = { path: string; exists: boolean; size: number; sha256?: string; preview?: string }

const navItems: Array<{ id: View; label: string; description: string; icon: typeof LayoutDashboard }> = [
  { id: 'home', label: '経営デスク', description: '話す・考える・決める', icon: Home },
  { id: 'council', label: '経営会議', description: '複数の視点で比較', icon: UsersRound },
  { id: 'operations', label: '仕事の状況', description: 'オペレーション詳細', icon: LayoutDashboard },
  { id: 'artifacts', label: '成果物', description: '作ったものを確認', icon: Archive },
  { id: 'audit', label: '安全と監査', description: '根拠と外部作用', icon: ClipboardCheck },
]

const statusLabels: Record<string, string> = {
  queued: '待機中', researching: 'OSS調査中', analysis_researching: '候補分析中', analysis_proposing: '提案作成中',
  analysis_criticizing: '反論検証中', analysis_judging: '最終判断中', analysis_completed: 'Council完了',
  analysis_degraded: '縮退運転', cloning: '固定コミット取得中', implementing: '実装中', verifying: '検証中',
  completed: '完了', degraded: '縮退完了', partial: '要確認', awaiting_approval: '承認待ち', failed: '失敗',
}

const pipeline = [
  ['researching', 'OSSを選ぶ', 'ライセンスと更新状態を確認'],
  ['analysis_proposing', '独立提案', '複数モデルが別々に検討'],
  ['analysis_judging', 'Council判断', '反論を踏まえて候補を決定'],
  ['cloning', '固定取得', '採用コミットを再現可能に保存'],
  ['implementing', '実装', '隔離領域で成果物を作成'],
  ['verifying', '検証', 'テスト・ハッシュ・外部作用を確認'],
] as const

const terminalStates = new Set(['completed', 'degraded', 'partial', 'awaiting_approval', 'failed'])

function shortId(value = '') { return value.length > 30 ? `${value.slice(0, 18)}…${value.slice(-7)}` : value }
function formatDate(value?: string) { return value ? new Intl.DateTimeFormat('ja-JP', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '—' }
function formatSize(bytes = 0) { return bytes < 1024 ? `${bytes} B` : bytes < 1024 ** 2 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 ** 2).toFixed(1)} MB` }
function safeText(value: unknown, fallback = '—') {
  if (typeof value === 'string' && value.trim()) return value
  if (typeof value === 'number') return String(value)
  return fallback
}

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail ? JSON.stringify(data.detail) : `HTTP ${response.status}`)
  return data as T
}

function StatusBadge({ status }: { status: string }) {
  const tone = status === 'completed' ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : status === 'failed' ? 'bg-red-50 text-red-700 ring-red-200' : terminalStates.has(status) ? 'bg-amber-50 text-amber-700 ring-amber-200' : 'bg-blue-50 text-blue-700 ring-blue-200'
  return <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${tone}`}><span className='size-1.5 rounded-full bg-current' />{statusLabels[status] || status}</span>
}

function Empty({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return <div className='flex min-h-52 flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 px-6 text-center'>
    <div className='mb-3 rounded-lg border bg-background p-2 text-muted-foreground'>{icon}</div>
    <p className='text-sm font-medium'>{title}</p><p className='mt-1 max-w-sm text-xs leading-5 text-muted-foreground'>{body}</p>
  </div>
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('guildless.sidebarCollapsed') === 'true')
  const [artifact, setArtifact] = useState<Artifact | null>(null)
  const [councilTab, setCouncilTab] = useState<'decision' | 'proposals' | 'criticism'>('decision')

  const loadJobs = useCallback(async () => {
    const payload = await api<{ jobs: Job[] }>('/v1/guildless/jobs?limit=50')
    setJobs(payload.jobs)
    setSelectedId(current => {
      if (current && payload.jobs.some(item => item.job_id === current)) return current
      return payload.jobs[0]?.job_id || null
    })
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
    try {
      await loadJobs()
      if (selectedId) await loadSelected(selectedId)
    } catch (e) { setError(e instanceof Error ? e.message : '読み込みに失敗しました') }
    finally { setLoading(false) }
  }, [loadJobs, loadSelected, selectedId])

  useEffect(() => { loadJobs().catch(e => setError(String(e))).finally(() => setLoading(false)) }, [loadJobs])
  useEffect(() => { localStorage.setItem('guildless.sidebarCollapsed', String(sidebarCollapsed)) }, [sidebarCollapsed])
  useEffect(() => { if (selectedId) loadSelected(selectedId).catch(e => setError(String(e))) }, [selectedId, loadSelected])
  useEffect(() => {
    if (!job || terminalStates.has(job.status) || !selectedId) return
    const timer = window.setInterval(() => { loadSelected(selectedId).catch(() => undefined); loadJobs().catch(() => undefined) }, 1500)
    return () => window.clearInterval(timer)
  }, [job, selectedId, loadSelected, loadJobs])

  const selectedSummary = jobs.find(item => item.job_id === selectedId)
  const pageTitle = navItems.find(item => item.id === view)?.label || 'Guildless'

  return <div className='min-h-screen bg-[#f7f7f5] text-[#20201e]'>
    {sidebarOpen && <button className='fixed inset-0 z-30 bg-black/25 backdrop-blur-[1px] lg:hidden' onClick={() => setSidebarOpen(false)} aria-label='サイドバーを閉じる' />}
    <aside className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-[#e6e5e1] bg-white transition-[width,transform] duration-200 lg:translate-x-0 ${sidebarCollapsed ? 'lg:w-[76px]' : 'lg:w-64'} ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
      <div className={`flex h-16 items-center border-b ${sidebarCollapsed ? 'lg:justify-center lg:px-3' : 'justify-between px-5'}`}>
        <button className='flex min-w-0 items-center gap-2.5' onClick={() => setView('home')} aria-label='Guildless 経営デスクを開く' title={sidebarCollapsed ? 'Guildless' : undefined}>
          <GuildlessMark className='size-9 shrink-0' />
          <span className={`truncate text-[15px] font-semibold tracking-tight ${sidebarCollapsed ? 'lg:hidden' : ''}`}>Guildless</span>
        </button>
        <button className='rounded-md p-1.5 text-muted-foreground hover:bg-muted lg:hidden' onClick={() => setSidebarOpen(false)} aria-label='サイドバーを閉じる'><X className='size-4' /></button>
      </div>
      <div className='px-3 py-4'>
        <p className={`px-2 pb-2 text-[11px] font-medium uppercase tracking-[.14em] text-muted-foreground ${sidebarCollapsed ? 'lg:hidden' : ''}`}>会社</p>
        <div className={`mb-5 flex items-center rounded-lg border bg-[#fafaf9] ${sidebarCollapsed ? 'justify-center p-2 lg:border-transparent lg:bg-transparent' : 'gap-3 p-3'}`} title={sidebarCollapsed ? 'Guildless Lab・安全運転中' : undefined}>
          <span className='relative grid size-8 shrink-0 place-items-center rounded-md border bg-white'><GuildlessMark className='size-6' /><span className='absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full border-2 border-white bg-emerald-500' /></span>
          <div className={`min-w-0 flex-1 ${sidebarCollapsed ? 'lg:hidden' : ''}`}><p className='truncate text-sm font-medium'>Guildless Lab</p><p className='text-xs text-muted-foreground'>安全運転中</p></div>
          <ChevronDown className={`size-4 text-muted-foreground ${sidebarCollapsed ? 'lg:hidden' : ''}`} />
        </div>
        <nav className='space-y-1' aria-label='メインナビゲーション'>
          {navItems.map(item => <button key={item.id} title={sidebarCollapsed ? item.label : undefined} aria-label={item.label} aria-current={view === item.id ? 'page' : undefined} onClick={() => { setView(item.id); setSidebarOpen(false) }} className={`group flex w-full items-center rounded-md py-2.5 text-left transition-colors ${sidebarCollapsed ? 'justify-center px-2 lg:h-11' : 'gap-3 px-3'} ${view === item.id ? 'bg-[#f0f0ed] text-[#171716]' : 'text-[#666560] hover:bg-[#f6f6f3] hover:text-[#171716]'}`}>
            <item.icon className='size-[18px] shrink-0' /><span className={`min-w-0 flex-1 ${sidebarCollapsed ? 'lg:hidden' : ''}`}><span className='block text-sm font-medium'>{item.label}</span><span className='block text-[11px] text-muted-foreground'>{item.description}</span></span>
          </button>)}
        </nav>
      </div>
      <div className={`mt-auto border-t py-4 ${sidebarCollapsed ? 'px-3' : 'px-5'}`}>
        <div className={`flex items-center text-xs text-muted-foreground ${sidebarCollapsed ? 'justify-center' : 'gap-2'}`} title={sidebarCollapsed ? '承認なしの外部作用 0' : undefined}><ShieldCheck className='size-4 shrink-0 text-emerald-600' /><span className={sidebarCollapsed ? 'lg:hidden' : ''}>承認なしの外部作用 0</span></div>
        <p className={`mt-2 text-[10px] leading-4 text-muted-foreground ${sidebarCollapsed ? 'lg:hidden' : ''}`}>Cloudflare OS UI patterns (Apache-2.0)</p>
        <button className={`mt-4 hidden h-9 w-full items-center rounded-md text-xs font-medium text-muted-foreground transition hover:bg-[#f3f3f0] hover:text-[#171716] lg:flex ${sidebarCollapsed ? 'justify-center' : 'gap-2 px-2'}`} onClick={() => setSidebarCollapsed(value => !value)} aria-label={sidebarCollapsed ? 'サイドバーを開く' : 'サイドバーを閉じる'} title={sidebarCollapsed ? 'サイドバーを開く' : undefined}>
          {sidebarCollapsed ? <PanelLeftOpen className='size-4' /> : <><PanelLeftClose className='size-4' /><span>サイドバーを閉じる</span></>}
        </button>
      </div>
    </aside>

    <div className={`transition-[padding] duration-200 ${sidebarCollapsed ? 'lg:pl-[76px]' : 'lg:pl-64'}`}>
      <header className='sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-[#e6e5e1] bg-white/95 px-4 backdrop-blur lg:px-8'>
        <button className='rounded-md p-2 hover:bg-muted lg:hidden' onClick={() => setSidebarOpen(true)} aria-label='メニューを開く'><Menu className='size-5' /></button>
        <div className='min-w-0 flex-1'><p className='truncate text-sm font-semibold'>{pageTitle}</p><p className='truncate text-xs text-muted-foreground'>{view === 'home' ? '会社を考え、決め、任せる場所' : selectedSummary ? selectedSummary.objective : '仕事を選択してください'}</p></div>
        <Button variant='outline' size='sm' onClick={refresh} disabled={loading}><RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} />更新</Button>
        <Button size='sm' className='bg-[#171716] text-white hover:bg-black' onClick={() => { setDelegateObjective(''); setCreateOpen(true) }}><Plus className='size-4' />仕事を任せる</Button>
      </header>

      <main className='mx-auto max-w-[1480px] p-4 lg:p-8'>
        {error && <div className='mb-5 flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700'><span>{error}</span><button onClick={() => setError('')}><X className='size-4' /></button></div>}
        {view === 'home' && <CeoHome jobs={jobs} selectedJob={job} onOpenOperations={() => setView('operations')} onOpenCouncil={() => setView('council')} onDelegate={(objective) => { setDelegateObjective(objective || ''); setCreateOpen(true) }} />}
        {view === 'operations' && <Operations jobs={jobs} selectedId={selectedId} onSelect={setSelectedId} job={job} events={events} onCreate={() => { setDelegateObjective(''); setCreateOpen(true) }} />}
        {view === 'council' && <CouncilView council={council} job={job} tab={councilTab} setTab={setCouncilTab} />}
        {view === 'artifacts' && <ArtifactsView artifacts={artifacts} job={job} onOpen={setArtifact} />}
        {view === 'audit' && <AuditView audit={audit} />}
      </main>
    </div>
    {createOpen && <CreateDialog initialObjective={delegateObjective} onClose={() => setCreateOpen(false)} onCreated={id => { setCreateOpen(false); setSelectedId(id); setView('operations') }} />}
    {artifact && <ArtifactDialog artifact={artifact} onClose={() => setArtifact(null)} />}
  </div>
}

function PageIntro({ eyebrow, title, body, action }: { eyebrow: string; title: string; body: string; action?: ReactNode }) {
  return <div className='mb-7 flex flex-col gap-4 border-b border-[#e3e2de] pb-6 sm:flex-row sm:items-end sm:justify-between'>
    <div><p className='mb-1 text-xs font-medium text-muted-foreground'>{eyebrow}</p><h1 className='text-2xl font-semibold tracking-[-.025em]'>{title}</h1><p className='mt-2 max-w-2xl text-sm leading-6 text-muted-foreground'>{body}</p></div>{action}
  </div>
}

function Operations({ jobs, selectedId, onSelect, job, events, onCreate }: { jobs: Job[]; selectedId: string | null; onSelect: (id: string) => void; job: JobPayload | null; events: Event[]; onCreate: () => void }) {
  const result = job?.result || {}; const verification = result.verification || {}; const repo = result.selected_repository || {}; const report = result.execution_report || {}
  const stageIndex = useMemo(() => {
    const status = job?.status || 'queued'; if (status === 'completed') return pipeline.length
    const map: Record<string, number> = { queued: -1, researching: 0, analysis_researching: 0, analysis_proposing: 1, analysis_criticizing: 1, analysis_judging: 2, analysis_completed: 2, analysis_degraded: 2, cloning: 3, implementing: 4, verifying: 5 }
    return map[status] ?? -1
  }, [job?.status])
  return <>
    <PageIntro eyebrow='CONTROL PLANE' title='会社を動かす仕事を、ここから始める' body='GitHubから実装候補を探し、Councilで比較し、隔離領域で成果物を作り、検証結果まで一続きで残します。' action={<Button onClick={onCreate} className='bg-[#171716] text-white hover:bg-black'><Play className='size-4' />実行を作成</Button>} />
    <section className='grid gap-3 sm:grid-cols-2 xl:grid-cols-4'>
      <Metric label='現在の状態' value={job ? statusLabels[job.status] || job.status : '未選択'} icon={<Activity className='size-4' />} />
      <Metric label='採用OSS' value={safeText(repo.full_name, '未決定')} icon={<GitBranch className='size-4' />} />
      <Metric label='通過テスト' value={`${verification.passed_test_count ?? 0} 件`} icon={<CheckCircle2 className='size-4' />} />
      <Metric label='外部作用' value={job?.external_actions_performed ? '検出' : '0 件'} icon={<ShieldCheck className='size-4' />} emphasis />
    </section>

    <div className='mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,.8fr)]'>
      <Card className='rounded-xl border-[#e3e2de] shadow-none'><CardHeader className='border-b'><div className='flex items-center justify-between'><div><CardTitle className='text-base'>実行パイプライン</CardTitle><p className='mt-1 text-xs text-muted-foreground'>{safeText(result.objective, '実行を選択してください')}</p></div>{job && <StatusBadge status={job.status} />}</div></CardHeader>
        <CardContent className='p-0'>{job ? <div className='divide-y'>{pipeline.map((stage, index) => { const done = index < stageIndex || job.status === 'completed'; const active = index === stageIndex && job.status !== 'completed'; return <div key={stage[0]} className='grid grid-cols-[32px_minmax(0,1fr)_auto] items-center gap-3 px-5 py-4'><span className={`grid size-7 place-items-center rounded-full border text-xs ${done ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : active ? 'border-blue-300 bg-blue-50 text-blue-700' : 'bg-white text-muted-foreground'}`}>{done ? <Check className='size-3.5' /> : active ? <LoaderCircle className='size-3.5 animate-spin' /> : index + 1}</span><div><p className='text-sm font-medium'>{stage[1]}</p><p className='text-xs text-muted-foreground'>{stage[2]}</p></div><span className='text-xs text-muted-foreground'>{done ? '完了' : active ? '処理中' : '待機'}</span></div>})}</div> : <Empty icon={<Play className='size-5' />} title='実行がありません' body='「新しい実行」からGuildlessへ仕事を渡してください。' />}</CardContent>
      </Card>
      <Card className='rounded-xl border-[#e3e2de] shadow-none'><CardHeader className='border-b'><CardTitle className='text-base'>直近の活動</CardTitle></CardHeader><CardContent className='p-0'><div className='max-h-[430px] divide-y overflow-auto'>{events.length ? events.slice().reverse().map(event => <div key={event.sequence} className='flex gap-3 px-5 py-4'><span className='mt-1 size-2 shrink-0 rounded-full bg-[#a3a39d]' /><div className='min-w-0'><p className='text-sm font-medium'>{statusLabels[event.status] || event.status}</p><p className='mt-1 truncate text-xs text-muted-foreground'>{safeText(event.details?.message, safeText(event.details?.summary, '処理を記録しました'))}</p><time className='mt-1 block text-[11px] text-muted-foreground'>{formatDate(event.occurred_at)}</time></div></div>) : <Empty icon={<History className='size-5' />} title='まだ記録がありません' body='実行を開始すると、各段階がここへ時系列で表示されます。' />}</div></CardContent></Card>
    </div>

    <Card className='mt-6 rounded-xl border-[#e3e2de] shadow-none'><CardHeader className='flex-row items-center justify-between border-b'><div><CardTitle className='text-base'>実行履歴</CardTitle><p className='mt-1 text-xs text-muted-foreground'>行を選ぶと、全画面がその実行へ切り替わります。</p></div><span className='text-xs text-muted-foreground'>{jobs.length} runs</span></CardHeader><CardContent className='overflow-x-auto p-0'><table className='w-full min-w-[760px] text-left text-sm'><thead className='border-b bg-[#fafaf8] text-xs text-muted-foreground'><tr><th className='px-5 py-3 font-medium'>目的</th><th className='px-4 py-3 font-medium'>状態</th><th className='px-4 py-3 font-medium'>採用OSS</th><th className='px-4 py-3 font-medium'>テスト</th><th className='px-5 py-3 font-medium'>更新</th></tr></thead><tbody className='divide-y'>{jobs.map(item => <tr key={item.job_id} onClick={() => onSelect(item.job_id)} className={`cursor-pointer hover:bg-[#fafaf8] ${item.job_id === selectedId ? 'bg-[#f4f4f1]' : 'bg-white'}`}><td className='max-w-[480px] px-5 py-4'><p className='truncate font-medium'>{item.objective}</p><p className='mt-1 text-xs text-muted-foreground'>{shortId(item.job_id)}</p></td><td className='px-4 py-4'><StatusBadge status={item.status} /></td><td className='px-4 py-4 text-muted-foreground'>{item.repository || '—'}</td><td className='px-4 py-4'>{item.passed_test_count}</td><td className='px-5 py-4 text-muted-foreground'>{formatDate(item.updated_at)}</td></tr>)}</tbody></table>{!jobs.length && <Empty icon={<Search className='size-5' />} title='実行履歴は空です' body='最初の実行を作成してください。' />}</CardContent></Card>
    {report.summary && <div className='mt-6 rounded-lg border border-emerald-200 bg-emerald-50/60 p-4'><p className='text-xs font-semibold text-emerald-800'>直近の結果</p><p className='mt-1 text-sm leading-6 text-emerald-950'>{report.summary}</p></div>}
  </>
}

function Metric({ label, value, icon, emphasis = false }: { label: string; value: string; icon: ReactNode; emphasis?: boolean }) { return <Card className='rounded-xl border-[#e3e2de] shadow-none'><CardContent className='flex items-start justify-between p-5'><div><p className='text-xs text-muted-foreground'>{label}</p><p className={`mt-2 truncate text-lg font-semibold tracking-tight ${emphasis ? 'text-emerald-700' : ''}`}>{value}</p></div><span className='rounded-md border bg-[#fafaf8] p-2 text-muted-foreground'>{icon}</span></CardContent></Card> }

function CouncilView({ council, job, tab, setTab }: { council: Record<string, any> | null; job: JobPayload | null; tab: 'decision' | 'proposals' | 'criticism'; setTab: (tab: 'decision' | 'proposals' | 'criticism') => void }) {
  const decision = council?.decision || {}; const scores = Array.isArray(decision.scores) ? decision.scores : []
  const proposals = Array.isArray(council?.proposals) ? council.proposals : council?.proposals && typeof council.proposals === 'object' ? Object.values(council.proposals) : []
  const tabs = [{ id: 'decision', label: '最終判断' }, { id: 'proposals', label: `独立提案 ${proposals.length || ''}` }, { id: 'criticism', label: '反論・監査' }] as const
  return <><PageIntro eyebrow='DECISION ROOM' title='Councilの判断を、理由ごと確認する' body='候補は自動で確定方針へ昇格しません。提案・反論・最終判断を分けて表示します。' />
    {!council?.available ? <Empty icon={<UsersRound className='size-5' />} title='Council結果がありません' body={council?.message || (job ? 'この実行ではCouncil結果がまだ保存されていません。' : '実行を選択してください。')} /> : <>
      <div className='mb-5 flex flex-wrap items-center gap-2 border-b'>{tabs.map(item => <button key={item.id} onClick={() => setTab(item.id)} className={`border-b-2 px-3 py-2.5 text-sm font-medium ${tab === item.id ? 'border-[#171716] text-[#171716]' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>{item.label}</button>)}<span className='ml-auto mb-2 rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 ring-1 ring-amber-200'>未確定候補</span></div>
      {tab === 'decision' && <div className='grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,.8fr)]'><Card className='rounded-xl border-[#e3e2de] shadow-none'><CardHeader className='border-b'><div className='flex items-center justify-between'><CardTitle className='text-base'>最終判断</CardTitle><span className='text-2xl font-semibold'>{Math.round(Number(decision.confidence || 0) * 100)}<small className='ml-1 text-xs font-normal text-muted-foreground'>% confidence</small></span></div></CardHeader><CardContent className='space-y-5 p-5'><TextBlock label='判断' text={safeText(decision.decision, '判断文は保存されていません')} /><TextBlock label='推奨アクション' text={safeText(decision.recommended_action)} /><TextBlock label='反対意見' text={safeText(decision.opposing_view)} /><TextBlock label='次回レビュー' text={safeText(decision.review_after)} /></CardContent></Card><Card className='rounded-xl border-[#e3e2de] shadow-none'><CardHeader className='border-b'><CardTitle className='text-base'>評価内訳</CardTitle></CardHeader><CardContent className='divide-y p-0'>{scores.length ? scores.map((score: any, i: number) => <div key={`${score.criterion}-${i}`} className='px-5 py-4'><div className='flex items-center justify-between'><p className='text-sm font-medium'>{safeText(score.criterion)}</p><span className='text-sm font-semibold'>{score.score ?? '—'} / 10</span></div><div className='mt-2 h-1.5 overflow-hidden rounded-full bg-muted'><div className='h-full bg-[#2f6b55]' style={{ width: `${Math.min(100, Number(score.score || 0) * 10)}%` }} /></div><p className='mt-2 text-xs leading-5 text-muted-foreground'>{safeText(score.reason)}</p></div>) : <Empty icon={<Sparkles className='size-5' />} title='評価項目なし' body='Councilの採点が保存されると表示します。' />}</CardContent></Card></div>}
      {tab === 'proposals' && <div className='grid gap-4 lg:grid-cols-2'>{proposals.length ? proposals.map((proposal: any, index: number) => <Card key={index} className='rounded-xl border-[#e3e2de] shadow-none'><CardHeader className='border-b'><div className='flex items-center gap-3'><span className='grid size-8 place-items-center rounded-md border bg-[#fafaf8] text-xs font-semibold'>{index + 1}</span><div><CardTitle className='text-sm'>{safeText(proposal.role, safeText(proposal.provider, `提案 ${index + 1}`))}</CardTitle><p className='text-xs text-muted-foreground'>独立生成</p></div></div></CardHeader><CardContent className='space-y-4 p-5'><TextBlock label='提案' text={safeText(proposal.proposal, safeText(proposal.recommendation, safeText(proposal.decision)))} /><TextBlock label='根拠' text={safeText(proposal.reasoning_summary, safeText(proposal.reasoning))} /><p className='text-xs text-muted-foreground'>Confidence: {proposal.confidence ?? '—'}</p></CardContent></Card>) : <Empty icon={<Bot className='size-5' />} title='提案データなし' body='独立提案が保存されるとここに並びます。' />}</div>}
      {tab === 'criticism' && <div className='grid gap-6 lg:grid-cols-2'><JsonCard title='反論' value={council.criticism} /><JsonCard title='再反論' value={council.rebuttals} /></div>}
    </>}
  </>
}

function TextBlock({ label, text }: { label: string; text: string }) { return <div><p className='mb-1 text-xs font-medium text-muted-foreground'>{label}</p><p className='whitespace-pre-wrap text-sm leading-6'>{text}</p></div> }
function JsonCard({ title, value }: { title: string; value: unknown }) { return <Card className='rounded-xl border-[#e3e2de] shadow-none'><CardHeader className='border-b'><CardTitle className='text-base'>{title}</CardTitle></CardHeader><CardContent className='p-5'><pre className='max-h-[560px] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-[#f5f5f2] p-4 text-xs leading-5'>{JSON.stringify(value, null, 2)}</pre></CardContent></Card> }

function ArtifactsView({ artifacts, job, onOpen }: { artifacts: Artifact[]; job: JobPayload | null; onOpen: (artifact: Artifact) => void }) {
  return <><PageIntro eyebrow='DELIVERABLES' title='作ったものを、ファイル単位で検証する' body='実在する成果物だけを表示し、サイズとSHA-256を付けています。原本の存在を確認できない主張はここには出ません。' />
    <Card className='rounded-xl border-[#e3e2de] shadow-none'><CardHeader className='flex-row items-center justify-between border-b'><div><CardTitle className='text-base'>成果物</CardTitle><p className='mt-1 text-xs text-muted-foreground'>{job ? `${shortId(job.job_id)} の出力` : '実行を選択してください'}</p></div><span className='text-sm font-medium'>{artifacts.filter(item => item.exists).length} / {artifacts.length}</span></CardHeader><CardContent className='overflow-x-auto p-0'>{artifacts.length ? <table className='w-full min-w-[720px] text-left text-sm'><thead className='border-b bg-[#fafaf8] text-xs text-muted-foreground'><tr><th className='px-5 py-3 font-medium'>ファイル</th><th className='px-4 py-3 font-medium'>検証</th><th className='px-4 py-3 font-medium'>サイズ</th><th className='px-4 py-3 font-medium'>SHA-256</th><th className='px-5 py-3'></th></tr></thead><tbody className='divide-y'>{artifacts.map(item => <tr key={item.path} className='bg-white hover:bg-[#fafaf8]'><td className='px-5 py-4'><div className='flex items-center gap-3'><span className='rounded-md border bg-[#fafaf8] p-2 text-muted-foreground'>{item.path.endsWith('.md') || item.path.endsWith('.txt') ? <FileText className='size-4' /> : <FileCode2 className='size-4' />}</span><span className='font-medium'>{item.path.replace(/^output\//, '')}</span></div></td><td className='px-4 py-4'>{item.exists ? <span className='inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700'><CheckCircle2 className='size-4' />存在確認済み</span> : <span className='text-xs font-medium text-red-700'>欠損</span>}</td><td className='px-4 py-4 text-muted-foreground'>{formatSize(item.size)}</td><td className='max-w-48 px-4 py-4'><code className='block truncate text-xs text-muted-foreground'>{item.sha256 || '—'}</code></td><td className='px-5 py-4 text-right'><Button variant='outline' size='sm' disabled={!item.preview} onClick={() => onOpen(item)}>開く<ArrowRight className='size-3.5' /></Button></td></tr>)}</tbody></table> : <Empty icon={<Archive className='size-5' />} title='成果物はまだありません' body='実装と検証が完了すると、実在ファイルがここへ表示されます。' />}</CardContent></Card>
  </>
}

function AuditView({ audit }: { audit: Record<string, any> | null }) {
  const execution = audit?.execution || {}; const verification = audit?.verification || {}; const events: Event[] = audit?.events || []
  return <><PageIntro eyebrow='AUDIT TRAIL' title='何を見て、何をして、どこで止まったか' body='モデルの使用量、処理時間、ソース改変、禁止操作、外部作用を一つの監査証跡として確認します。' />
    <section className='grid gap-3 sm:grid-cols-2 xl:grid-cols-4'><Metric label='外部作用' value={audit?.external_actions_performed ? '検出' : '0 件'} icon={<ShieldCheck className='size-4' />} emphasis /><Metric label='ソース原本' value={verification.source_unchanged === false ? '変更あり' : verification.source_unchanged === true ? '変更なし' : '未検証'} icon={<Code2 className='size-4' />} /><Metric label='処理時間' value={execution.latency_ms ? `${(execution.latency_ms / 1000).toFixed(1)} 秒` : '—'} icon={<Clock3 className='size-4' />} /><Metric label='出力トークン' value={execution.usage?.output_tokens?.toLocaleString('ja-JP') || '—'} icon={<Bot className='size-4' />} /></section>
    <div className='mt-6 grid gap-6 xl:grid-cols-2'><Card className='rounded-xl border-[#e3e2de] shadow-none'><CardHeader className='border-b'><CardTitle className='text-base'>安全性チェック</CardTitle></CardHeader><CardContent className='divide-y p-0'><AuditRow label='Sandbox' value={execution.sandbox || '—'} /><AuditRow label='実行方式' value={execution.executor || '—'} /><AuditRow label='ネットワーク許可' value={execution.network_permission_granted ? 'あり' : 'なし'} good={!execution.network_permission_granted} /><AuditRow label='危険な迂回' value={execution.dangerous_bypass_used ? '使用' : '未使用'} good={!execution.dangerous_bypass_used} /><AuditRow label='禁止コマンド' value={(execution.prohibited_commands || []).length ? execution.prohibited_commands.join(', ') : '0 件'} good={!(execution.prohibited_commands || []).length} /><AuditRow label='確定方針への自動昇格' value={audit?.confirmed_decision_created ? 'あり' : 'なし'} good={!audit?.confirmed_decision_created} /></CardContent></Card>
      <Card className='rounded-xl border-[#e3e2de] shadow-none'><CardHeader className='border-b'><CardTitle className='text-base'>ハッシュ検証</CardTitle></CardHeader><CardContent className='space-y-5 p-5'><HashBlock label='実行前' value={verification.source_hash_before} /><HashBlock label='実行後' value={verification.source_hash_after} /><div className={`rounded-lg border p-4 text-sm ${verification.source_unchanged ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{verification.source_unchanged ? '固定コミットの原本は変更されていません。' : '原本ハッシュの一致を確認できません。'}</div></CardContent></Card></div>
    <Card className='mt-6 rounded-xl border-[#e3e2de] shadow-none'><CardHeader className='border-b'><CardTitle className='text-base'>時系列ログ</CardTitle></CardHeader><CardContent className='overflow-x-auto p-0'>{events.length ? <table className='w-full min-w-[720px] text-left text-sm'><thead className='border-b bg-[#fafaf8] text-xs text-muted-foreground'><tr><th className='px-5 py-3 font-medium'>#</th><th className='px-4 py-3 font-medium'>時刻</th><th className='px-4 py-3 font-medium'>状態</th><th className='px-5 py-3 font-medium'>詳細</th></tr></thead><tbody className='divide-y'>{events.map(event => <tr key={event.sequence}><td className='px-5 py-3 text-muted-foreground'>{event.sequence}</td><td className='px-4 py-3 text-muted-foreground'>{formatDate(event.occurred_at)}</td><td className='px-4 py-3'><StatusBadge status={event.status} /></td><td className='max-w-xl px-5 py-3 text-muted-foreground'>{safeText(event.details?.message, safeText(event.details?.summary, JSON.stringify(event.details || {})))}</td></tr>)}</tbody></table> : <Empty icon={<ClipboardCheck className='size-5' />} title='監査ログがありません' body='実行を選択すると時系列ログを表示します。' />}</CardContent></Card>
  </>
}

function AuditRow({ label, value, good = false }: { label: string; value: string; good?: boolean }) { return <div className='flex items-center justify-between gap-4 px-5 py-4'><span className='text-sm text-muted-foreground'>{label}</span><span className={`text-right text-sm font-medium ${good ? 'text-emerald-700' : ''}`}>{value}</span></div> }
function HashBlock({ label, value }: { label: string; value?: string }) { return <div><p className='mb-1 text-xs font-medium text-muted-foreground'>{label}</p><code className='block overflow-hidden text-ellipsis rounded-md bg-[#f5f5f2] px-3 py-2 text-xs'>{value || '—'}</code></div> }

function CreateDialog({ initialObjective, onClose, onCreated }: { initialObjective?: string; onClose: () => void; onCreated: (id: string) => void }) {
  const [objective, setObjective] = useState(initialObjective || '既存OSSを調査し、Guildlessへ再利用できる最小構成を実装してテストする')
  const [queries, setQueries] = useState('multi agent council orchestration\nagent decision audit framework')
  const [providers, setProviders] = useState<string[]>(['deepseek', 'codex'])
  const [submitting, setSubmitting] = useState(false); const [error, setError] = useState('')
  const toggle = (provider: string) => setProviders(current => current.includes(provider) ? current.filter(item => item !== provider) : [...current, provider])
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(''); if (providers.length < 2) { setError('Councilには2モデル以上を選んでください。'); return } setSubmitting(true); try { const data = await api<{ run_id: string }>('/v1/guildless/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ objective, github_queries: queries.split('\n').map(v => v.trim()).filter(Boolean), context: {}, allowed_providers: providers, workspace_label: 'ui', max_rounds: 1, max_execution_minutes: 20, constraints: { license_allowlist: ['MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause'], min_stars: 0, max_candidates: 10, active_within_days: 730 } }) }); onCreated(data.run_id) } catch (e) { setError(e instanceof Error ? e.message : '開始できませんでした') } finally { setSubmitting(false) } }
  return <div className='fixed inset-0 z-50 grid place-items-center bg-black/30 p-4' role='dialog' aria-modal='true' aria-label='新しい実行'><form onSubmit={submit} className='w-full max-w-2xl rounded-xl border bg-white shadow-2xl'><div className='flex items-start justify-between border-b px-6 py-5'><div><h2 className='text-lg font-semibold'>新しい実行</h2><p className='mt-1 text-sm text-muted-foreground'>目的と探索条件を固定してから実行します。</p></div><button type='button' onClick={onClose} className='rounded-md p-2 hover:bg-muted' aria-label='閉じる'><X className='size-4' /></button></div><div className='space-y-5 px-6 py-5'><label className='block'><span className='mb-2 block text-sm font-medium'>目的</span><textarea required value={objective} onChange={e => setObjective(e.target.value)} className='min-h-28 w-full rounded-lg border bg-white px-3 py-2.5 text-sm leading-6 outline-none focus:border-[#777] focus:ring-2 focus:ring-[#ddd]' /></label><label className='block'><span className='mb-2 block text-sm font-medium'>GitHub検索語（1行1件）</span><textarea required value={queries} onChange={e => setQueries(e.target.value)} className='min-h-24 w-full rounded-lg border bg-white px-3 py-2.5 font-mono text-sm outline-none focus:border-[#777] focus:ring-2 focus:ring-[#ddd]' /></label><div><span className='mb-2 block text-sm font-medium'>Councilモデル</span><div className='grid grid-cols-2 gap-2 sm:grid-cols-4'>{['deepseek', 'codex', 'claude', 'sakana'].map(provider => <button key={provider} type='button' onClick={() => toggle(provider)} className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${providers.includes(provider) ? 'border-[#555] bg-[#f3f3f0]' : 'bg-white text-muted-foreground'}`}><span>{provider}</span>{providers.includes(provider) && <Check className='size-4' />}</button>)}</div></div>{error && <p className='text-sm text-red-600'>{error}</p>}<div className='rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs leading-5 text-emerald-800'>外部公開・送信・契約・決済は実行しません。成果物は隔離された出力領域へ保存します。</div></div><div className='flex justify-end gap-2 border-t bg-[#fafaf8] px-6 py-4'><Button type='button' variant='outline' onClick={onClose}>キャンセル</Button><Button type='submit' disabled={submitting} className='bg-[#171716] text-white hover:bg-black'>{submitting ? <LoaderCircle className='size-4 animate-spin' /> : <Play className='size-4' />}{submitting ? '開始中' : '実行を開始'}</Button></div></form></div>
}

function ArtifactDialog({ artifact, onClose }: { artifact: Artifact; onClose: () => void }) { const copy = () => navigator.clipboard.writeText(artifact.preview || '').catch(() => undefined); return <div className='fixed inset-0 z-50 grid place-items-center bg-black/30 p-4' role='dialog' aria-modal='true' aria-label='成果物プレビュー'><div className='flex max-h-[88vh] w-full max-w-4xl flex-col rounded-xl border bg-white shadow-2xl'><div className='flex items-center justify-between border-b px-5 py-4'><div><h2 className='text-sm font-semibold'>{artifact.path}</h2><p className='mt-1 text-xs text-muted-foreground'>{formatSize(artifact.size)} · {artifact.sha256?.slice(0, 16)}…</p></div><div className='flex gap-2'><Button variant='outline' size='sm' onClick={copy}>コピー</Button><button onClick={onClose} className='rounded-md p-2 hover:bg-muted' aria-label='閉じる'><X className='size-4' /></button></div></div><pre className='min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words bg-[#f7f7f5] p-6 font-mono text-xs leading-5'>{artifact.preview || 'プレビューできません'}</pre></div></div> }
